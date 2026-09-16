"""
Prophet demand forecasting engine.
Integrates festival calendar holidays, weekly/yearly seasonality, and uncertainty intervals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
from prophet import Prophet

from src.config import PROJECT_ROOT
from src.forecasting.base import (
    BaseForecaster,
    ForecastPoint,
    ForecastResult,
    BacktestMetrics,
    compute_metrics,
)

logger = logging.getLogger(__name__)


def _load_festival_holidays() -> Optional[pd.DataFrame]:
    """Load festival calendar as a Prophet holidays dataframe."""
    candidates = [
        PROJECT_ROOT / "data" / "rag_sources" / "festival_calendar.csv",
        PROJECT_ROOT / "data" / "promotions_context" / "festival_calendar.csv",
    ]
    for p in candidates:
        if p.exists():
            try:
                df = pd.read_csv(p)
                holidays_df = pd.DataFrame({
                    "holiday": df["Festival_Name"].astype(str),
                    "ds": pd.to_datetime(df["Date"]),
                    "lower_window": -1,
                    "upper_window": 2,
                })
                return holidays_df
            except Exception as e:
                logger.warning(f"Failed to load festivals for Prophet: {e}")
    return None


class ProphetForecaster(BaseForecaster):
    """Prophet-based demand forecasting model with festival holiday regressors."""

    def __init__(self):
        super().__init__(name="prophet")
        self.holidays = _load_festival_holidays()

    def fit_predict(
        self,
        historical_df: pd.DataFrame,
        horizon_days: int = 30,
        sku_id: str = "",
        warehouse_id: str = "",
    ) -> ForecastResult:
        """
        Fit Prophet on daily historical sales and predict horizon_days.
        Expects historical_df with columns ['date', 'quantity'] (or ['Date', 'Quantity']).
        """
        df = historical_df.copy()
        # Normalize column names
        date_col = "Date" if "Date" in df.columns else "date"
        qty_col = "Quantity" if "Quantity" in df.columns else "quantity"

        df["ds"] = pd.to_datetime(df[date_col])
        df["y"] = df[qty_col].astype(float)
        df = df.groupby("ds", as_index=False)["y"].sum().sort_values("ds")

        if len(df) < 5:
            # Not enough data for Prophet: fallback to naive moving average
            mean_y = max(float(df["y"].mean() if len(df) > 0 else 1.0), 0.1)
            last_date = df["ds"].max() if len(df) > 0 else pd.to_datetime("today")
            points = []
            for i in range(1, horizon_days + 1):
                d = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
                points.append(ForecastPoint(date=d, predicted_demand=mean_y, lower_bound=mean_y * 0.8, upper_bound=mean_y * 1.2))
            return ForecastResult(
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                model_name="naive_fallback",
                horizon_days=horizon_days,
                predictions=points,
            )

        # Backtest on last min(30, 20% of data) days
        test_size = min(30, max(5, int(len(df) * 0.2)))
        train_df = df.iloc[:-test_size]
        test_df = df.iloc[-test_size:]

        # Run backtest fit
        metrics: Optional[BacktestMetrics] = None
        try:
            m_bt = Prophet(
                holidays=self.holidays,
                weekly_seasonality=True,
                yearly_seasonality=len(train_df) > 180,
                daily_seasonality=False,
            )
            m_bt.fit(train_df)
            future_bt = m_bt.make_future_dataframe(periods=test_size, freq="D")
            forecast_bt = m_bt.predict(future_bt)
            pred_y = forecast_bt.iloc[-test_size:]["yhat"].clip(lower=0).values
            act_y = test_df["y"].values
            metrics = compute_metrics(act_y, pred_y)
        except Exception as e:
            logger.warning(f"Prophet backtest failed ({e}), continuing with full fit")

        # Full fit on all available data with fallback
        try:
            model = Prophet(
                holidays=self.holidays,
                weekly_seasonality=True,
                yearly_seasonality=len(df) > 180,
                daily_seasonality=False,
            )
            model.fit(df)
            future = model.make_future_dataframe(periods=horizon_days, freq="D")
            forecast = model.predict(future)
        except Exception as e:
            logger.warning(f"Prophet full fit failed ({e}). Falling back to statistical Exponential Smoothing / SARIMA engine.")
            from src.forecasting.sarima_engine import SarimaForecaster
            fallback_res = SarimaForecaster().fit_predict(
                historical_df=historical_df,
                horizon_days=horizon_days,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
            )
            fallback_res.model_name = "prophet (fallback: exponential smoothing)"
            return fallback_res

        future_rows = forecast.iloc[-horizon_days:]
        points: List[ForecastPoint] = []
        for _, row in future_rows.iterrows():
            d_str = row["ds"].strftime("%Y-%m-%d")
            pred = max(float(row["yhat"]), 0.0)
            y_lower = max(float(row["yhat_lower"]), 0.0)
            y_upper = max(float(row["yhat_upper"]), pred)

            points.append(
                ForecastPoint(
                    date=d_str,
                    predicted_demand=round(pred, 2),
                    lower_bound=round(y_lower, 2),
                    upper_bound=round(y_upper, 2),
                )
            )

        # Historical recent points (last 30 days) for visualization
        recent_hist = df.tail(30)
        hist_points = [
            {"date": r["ds"].strftime("%Y-%m-%d"), "quantity": float(r["y"])}
            for _, r in recent_hist.iterrows()
        ]

        return ForecastResult(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            model_name="prophet",
            horizon_days=horizon_days,
            predictions=points,
            metrics=metrics,
            historical_points=hist_points,
        )
