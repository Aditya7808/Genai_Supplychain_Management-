"""
FastAPI application — main entry point.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.config import get_settings
from src.database import get_session, init_db
from src.ingestion.models import (
    SalesHistory, InventoryLevel, SkuMaster, SupplierLeadtime,
    WarehouseMetadata, WarehouseDistance, Forecast, Approval, ActionLog,
)
from src.api.schemas import (
    HealthResponse, SkuResponse, WarehouseResponse, InventoryResponse,
    InventorySummary, ForecastRequest, ForecastResponse, ForecastPoint,
    ApprovalListItem, ApprovalAction, ApprovalResponse, ApprovalStatus, ApprovalCreate,
    DashboardSummary, ReplenishmentRecommendation, WhatIfRequest, WhatIfResponse,
    AnomalyAlert, ChatRequest, ChatResponse,
)

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ──
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    init_db()
    logger.info(f"{settings.app_name} started on port {settings.app_port}")
    yield


app = FastAPI(
    title=settings.app_name,
    description="GenAI-powered Inventory & Demand-Forecasting Assistant API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





# ══════════════════════════════════════════════════════════════
#  ROOT & HEALTH
# ══════════════════════════════════════════════════════════════

@app.get("/", tags=["System"])
def root():
    return {
        "app": settings.app_name,
        "status": "online",
        "docs_url": "/docs",
        "health_check": "/health",
        "frontend_url": "http://localhost:5173",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )


# ══════════════════════════════════════════════════════════════
#  SKU
# ══════════════════════════════════════════════════════════════

@app.get("/api/skus", response_model=List[SkuResponse], tags=["SKU"])
def list_skus(
    category: Optional[str] = None,
    session: Session = Depends(get_session),
):
    q = session.query(SkuMaster)
    if category:
        q = q.filter(SkuMaster.category == category)
    return [
        SkuResponse(
            sku_id=s.sku_id, description=s.description, category=s.category,
            unit_cost=s.unit_cost, unit_price=s.unit_price, margin_pct=s.margin_pct,
        )
        for s in q.order_by(SkuMaster.sku_id).all()
    ]


@app.get("/api/skus/{sku_id}", response_model=SkuResponse, tags=["SKU"])
def get_sku(sku_id: str, session: Session = Depends(get_session)):
    sku = session.query(SkuMaster).filter_by(sku_id=sku_id).first()
    if not sku:
        raise HTTPException(404, f"SKU {sku_id} not found")
    return SkuResponse(
        sku_id=sku.sku_id, description=sku.description, category=sku.category,
        unit_cost=sku.unit_cost, unit_price=sku.unit_price, margin_pct=sku.margin_pct,
    )


# ══════════════════════════════════════════════════════════════
#  WAREHOUSE
# ══════════════════════════════════════════════════════════════

@app.get("/api/warehouses", response_model=List[WarehouseResponse], tags=["Warehouse"])
def list_warehouses(session: Session = Depends(get_session)):
    return [
        WarehouseResponse(
            warehouse_id=w.warehouse_id, primary_region=w.primary_region,
            city=w.city, capacity_units=w.capacity_units,
            fixed_cost_per_day_inr=w.fixed_cost_per_day_inr,
        )
        for w in session.query(WarehouseMetadata).order_by(WarehouseMetadata.warehouse_id).all()
    ]


# ══════════════════════════════════════════════════════════════
#  INVENTORY
# ══════════════════════════════════════════════════════════════

@app.get("/api/inventory", response_model=List[InventorySummary], tags=["Inventory"])
def get_inventory_summary(
    sku_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Get latest inventory summary for each SKU-warehouse pair."""
    # Get the latest date for each sku-warehouse pair
    subq = (
        session.query(
            InventoryLevel.sku_id,
            InventoryLevel.warehouse_id,
            func.max(InventoryLevel.date).label("max_date"),
        )
        .group_by(InventoryLevel.sku_id, InventoryLevel.warehouse_id)
        .subquery()
    )

    q = (
        session.query(InventoryLevel)
        .join(subq, (
            (InventoryLevel.sku_id == subq.c.sku_id) &
            (InventoryLevel.warehouse_id == subq.c.warehouse_id) &
            (InventoryLevel.date == subq.c.max_date)
        ))
    )

    if sku_id:
        q = q.filter(InventoryLevel.sku_id == sku_id)
    if warehouse_id:
        q = q.filter(InventoryLevel.warehouse_id == warehouse_id)

    results = []
    for inv in q.all():
        # Calculate approximate days of stock
        avg_daily = (
            session.query(func.avg(SalesHistory.units_sold))
            .filter(SalesHistory.sku_id == inv.sku_id, SalesHistory.warehouse_id == inv.warehouse_id)
            .scalar() or 1
        )
        days = round(inv.on_hand / avg_daily, 1) if avg_daily > 0 else None

        # Determine risk level
        if inv.critical_stockout_flag:
            risk = "critical"
        elif inv.stockout_risk_flag or inv.stockout_flag:
            risk = "at_risk"
        else:
            risk = "healthy"

        results.append(InventorySummary(
            sku_id=inv.sku_id,
            warehouse_id=inv.warehouse_id,
            latest_on_hand=inv.on_hand,
            latest_on_order=inv.on_order,
            reorder_point=inv.reorder_point,
            days_of_stock=days,
            risk_level=risk,
        ))

    return sorted(results, key=lambda x: (x.risk_level != "critical", x.risk_level != "at_risk", x.sku_id))


