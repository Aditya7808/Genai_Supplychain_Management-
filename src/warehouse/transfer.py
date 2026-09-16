"""
Inter-warehouse transfer and stock rebalancing optimization engine.
Evaluates surplus vs. deficit warehouses and compares transfer cost/lead-time against supplier reorders.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from src.database import SessionLocal
from src.ingestion.models import (
    InventoryLevel,
    WarehouseMetadata,
    WarehouseDistance,
    SupplierLeadtime,
    SkuMaster,
)

logger = logging.getLogger(__name__)


def find_transfer_opportunities(
    target_sku_id: str,
    deficit_warehouse_id: str,
    needed_quantity: float,
) -> List[Dict[str, Any]]:
    """
    Find candidate source warehouses that have surplus stock of target_sku_id
    and calculate transfer costs, transit time, and trade-offs against a supplier purchase order.
    """
    session = SessionLocal()
    opportunities: List[Dict[str, Any]] = []

    try:
        # 1. Get latest inventory levels for this SKU across all warehouses
        # Find latest inventory records
        all_inv = (
            session.query(InventoryLevel)
            .filter(InventoryLevel.sku_id == target_sku_id)
            .order_by(InventoryLevel.date.desc())
            .all()
        )

        # Keep only the latest entry per warehouse
        latest_by_wh: Dict[str, InventoryLevel] = {}
        for inv in all_inv:
            if inv.warehouse_id not in latest_by_wh:
                latest_by_wh[inv.warehouse_id] = inv

        # 2. Get supplier lead time & cost for comparison
        supplier_info = (
            session.query(SupplierLeadtime)
            .filter(SupplierLeadtime.sku_id == target_sku_id)
            .first()
        )
        supplier_lead_time_days = float(supplier_info.lead_time_days) if supplier_info else 10.0

        sku_meta = session.query(SkuMaster).filter(SkuMaster.sku_id == target_sku_id).first()
        unit_cost = float(sku_meta.unit_cost) if sku_meta else 100.0

        # 3. Check each potential source warehouse
        for wh_id, inv in latest_by_wh.items():
            if wh_id == deficit_warehouse_id:
                continue

            stock = float(inv.on_hand)
            rop = float(inv.reorder_point) if inv.reorder_point else 100.0
            safety = float(rop * 0.5)

            # Safe surplus = stock above (ROP + 20% safety buffer)
            surplus = max(0.0, stock - (rop + safety * 0.2))
            if surplus < 5.0:
                continue  # Not enough surplus to transfer safely

            transferable_qty = min(surplus, needed_quantity)

            # Query distance and transfer cost
            dist_rec = (
                session.query(WarehouseDistance)
                .filter(
                    and_(
                        WarehouseDistance.from_warehouse == wh_id,
                        WarehouseDistance.to_warehouse == deficit_warehouse_id,
                    )
                )
                .first()
            )

            distance_km = float(dist_rec.distance_km) if dist_rec else 800.0
            cost_per_unit = float(dist_rec.transfer_cost_per_unit) if (dist_rec and dist_rec.transfer_cost_per_unit) else 4.5

            # Estimated road transit time in days (~450 km/day + 0.5 day handling)
            transit_days = max(1, round((distance_km / 450.0) + 0.5, 1))
            total_transfer_cost = round(transferable_qty * cost_per_unit, 2)

            # Supplier purchase order baseline
            supplier_order_total = round(transferable_qty * unit_cost, 2)
            days_saved = max(0.0, supplier_lead_time_days - transit_days)

            # Warehouse metadata
            source_meta = session.query(WarehouseMetadata).filter(WarehouseMetadata.warehouse_id == wh_id).first()
            source_city = source_meta.city if source_meta else wh_id

            opportunities.append({
                "source_warehouse_id": wh_id,
                "source_city": source_city,
                "available_surplus": round(surplus, 1),
                "transferable_quantity": round(transferable_qty, 1),
                "distance_km": round(distance_km, 1),
                "transit_days": transit_days,
                "cost_per_unit": cost_per_unit,
                "total_transfer_cost": total_transfer_cost,
                "supplier_lead_time_days": supplier_lead_time_days,
                "days_saved": days_saved,
                "is_faster_than_supplier": transit_days < supplier_lead_time_days,
                "recommendation": (
                    f"Transfer {round(transferable_qty)} units from {source_city} ({wh_id}) to arrive in "
                    f"{transit_days} days (saves {days_saved} days vs supplier) at ₹{total_transfer_cost:,.2f} transfer cost."
                ),
            })

        # Rank opportunities by fastest transit then lowest cost
        opportunities.sort(key=lambda x: (x["transit_days"], x["total_transfer_cost"]))
        return opportunities
    finally:
        session.close()
