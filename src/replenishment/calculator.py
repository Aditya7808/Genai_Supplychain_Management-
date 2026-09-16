"""
Inventory replenishment engine: calculates Reorder Point (ROP), Safety Stock,
Economic Order Quantity (EOQ), stockout risk, and suggested purchase orders.
"""

from __future__ import annotations

import math
import logging
from datetime import date
from typing import Dict, List, Optional, Any

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.ingestion.models import SkuMaster, InventoryLevel, SupplierLeadtime, SalesHistory

logger = logging.getLogger(__name__)

# Standard Normal Z-values for service levels
SERVICE_LEVEL_Z = {
    0.90: 1.28,
    0.95: 1.645,
    0.98: 2.05,
    0.99: 2.33,
}


def calculate_replenishment_parameters(
    current_stock: float,
    daily_demand_mean: float,
    daily_demand_std: float,
    lead_time_days: float,
    lead_time_std: float = 1.5,
    unit_cost: float = 100.0,
    service_level: float = 0.95,
    holding_cost_rate: float = 0.20,
    order_cost: float = 500.0,
) -> Dict[str, Any]:
    """
    Calculate inventory optimization metrics using classic supply chain formulas:
    - Safety Stock: Z * sqrt(L * sigma_d^2 + d^2 * sigma_L^2)
    - Reorder Point (ROP): d * L + Safety Stock
    - Days of Inventory (DOI): Current Stock / Daily Demand
    - Economic Order Quantity (EOQ): sqrt(2 * D * S / H)
    """
    z = SERVICE_LEVEL_Z.get(service_level, 1.645)
    L = max(lead_time_days, 1.0)
    d = max(daily_demand_mean, 0.01)
    sig_d = max(daily_demand_std, 0.01)
    sig_L = max(lead_time_std, 0.5)

    # Combined lead-time and demand variance formula
    variance_term = (L * (sig_d ** 2)) + ((d ** 2) * (sig_L ** 2))
    safety_stock = z * math.sqrt(max(variance_term, 0.01))
    reorder_point = (d * L) + safety_stock

    # Days of Inventory
    days_of_inventory = current_stock / d if d > 0 else 999.0

    # Annual demand approximation for EOQ
    annual_demand = d * 365.0
    holding_cost_per_unit = max(unit_cost * holding_cost_rate, 1.0)
    eoq = math.sqrt((2.0 * annual_demand * order_cost) / holding_cost_per_unit)

    # Stockout risk status
    if current_stock <= safety_stock:
        status = "CRITICAL"
        risk_label = "HIGH"
        recommended_order = max(math.ceil(reorder_point + eoq - current_stock), math.ceil(eoq))
    elif current_stock <= reorder_point:
        status = "WARNING"
        risk_label = "MEDIUM"
        recommended_order = max(math.ceil(reorder_point - current_stock + eoq * 0.5), 10)
    else:
        status = "HEALTHY"
        risk_label = "LOW"
        recommended_order = 0

    return {
        "current_stock": round(current_stock, 1),
        "daily_demand_mean": round(d, 2),
        "daily_demand_std": round(sig_d, 2),
        "lead_time_days": round(L, 1),
        "safety_stock": round(safety_stock, 1),
        "reorder_point": round(reorder_point, 1),
        "days_of_inventory": round(days_of_inventory, 1),
        "eoq": round(eoq, 1),
        "status": status,
        "risk_level": risk_label,
        "recommended_order_quantity": recommended_order,
    }


def get_sku_replenishment_status(
    sku_id: str,
    warehouse_id: str,
    service_level: float = 0.95,
) -> Dict[str, Any]:
    """Compute replenishment status for a specific SKU and warehouse from DB records."""
    session = SessionLocal()
    try:
        # 1. Current stock
        inv_record = session.query(InventoryLevel).filter(
            and_(
                InventoryLevel.sku_id == sku_id,
                InventoryLevel.warehouse_id == warehouse_id,
            )
        ).order_by(InventoryLevel.date.desc()).first()

        current_stock = float(inv_record.on_hand) if inv_record else 100.0

        # 2. SKU Master info
        sku_master = session.query(SkuMaster).filter(SkuMaster.sku_id == sku_id).first()
        unit_cost = float(sku_master.unit_cost) if sku_master else 100.0
        unit_price = float(sku_master.unit_price) if sku_master else 150.0

        # 3. Lead time from supplier table
        supplier = session.query(SupplierLeadtime).filter(
            SupplierLeadtime.sku_id == sku_id
        ).first()
        lead_time_days = float(supplier.lead_time_days) if supplier else 7.0

        # 4. Recent sales demand statistics (last 60 days)
        sales = session.query(SalesHistory.units_sold).filter(
            and_(
                SalesHistory.sku_id == sku_id,
                SalesHistory.warehouse_id == warehouse_id,
            )
        ).order_by(SalesHistory.date.desc()).limit(60).all()

        if sales:
            quantities = [float(s[0]) for s in sales]
            d_mean = float(np.mean(quantities))
            d_std = float(np.std(quantities)) if len(quantities) > 1 else 1.0
        else:
            d_mean = 5.0
            d_std = 2.0

        metrics = calculate_replenishment_parameters(
            current_stock=current_stock,
            daily_demand_mean=d_mean,
            daily_demand_std=d_std,
            lead_time_days=lead_time_days,
            unit_cost=unit_cost,
            service_level=service_level,
        )

        metrics["sku_id"] = sku_id
        metrics["warehouse_id"] = warehouse_id
        metrics["unit_cost"] = unit_cost
        metrics["unit_price"] = unit_price
        metrics["supplier_name"] = f"Supplier-{supplier.supplier_id}" if supplier else "Primary Supplier"

        return metrics
    finally:
        session.close()


def get_all_low_stock_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    """Scan latest inventory and return all items requiring replenishment."""
    session = SessionLocal()
    try:
        # Get latest distinct inventory for each sku + warehouse
        # Subquery to find max date per sku+warehouse
        from sqlalchemy import func
        subq = (
            session.query(
                InventoryLevel.sku_id,
                InventoryLevel.warehouse_id,
                func.max(InventoryLevel.date).label("max_date"),
            )
            .group_by(InventoryLevel.sku_id, InventoryLevel.warehouse_id)
            .subquery()
        )

        latest_inv = (
            session.query(InventoryLevel)
            .join(
                subq,
                and_(
                    InventoryLevel.sku_id == subq.c.sku_id,
                    InventoryLevel.warehouse_id == subq.c.warehouse_id,
                    InventoryLevel.date == subq.c.max_date,
                ),
            )
            .all()
        )

        alerts = []
        for inv in latest_inv:
            stock = float(inv.on_hand)
            rop = float(inv.reorder_point) if inv.reorder_point else 100.0
            safety = float(rop * 0.5)

            if stock <= rop:
                alerts.append({
                    "sku_id": inv.sku_id,
                    "warehouse_id": inv.warehouse_id,
                    "current_stock": stock,
                    "reorder_point": rop,
                    "safety_stock": safety,
                    "deficit": max(0.0, rop - stock),
                    "status": "CRITICAL" if stock <= safety else "WARNING",
                })

        # Sort critical first, then highest deficit
        alerts.sort(key=lambda x: (0 if x["status"] == "CRITICAL" else 1, -x["deficit"]))
        return alerts[:limit]
    finally:
        session.close()
