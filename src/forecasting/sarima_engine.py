"""
Statistical forecasting engine using Exponential Smoothing / Holt-Winters and ARIMA.
Provides fast statistical baseline and fallback for Prophet.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.forecasting.base import (
    BaseForecaster,
    ForecastPoint,
    ForecastResult,
    BacktestMetrics,
    compute_metrics,
)

logger = logging.getLogger(__name__)


class SarimaForecaster(BaseForecaster):
    """Holt-Winters / Exponential Smoothing time-series forecaster."""

    def __init__(self):
        super().__init__(name="sarima")

    def fit_predict(
        self,
        historical_df: pd.DataFrame,
        horizon_days: int = 30,
        sku_id: str = "",
        warehouse_id: str = "",
    ) -> ForecastResult:
        df = historical_df.copy()
        date_col = "Date" if "Date" in df.columns else "date"
        qty_col = "Quantity" if "Quantity" in df.columns else "quantity"

        df["ds"] = pd.to_datetime(df[date_col])
        df["y"] = df[qty_col].astype(float)
        df = df.groupby("ds", as_index=False)["y"].sum().sort_values("ds")

        # Reindex to complete daily frequency filling missing with 0
        df = df.set_index("ds").asfreq("D", fill_value=0.0).reset_index()

        if len(df) < 14:
            mean_y = max(float(df["y"].mean() if len(df) > 0 else 1.0), 0.1)
            last_date = df["ds"].max() if len(df) > 0 else pd.to_datetime("today")
            points = [
                ForecastPoint(
                    date=(last_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                    predicted_demand=mean_y,
                    lower_bound=mean_y * 0.8,
                    upper_bound=mean_y * 1.2,
                )
                for i in range(1, horizon_days + 1)
            ]
            return ForecastResult(sku_id=sku_id, warehouse_id=warehouse_id, model_name="sarima", horizon_days=horizon_days, predictions=points)

        test_size = min(30, max(7, int(len(df) * 0.2)))
        train_df = df.iloc[:-test_size]
        test_df = df.iloc[-test_size:]

        # Backtest
        metrics: Optional[BacktestMetrics] = None
        try:
            seasonal_periods = 7 if len(train_df) >= 14 else None
            hw_model = ExponentialSmoothing(
                train_df["y"],
                trend="add" if len(train_df) >= 14 else None,
                seasonal="add" if seasonal_periods else None,
                seasonal_periods=seasonal_periods,
            ).fit(optimized=True)
            pred_bt = hw_model.forecast(test_size).clip(lower=0).values
            metrics = compute_metrics(test_df["y"].values, pred_bt)
        except Exception as e:
            logger.warning(f"SARIMA/HW backtest fit failed ({e})")

        # Full fit
        seasonal_periods = 7 if len(df) >= 14 else None
        try:
            model = ExponentialSmoothing(
                df["y"],
                trend="add" if len(df) >= 14 else None,
                seasonal="add" if seasonal_periods else None,
                seasonal_periods=seasonal_periods,
            ).fit(optimized=True)
            forecast_values = model.forecast(horizon_days).clip(lower=0).values
        except Exception as e:
            logger.warning(f"ExponentialSmoothing full fit failed ({e}), using rolling mean")
            forecast_values = np.full(horizon_days, max(df["y"].tail(14).mean(), 0.1))

        # Standard deviation for confidence interval
        residuals_std = float(np.std(df["y"].tail(30))) if len(df) >= 5 else 2.0
        last_date = df["ds"].max()
        points: List[ForecastPoint] = []
        for i, val in enumerate(forecast_values, 1):
            target_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
            pred = max(float(val), 0.0)
            points.append(
                ForecastPoint(
                    date=target_date,
                    predicted_demand=round(pred, 2),
                    lower_bound=round(max(pred - 1.96 * residuals_std, 0.0), 2),
                    upper_bound=round(pred + 1.96 * residuals_std, 2),
                )
            )

        recent_hist = df.tail(30)
        hist_points = [
            {"date": r["ds"].strftime("%Y-%m-%d"), "quantity": float(r["y"])}
            for _, r in recent_hist.iterrows()
        ]

        return ForecastResult(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            model_name="sarima",
            horizon_days=horizon_days,
            predictions=points,
            metrics=metrics,
            historical_points=hist_points,
        )
