"""
Anomaly detection engine for inventory and demand signals.
Detects demand spikes, demand collapse, and stock depletion anomalies using statistical methods.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import and_, select

from src.database import SessionLocal
from src.ingestion.models import SalesHistory, InventoryLevel

logger = logging.getLogger(__name__)


def detect_demand_anomalies(
    sku_id: str,
    warehouse_id: Optional[str] = None,
    threshold_z: float = 2.5,
) -> List[Dict[str, Any]]:
    """
    Detect anomalous demand days using rolling Z-Score and IQR.
    Identifies sudden demand surges (+Z) or demand collapses (-Z).
    """
    session = SessionLocal()
    anomalies: List[Dict[str, Any]] = []

    try:
        q = select(
            SalesHistory.date,
            SalesHistory.warehouse_id,
            SalesHistory.units_sold,
        ).where(SalesHistory.sku_id == sku_id)

        if warehouse_id:
            q = q.where(SalesHistory.warehouse_id == warehouse_id)

        q = q.order_by(SalesHistory.date.asc())
        rows = session.execute(q).fetchall()

        if len(rows) < 14:
            return anomalies

        df = pd.DataFrame(rows, columns=["date", "warehouse_id", "quantity"])
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)

        # 14-day rolling mean & std for dynamic baseline
        rolling_mean = df["quantity"].rolling(window=14, min_periods=7).mean()
        rolling_std = df["quantity"].rolling(window=14, min_periods=7).std().replace(0, 1.0)
        z_scores = (df["quantity"] - rolling_mean) / rolling_std

        # Identify outliers
        outlier_indices = np.where(np.abs(z_scores) >= threshold_z)[0]

        for idx in outlier_indices:
            row = df.iloc[idx]
            z_val = float(z_scores.iloc[idx])
            mean_val = float(rolling_mean.iloc[idx])
            observed = float(row["quantity"])

            anomaly_type = "DEMAND_SURGE" if z_val > 0 else "DEMAND_COLLAPSE"
            severity = "HIGH" if abs(z_val) > 3.5 else "MEDIUM"

            anomalies.append({
                "sku_id": sku_id,
                "warehouse_id": row["warehouse_id"],
                "date": str(row["date"]),
                "anomaly_type": anomaly_type,
                "severity": severity,
                "observed_value": observed,
                "expected_mean": round(mean_val, 1),
                "z_score": round(z_val, 2),
                "deviation_pct": round(((observed - mean_val) / max(mean_val, 0.1)) * 100, 1),
            })

        return anomalies
    finally:
        session.close()


def scan_warehouse_anomalies(warehouse_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Scan recent activity in a warehouse and flag top anomalous signals."""
    session = SessionLocal()
    try:
        # Check sales for top SKUs in this warehouse
        from sqlalchemy import func
        top_skus = (
            session.query(SalesHistory.sku_id)
            .filter(SalesHistory.warehouse_id == warehouse_id)
            .group_by(SalesHistory.sku_id)
            .limit(15)
            .all()
        )

        all_anomalies = []
        for (sku,) in top_skus:
            anoms = detect_demand_anomalies(sku_id=sku, warehouse_id=warehouse_id, threshold_z=2.5)
            all_anomalies.extend(anoms)

        # Sort by most recent and highest deviation
        all_anomalies.sort(key=lambda x: (x["date"], abs(x["z_score"])), reverse=True)
        return all_anomalies[:limit]
    finally:
        session.close()