@app.get("/api/inventory/{sku_id}/{warehouse_id}/history", response_model=List[InventoryResponse], tags=["Inventory"])
def get_inventory_history(
    sku_id: str,
    warehouse_id: str,
    limit: int = Query(default=90, le=365),
    session: Session = Depends(get_session),
):
    records = (
        session.query(InventoryLevel)
        .filter_by(sku_id=sku_id, warehouse_id=warehouse_id)
        .order_by(desc(InventoryLevel.date))
        .limit(limit)
        .all()
    )
    return [
        InventoryResponse(
            sku_id=r.sku_id, warehouse_id=r.warehouse_id, date=r.date,
            on_hand=r.on_hand, on_order=r.on_order, reorder_point=r.reorder_point,
            stockout_flag=r.stockout_flag, stockout_risk_flag=r.stockout_risk_flag,
            critical_stockout_flag=r.critical_stockout_flag,
        )
        for r in reversed(records)
    ]


# ══════════════════════════════════════════════════════════════
#  SALES HISTORY
# ══════════════════════════════════════════════════════════════

@app.get("/api/sales/{sku_id}/{warehouse_id}", tags=["Sales"])
def get_sales_history(
    sku_id: str,
    warehouse_id: str,
    limit: int = Query(default=365, le=1000),
    session: Session = Depends(get_session),
):
    records = (
        session.query(SalesHistory)
        .filter_by(sku_id=sku_id, warehouse_id=warehouse_id)
        .order_by(desc(SalesHistory.date))
        .limit(limit)
        .all()
    )
    return [
        {
            "date": r.date.isoformat(),
            "units_sold": r.units_sold,
            "promotion_flag": r.promotion_flag,
            "demand_forecast": r.demand_forecast,
        }
        for r in reversed(records)
    ]


# ══════════════════════════════════════════════════════════════
#  APPROVALS (Human-in-the-Loop)
# ══════════════════════════════════════════════════════════════

@app.get("/api/approvals", response_model=List[ApprovalListItem], tags=["Approvals"])
def list_approvals(
    status: Optional[ApprovalStatus] = None,
    session: Session = Depends(get_session),
):
    q = session.query(Approval)
    if status:
        q = q.filter(Approval.status == status.value)
    approvals = q.order_by(desc(Approval.created_at)).all()
    return [
        ApprovalListItem(
            id=a.id, recommendation_type=a.recommendation_type,
            sku_id=a.sku_id, warehouse_id=a.warehouse_id,
            action=a.action, quantity=a.quantity,
            ai_reasoning=a.ai_reasoning, ai_confidence=a.ai_confidence,
            status=a.status, created_at=a.created_at,
            reviewed_by=a.reviewed_by, reviewed_at=a.reviewed_at,
            edited_quantity=a.edited_quantity,
        )
        for a in approvals
    ]


@app.post("/api/approvals", response_model=ApprovalListItem, status_code=201, tags=["Approvals"])
def create_approval(
    body: ApprovalCreate,
    session: Session = Depends(get_session),
):
    approval = Approval(
        recommendation_type=body.recommendation_type,
        sku_id=body.sku_id,
        warehouse_id=body.warehouse_id,
        action=body.action,
        quantity=body.quantity,
        ai_reasoning=body.ai_reasoning,
        ai_confidence=body.ai_confidence or 0.95,
        status="pending",
    )
    session.add(approval)
    session.commit()
    session.refresh(approval)
    return ApprovalListItem(
        id=approval.id,
        recommendation_type=approval.recommendation_type,
        sku_id=approval.sku_id,
        warehouse_id=approval.warehouse_id,
        action=approval.action,
        quantity=approval.quantity,
        ai_reasoning=approval.ai_reasoning,
        ai_confidence=approval.ai_confidence,
        status=approval.status,
        created_at=approval.created_at,
        reviewed_by=approval.reviewed_by,
        reviewed_at=approval.reviewed_at,
        edited_quantity=approval.edited_quantity,
    )


