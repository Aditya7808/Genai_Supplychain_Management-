"""
Tool definitions and implementations for the GenAI reasoning layer.
These functions can be invoked directly or mapped to OpenAI/OpenRouter tool calling schemas.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.forecasting.service import generate_forecast
from src.replenishment.calculator import get_sku_replenishment_status, get_all_low_stock_alerts
from src.warehouse.transfer import find_transfer_opportunities
from src.whatif.simulation import simulate_scenario
from src.anomaly.detector import detect_demand_anomalies
from src.rag.retriever import retrieve_context, format_context_for_prompt
from src.database import SessionLocal
from src.ingestion.models import Approval, InventoryLevel, SkuMaster

logger = logging.getLogger(__name__)


def tool_get_forecast(sku_id: str, warehouse_id: str, horizon_days: int = 30) -> Dict[str, Any]:
    """Retrieve or compute statistical demand forecast for a SKU and warehouse."""
    try:
        res = generate_forecast(sku_id=sku_id, warehouse_id=warehouse_id, horizon_days=horizon_days)
        return {
            "sku_id": res.sku_id,
            "warehouse_id": res.warehouse_id,
            "horizon_days": res.horizon_days,
            "total_projected_demand": round(res.total_projected_demand, 1),
            "avg_daily_demand": round(res.avg_daily_projected_demand, 1),
            "model_name": res.model_name,
            "metrics": res.metrics.to_dict() if res.metrics else {},
            "sample_predictions": [
                {"date": p.date, "pred": p.predicted_demand, "lower": p.lower_bound, "upper": p.upper_bound}
                for p in res.predictions[:7]
            ],
        }
    except Exception as e:
        logger.error(f"tool_get_forecast error: {e}")
        return {"error": str(e)}


def tool_get_inventory(sku_id: str, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    """Check current stock level, safety stock, and ROP for a SKU."""
    session = SessionLocal()
    try:
        q = session.query(InventoryLevel).filter(InventoryLevel.sku_id == sku_id)
        if warehouse_id:
            q = q.filter(InventoryLevel.warehouse_id == warehouse_id)
        latest_records = q.order_by(InventoryLevel.date.desc()).limit(5).all()

        if not latest_records:
            return {"error": f"No inventory record found for SKU {sku_id}"}

        items = []
        for r in latest_records:
            stock = float(r.on_hand)
            rop = float(r.reorder_point or 0)
            safety = float(rop * 0.5)
            items.append({
                "sku_id": r.sku_id,
                "warehouse_id": r.warehouse_id,
                "current_stock": stock,
                "reorder_point": rop,
                "safety_stock": safety,
                "status": "CRITICAL" if stock <= safety else ("WARNING" if stock <= rop else "HEALTHY"),
            })
        return {"sku_id": sku_id, "inventory": items}
    finally:
        session.close()


def tool_get_replenishment_recommendation(sku_id: str, warehouse_id: str) -> Dict[str, Any]:
    """Calculate ROP, safety stock, EOQ, and recommended order quantity."""
    return get_sku_replenishment_status(sku_id=sku_id, warehouse_id=warehouse_id)


def tool_check_transfer_options(sku_id: str, deficit_warehouse_id: str, needed_quantity: float) -> Dict[str, Any]:
    """Find candidate surplus warehouses for stock rebalancing transfers."""
    opportunities = find_transfer_opportunities(
        target_sku_id=sku_id,
        deficit_warehouse_id=deficit_warehouse_id,
        needed_quantity=needed_quantity,
    )
    return {
        "sku_id": sku_id,
        "deficit_warehouse_id": deficit_warehouse_id,
        "needed_quantity": needed_quantity,
        "transfer_options": opportunities,
    }


def tool_simulate_whatif(
    sku_id: str,
    warehouse_id: str,
    demand_shock_pct: float = 0.0,
    lead_time_delay_days: int = 0,
    promo_lift_pct: float = 0.0,
) -> Dict[str, Any]:
    """Simulate what-if stress scenario and report stockout risk and revenue at risk."""
    return simulate_scenario(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        demand_shock_pct=demand_shock_pct,
        lead_time_delay_days=lead_time_delay_days,
        promo_lift_pct=promo_lift_pct,
    )


def tool_search_rag_context(query: str, region: Optional[str] = None) -> Dict[str, Any]:
    """Search ChromaDB knowledge base for festival calendar, supplier policies, or disruptions."""
    docs = retrieve_context(query=query, region=region, n_results=4)
    formatted = format_context_for_prompt(docs)
    return {
        "query": query,
        "retrieved_count": len(docs),
        "context_summary": formatted,
    }


def tool_create_approval_request(
    sku_id: str,
    warehouse_id: str,
    action_type: str,
    quantity: int,
    reason: str,
    source_warehouse_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Human-in-the-Loop approval item in the approvals queue.
    action_type: 'PURCHASE_ORDER' or 'WAREHOUSE_TRANSFER'
    """
    session = SessionLocal()
    try:
        approval = Approval(
            recommendation_type=action_type,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            action=action_type,
            quantity=quantity,
            ai_reasoning=reason,
            status="pending",
        )
        session.add(approval)
        session.commit()
        session.refresh(approval)
        return {
            "status": "SUCCESS",
            "approval_id": approval.id,
            "message": f"Proposal created successfully for {action_type} of {quantity} units (ID: {approval.id})",
        }
    except Exception as e:
        session.rollback()
        return {"status": "ERROR", "error": str(e)}
    finally:
        session.close()


