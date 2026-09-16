"""
SQLAlchemy ORM models for the inventory database.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, Float, Date, DateTime, Boolean, Text,
    UniqueConstraint, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class SalesHistory(Base):
    """Daily sales records per SKU per warehouse."""
    __tablename__ = "sales_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=True)
    promotion_flag: Mapped[int] = mapped_column(Integer, default=0)
    demand_forecast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint("sku_id", "warehouse_id", "date", name="uq_sales_sku_wh_date"),
        Index("ix_sales_sku_wh", "sku_id", "warehouse_id"),
    )


class InventoryLevel(Base):
    """Inventory snapshot per SKU per warehouse per date."""
    __tablename__ = "inventory_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    on_order: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    stockout_flag: Mapped[int] = mapped_column(Integer, default=0)
    stockout_risk_flag: Mapped[int] = mapped_column(Integer, default=0)
    critical_stockout_flag: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("sku_id", "warehouse_id", "date", name="uq_inv_sku_wh_date"),
        Index("ix_inv_sku_wh", "sku_id", "warehouse_id"),
    )


class SkuMaster(Base):
    """SKU reference data."""
    __tablename__ = "sku_master"

    sku_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    margin_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class SupplierLeadtime(Base):
    """Supplier lead time per SKU-supplier pair."""
    __tablename__ = "supplier_leadtimes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("sku_id", "supplier_id", name="uq_leadtime_sku_sup"),
    )


class WarehouseMetadata(Base):
    """Warehouse reference data."""
    __tablename__ = "warehouse_metadata"

    warehouse_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    primary_region: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=False)
    fixed_cost_per_day_inr: Mapped[float] = mapped_column(Float, nullable=False)


class WarehouseDistance(Base):
    """Inter-warehouse distance matrix."""
    __tablename__ = "warehouse_distances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_warehouse: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    to_warehouse: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    transfer_cost_per_unit: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("from_warehouse", "to_warehouse", name="uq_wh_dist"),
    )


class Forecast(Base):
    """Generated demand forecasts."""
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    point_forecast: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_used: Mapped[str] = mapped_column(String(50), default="prophet")
    mape: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rmse: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("sku_id", "warehouse_id", "forecast_date", "model_used",
                         name="uq_forecast_sku_wh_date_model"),
        Index("ix_forecast_sku_wh", "sku_id", "warehouse_id"),
    )


class Approval(Base):
    """Human-in-the-loop approval records for AI recommendations."""
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending | approved | rejected
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    edited_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_approval_status", "status"),
    )


class ActionLog(Base):
    """Audit trail for approved/executed actions."""
    __tablename__ = "actions_taken"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(20), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(20), nullable=False)
    final_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    original_ai_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(100), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
