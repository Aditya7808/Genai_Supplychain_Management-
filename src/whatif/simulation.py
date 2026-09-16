"""
What-If Scenario Simulation Engine for supply chain stress-testing.
Simulates demand surges, supplier lead time delays, promotional lifts, and cost shocks.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from src.forecasting.service import load_historical_sales_df
from src.replenishment.calculator import get_sku_replenishment_status

logger = logging.getLogger(__name__)


def simulate_scenario(
    sku_id: str,
    warehouse_id: str,
    demand_shock_pct: float = 0.0,
    lead_time_delay_days: int = 0,
    promo_lift_pct: float = 0.0,
    promo_duration_days: int = 7,
    horizon_days: int = 30,
) -> Dict[str, Any]:
    """
    Simulate inventory trajectory under what-if stress conditions:

    Args:
        sku_id: Product SKU ID
        warehouse_id: Target warehouse ID
        demand_shock_pct: Overall percentage demand change (+25 for +25%, -20 for -20%)
        lead_time_delay_days: Additional days added to supplier arrival
        promo_lift_pct: Demand spike during promotional campaign
        promo_duration_days: Length of promotional surge (days)
        horizon_days: Simulation duration in days
    """
    status = get_sku_replenishment_status(sku_id=sku_id, warehouse_id=warehouse_id)
    current_stock = float(status.get("current_stock", 100.0))
    base_daily_demand = float(status.get("daily_demand_mean", 10.0))
    unit_cost = float(status.get("unit_cost", 100.0))
    unit_price = float(status.get("unit_price", 150.0))
    lead_time = float(status.get("lead_time_days", 7.0)) + lead_time_delay_days
    safety_stock = float(status.get("safety_stock", 30.0))

    sim_date = date.today()
    daily_trajectory: List[Dict[str, Any]] = []

    stock = current_stock
    stockout_day: Optional[int] = None
    stockout_date: Optional[str] = None
    total_unmet_demand = 0.0
    pending_orders: List[Dict[str, Any]] = []

    # If current stock is below ROP at day 0, place an initial simulated replenishment order
    reorder_point = float(status.get("reorder_point", 50.0))
    eoq = float(status.get("eoq", 80.0))
    if stock <= reorder_point:
        pending_orders.append({
            "arrival_day": int(lead_time),
            "quantity": eoq,
        })

    for day in range(1, horizon_days + 1):
        target_d = (sim_date + timedelta(days=day)).strftime("%Y-%m-%d")

        # Demand adjustment: baseline * (1 + shock) * (1 + promo if within promo window)
        daily_mult = 1.0 + (demand_shock_pct / 100.0)
        if day <= promo_duration_days and promo_lift_pct != 0:
            daily_mult *= (1.0 + (promo_lift_pct / 100.0))

        simulated_demand = max(0.0, base_daily_demand * daily_mult)

        # Receive arriving orders
        for po in pending_orders:
            if po["arrival_day"] == day:
                stock += po["quantity"]

        # Satisfy demand
        if stock >= simulated_demand:
            stock -= simulated_demand
            unmet = 0.0
        else:
            unmet = simulated_demand - stock
            stock = 0.0
            total_unmet_demand += unmet
            if stockout_day is None:
                stockout_day = day
                stockout_date = target_d

        # Check if new reorder is triggered
        if stock <= reorder_point and not any(po["arrival_day"] > day for po in pending_orders):
            pending_orders.append({
                "arrival_day": day + int(lead_time),
                "quantity": eoq,
            })

        daily_trajectory.append({
            "day": day,
            "date": target_d,
            "stock_level": round(stock, 1),
            "projected_demand": round(simulated_demand, 1),
            "unmet_demand": round(unmet, 1),
            "is_stockout": stock <= 0,
        })

    revenue_at_risk = round(total_unmet_demand * unit_price, 2)
    margin_at_risk = round(total_unmet_demand * (unit_price - unit_cost), 2)

    return {
        "sku_id": sku_id,
        "warehouse_id": warehouse_id,
        "scenario_params": {
            "demand_shock_pct": demand_shock_pct,
            "lead_time_delay_days": lead_time_delay_days,
            "promo_lift_pct": promo_lift_pct,
            "promo_duration_days": promo_duration_days,
            "effective_lead_time_days": lead_time,
        },
        "stockout_occurred": stockout_day is not None,
        "stockout_day": stockout_day,
        "stockout_date": stockout_date,
        "total_unmet_demand": round(total_unmet_demand, 1),
        "revenue_at_risk": revenue_at_risk,
        "margin_at_risk": margin_at_risk,
        "recommended_safety_stock_adjustment": round(
            safety_stock * (1.0 + (demand_shock_pct / 100.0) * 0.5 + (lead_time_delay_days / 10.0)), 1
        ),
        "trajectory": daily_trajectory,
    }