@app.post("/api/approvals/{approval_id}/review", response_model=ApprovalResponse, tags=["Approvals"])
def review_approval(
    approval_id: int,
    body: ApprovalAction,
    session: Session = Depends(get_session),
):
    approval = session.query(Approval).filter_by(id=approval_id).first()
    if not approval:
        raise HTTPException(404, f"Approval {approval_id} not found")
    if approval.status != "pending":
        raise HTTPException(400, f"Approval {approval_id} already {approval.status}")

    approval.status = body.action.value
    approval.reviewed_by = body.reviewed_by
    approval.reviewed_at = datetime.now(timezone.utc)
    approval.edited_quantity = body.edited_quantity
    approval.review_notes = body.review_notes

    # If approved, log the action
    if body.action == ApprovalStatus.APPROVED:
        final_qty = body.edited_quantity if body.edited_quantity is not None else approval.quantity
        action_log = ActionLog(
            approval_id=approval.id,
            action_type=approval.action,
            sku_id=approval.sku_id,
            warehouse_id=approval.warehouse_id,
            final_quantity=final_qty,
            original_ai_quantity=approval.quantity,
            approved_by=body.reviewed_by,
            notes=body.review_notes,
        )
        session.add(action_log)

    session.commit()
    return ApprovalResponse(
        id=approval.id,
        status=approval.status,
        message=f"Approval {approval.id} {body.action.value}",
    )


# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════

@app.get("/api/dashboard", response_model=DashboardSummary, tags=["Dashboard"])
def get_dashboard(session: Session = Depends(get_session)):
    total_skus = session.query(func.count(SkuMaster.sku_id)).scalar() or 0
    total_warehouses = session.query(func.count(WarehouseMetadata.warehouse_id)).scalar() or 0
    pending_approvals = session.query(func.count(Approval.id)).filter(Approval.status == "pending").scalar() or 0

    # Count inventory alerts (stockout risk or critical)
    subq = (
        session.query(
            InventoryLevel.sku_id,
            InventoryLevel.warehouse_id,
            func.max(InventoryLevel.date).label("max_date"),
        )
        .group_by(InventoryLevel.sku_id, InventoryLevel.warehouse_id)
        .subquery()
    )
    alerts = (
        session.query(func.count())
        .select_from(InventoryLevel)
        .join(subq, (
            (InventoryLevel.sku_id == subq.c.sku_id) &
            (InventoryLevel.warehouse_id == subq.c.warehouse_id) &
            (InventoryLevel.date == subq.c.max_date)
        ))
        .filter((InventoryLevel.stockout_risk_flag == 1) | (InventoryLevel.critical_stockout_flag == 1))
        .scalar() or 0
    )

    # Get top risk SKUs
    risk_items = get_inventory_summary(session=session)
    top_risk = [r for r in risk_items if r.risk_level in ("critical", "at_risk")][:10]

    return DashboardSummary(
        total_skus=total_skus,
        total_warehouses=total_warehouses,
        total_alerts=alerts,
        pending_approvals=pending_approvals,
        avg_forecast_accuracy=None,  # Populated after Phase 2
        top_risk_skus=top_risk,
    )


# ══════════════════════════════════════════════════════════════
#  CATEGORIES (for filters)
# ══════════════════════════════════════════════════════════════

@app.get("/api/categories", tags=["SKU"])
def list_categories(session: Session = Depends(get_session)):
    cats = session.query(SkuMaster.category).distinct().all()
    return sorted([c[0] for c in cats])


# ══════════════════════════════════════════════════════════════
#  SUPPLIER LEAD TIMES
# ══════════════════════════════════════════════════════════════

@app.get("/api/leadtimes/{sku_id}", tags=["Supplier"])
def get_leadtimes(sku_id: str, session: Session = Depends(get_session)):
    records = session.query(SupplierLeadtime).filter_by(sku_id=sku_id).all()
    if not records:
        raise HTTPException(404, f"No lead time data for {sku_id}")
    return [
        {"supplier_id": r.supplier_id, "lead_time_days": r.lead_time_days}
        for r in records
    ]


# ══════════════════════════════════════════════════════════════
#  FORECASTING
# ══════════════════════════════════════════════════════════════

