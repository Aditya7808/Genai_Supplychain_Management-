"""
Pydantic schemas for API request/response models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ──

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ForecastModel(str, Enum):
    PROPHET = "prophet"
    SARIMA = "sarima"
    HOLT_WINTERS = "holt_winters"
    AUTO = "auto"


# ── Health ──

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime


# ── SKU ──

class SkuResponse(BaseModel):
    sku_id: str
    description: Optional[str]
    category: str
    unit_cost: float
    unit_price: float
    margin_pct: Optional[float]


# ── Warehouse ──

class WarehouseResponse(BaseModel):
    warehouse_id: str
    primary_region: str
    city: str
    capacity_units: int
    fixed_cost_per_day_inr: float


# ── Inventory ──

class InventoryResponse(BaseModel):
    sku_id: str
    warehouse_id: str
    date: date
    on_hand: int
    on_order: int
    reorder_point: int
    stockout_flag: int
    stockout_risk_flag: int
    critical_stockout_flag: int


class InventorySummary(BaseModel):
    sku_id: str
    warehouse_id: str
    latest_on_hand: int
    latest_on_order: int
    reorder_point: int
    days_of_stock: Optional[float]
    risk_level: str  # "healthy", "at_risk", "critical"


# ── Forecast ──

class ForecastRequest(BaseModel):
    sku_id: str
    warehouse_id: str
    horizon_days: int = Field(default=30, ge=1, le=365)
    model: Optional[str] = "prophet"


class ForecastPoint(BaseModel):
    date: date
    point_forecast: float
    lower_bound: Optional[float]
    upper_bound: Optional[float]


class ForecastResponse(BaseModel):
    sku_id: str
    warehouse_id: str
    model_used: str
    horizon_days: int
    mape: Optional[float]
    rmse: Optional[float]
    forecasts: List[ForecastPoint]


# ── Replenishment ──

class ReplenishmentRecommendation(BaseModel):
    sku_id: str
    warehouse_id: str
    current_on_hand: int
    current_on_order: int
    forecasted_demand: float
    lead_time_days: int
    safety_stock: int
    reorder_quantity: int
    urgency: str  # "immediate", "upcoming", "adequate"
    reasoning: str


# ── What-If ──

class WhatIfRequest(BaseModel):
    sku_id: str
    warehouse_id: str
    demand_change_pct: Optional[float] = None  # e.g. +20 for 20% increase
    lead_time_change_days: Optional[int] = None
    promotion_active: Optional[bool] = None


class WhatIfResponse(BaseModel):
    sku_id: str
    warehouse_id: str
    scenario_description: str
    baseline_forecast: float
    adjusted_forecast: float
    baseline_reorder_qty: int
    adjusted_reorder_qty: int
    impact_summary: str


# ── Anomaly ──

class AnomalyAlert(BaseModel):
    sku_id: str
    warehouse_id: str
    date: date
    actual_demand: int
    forecasted_demand: float
    deviation_pct: float
    z_score: float
    severity: str  # "minor", "moderate", "severe"
    likely_causes: List[str]
    investigation_summary: str


# ── Chat ──

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ToolCallInfo(BaseModel):
    tool_name: str
    arguments: dict
    result_summary: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    tool_calls: List[ToolCallInfo] = []
    recommendation: Optional[RecommendationOutput] = None


class RecommendationOutput(BaseModel):
    """Structured recommendation from the GenAI reasoning layer."""
    action: str
    sku_id: str
    warehouse_id: str
    quantity: int
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    requires_approval: bool = True


# Fix forward reference
ChatResponse.model_rebuild()


# ── Approvals ──

class ApprovalListItem(BaseModel):
    id: int
    recommendation_type: str
    sku_id: str
    warehouse_id: str
    action: str
    quantity: int
    ai_reasoning: str
    ai_confidence: Optional[float]
    status: ApprovalStatus
    created_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    edited_quantity: Optional[int]


class ApprovalAction(BaseModel):
    action: ApprovalStatus  # approved or rejected
    reviewed_by: str = "manager"
    edited_quantity: Optional[int] = None
    review_notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: int
    status: ApprovalStatus
    message: str


class ApprovalCreate(BaseModel):
    recommendation_type: str = "WAREHOUSE_TRANSFER"
    sku_id: str
    warehouse_id: str
    action: str
    quantity: int
    ai_reasoning: str
    ai_confidence: Optional[float] = 0.95


# ── Dashboard ──

class DashboardSummary(BaseModel):
    total_skus: int
    total_warehouses: int
    total_alerts: int
    pending_approvals: int
    avg_forecast_accuracy: Optional[float]
    top_risk_skus: List[InventorySummary]