# JSON schemas for OpenRouter / OpenAI function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Get statistical demand forecast for a SKU and warehouse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string", "description": "e.g. SKU_001"},
                    "warehouse_id": {"type": "string", "description": "e.g. WH_01"},
                    "horizon_days": {"type": "integer", "description": "Number of days ahead (default 30)"},
                },
                "required": ["sku_id", "warehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory",
            "description": "Get current stock levels, safety stock, and ROP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string", "description": "SKU identifier"},
                    "warehouse_id": {"type": "string", "description": "Warehouse identifier (optional)"},
                },
                "required": ["sku_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_replenishment_recommendation",
            "description": "Calculate safety stock, ROP, EOQ, and suggested order quantity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string"},
                    "warehouse_id": {"type": "string"},
                },
                "required": ["sku_id", "warehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_transfer_options",
            "description": "Find and evaluate inter-warehouse stock transfer opportunities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string"},
                    "deficit_warehouse_id": {"type": "string"},
                    "needed_quantity": {"type": "number"},
                },
                "required": ["sku_id", "deficit_warehouse_id", "needed_quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_whatif",
            "description": "Simulate what-if stress scenario (demand surges, supplier delays).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string"},
                    "warehouse_id": {"type": "string"},
                    "demand_shock_pct": {"type": "number", "description": "+20 for 20% spike"},
                    "lead_time_delay_days": {"type": "integer", "description": "Days delayed"},
                    "promo_lift_pct": {"type": "number"},
                },
                "required": ["sku_id", "warehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_rag_context",
            "description": "Search domain knowledge base for festival calendar, supplier terms, or disruptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"},
                    "region": {"type": "string", "description": "e.g. North, South, West"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_approval_request",
            "description": "Submit an order or transfer proposal to the human approval queue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_id": {"type": "string"},
                    "warehouse_id": {"type": "string"},
                    "action_type": {"type": "string", "enum": ["PURCHASE_ORDER", "WAREHOUSE_TRANSFER"]},
                    "quantity": {"type": "integer"},
                    "reason": {"type": "string"},
                    "source_warehouse_id": {"type": "string"},
                },
                "required": ["sku_id", "warehouse_id", "action_type", "quantity", "reason"],
            },
        },
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch tool execution by name."""
    if name == "get_forecast":
        return tool_get_forecast(
            sku_id=args["sku_id"],
            warehouse_id=args["warehouse_id"],
            horizon_days=args.get("horizon_days", 30),
        )
    elif name == "get_inventory":
        return tool_get_inventory(
            sku_id=args["sku_id"],
            warehouse_id=args.get("warehouse_id"),
        )
    elif name == "get_replenishment_recommendation":
        return tool_get_replenishment_recommendation(
            sku_id=args["sku_id"],
            warehouse_id=args["warehouse_id"],
        )
    elif name == "check_transfer_options":
        return tool_check_transfer_options(
            sku_id=args["sku_id"],
            deficit_warehouse_id=args["deficit_warehouse_id"],
            needed_quantity=float(args["needed_quantity"]),
        )
    elif name == "simulate_whatif":
        return tool_simulate_whatif(
            sku_id=args["sku_id"],
            warehouse_id=args["warehouse_id"],
            demand_shock_pct=float(args.get("demand_shock_pct", 0.0)),
            lead_time_delay_days=int(args.get("lead_time_delay_days", 0)),
            promo_lift_pct=float(args.get("promo_lift_pct", 0.0)),
        )
    elif name == "search_rag_context":
        return tool_search_rag_context(
            query=args["query"],
            region=args.get("region"),
        )
    elif name == "create_approval_request":
        return tool_create_approval_request(
            sku_id=args["sku_id"],
            warehouse_id=args["warehouse_id"],
            action_type=args["action_type"],
            quantity=int(args["quantity"]),
            reason=args["reason"],
            source_warehouse_id=args.get("source_warehouse_id"),
        )
    else:
        return {"error": f"Unknown tool name: {name}"}