@app.post("/api/forecast", tags=["Forecasting"])
def create_forecast(body: ForecastRequest):
    from src.forecasting.service import generate_forecast
    try:
        model_str = body.model.value if hasattr(body.model, "value") else (body.model or "prophet").lower()
        res = generate_forecast(
            sku_id=body.sku_id,
            warehouse_id=body.warehouse_id,
            horizon_days=body.horizon_days,
            model_name=model_str,
        )
        return {
            "sku_id": res.sku_id,
            "warehouse_id": res.warehouse_id,
            "model_used": res.model_name,
            "horizon_days": res.horizon_days,
            "mape": res.metrics.mape if res.metrics else None,
            "rmse": res.metrics.rmse if res.metrics else None,
            "forecasts": [
                {
                    "date": p.date,
                    "point_forecast": p.predicted_demand,
                    "lower_bound": p.lower_bound,
                    "upper_bound": p.upper_bound,
                }
                for p in res.predictions
            ],
            "historical_points": res.historical_points,
        }
    except Exception as e:
        logger.error(f"Forecasting error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
#  REPLENISHMENT & TRANSFERS
# ══════════════════════════════════════════════════════════════

@app.get("/api/replenishment/alerts", tags=["Replenishment"])
def list_replenishment_alerts(limit: int = Query(default=50, le=200)):
    from src.replenishment.calculator import get_all_low_stock_alerts
    return get_all_low_stock_alerts(limit=limit)


@app.get("/api/replenishment/{sku_id}/{warehouse_id}", tags=["Replenishment"])
def get_replenishment_details(sku_id: str, warehouse_id: str):
    from src.replenishment.calculator import get_sku_replenishment_status
    return get_sku_replenishment_status(sku_id=sku_id, warehouse_id=warehouse_id)


@app.get("/api/transfers/{sku_id}/{warehouse_id}", tags=["Transfers"])
def get_transfer_options(sku_id: str, warehouse_id: str, quantity: float = Query(default=50.0)):
    from src.warehouse.transfer import find_transfer_opportunities
    return find_transfer_opportunities(
        target_sku_id=sku_id,
        deficit_warehouse_id=warehouse_id,
        needed_quantity=quantity,
    )


# ══════════════════════════════════════════════════════════════
#  WHAT-IF SIMULATION
# ══════════════════════════════════════════════════════════════

@app.post("/api/whatif", tags=["What-If"])
def run_whatif_scenario(body: dict):
    from src.whatif.simulation import simulate_scenario
    sku_id = body.get("sku_id", "SKU_001")
    warehouse_id = body.get("warehouse_id", "WH_01")
    demand_shock_pct = float(body.get("demand_shock_pct", body.get("demand_change_pct", 0.0) or 0.0))
    lead_time_delay_days = int(body.get("lead_time_delay_days", body.get("lead_time_change_days", 0) or 0))
    promo_lift_pct = float(body.get("promo_lift_pct", 25.0 if body.get("promotion_active") else 0.0))
    horizon_days = int(body.get("horizon_days", 30))

    return simulate_scenario(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        demand_shock_pct=demand_shock_pct,
        lead_time_delay_days=lead_time_delay_days,
        promo_lift_pct=promo_lift_pct,
        horizon_days=horizon_days,
    )


# ══════════════════════════════════════════════════════════════
#  ANOMALIES
# ══════════════════════════════════════════════════════════════

@app.get("/api/anomalies/{warehouse_id}", tags=["Anomalies"])
def get_anomalies(warehouse_id: str, limit: int = Query(default=20, le=100)):
    from src.anomaly.detector import scan_warehouse_anomalies
    return scan_warehouse_anomalies(warehouse_id=warehouse_id, limit=limit)


# ══════════════════════════════════════════════════════════════
#  RAG KNOWLEDGE SEARCH
# ══════════════════════════════════════════════════════════════

@app.get("/api/rag/search", tags=["RAG"])
def search_rag(query: str, region: Optional[str] = None, limit: int = Query(default=5, le=20)):
    from src.rag.retriever import retrieve_context
    return retrieve_context(query=query, region=region, n_results=limit)


# ══════════════════════════════════════════════════════════════
#  GENAI CHAT
# ══════════════════════════════════════════════════════════════

@app.post("/api/chat", tags=["Chat"])
def chat_endpoint(body: ChatRequest):
    from src.reasoning.agent import get_agent
    agent = get_agent()
    result = agent.run_conversation(
        messages=[{"role": "user", "content": body.message}],
        context_query=body.message,
    )
    return {
        "reply": result.get("content", ""),
        "conversation_id": body.conversation_id or "default-session",
        "model_used": result.get("model_used", "auto"),
        "tool_calls": result.get("tool_calls", []),
    }
