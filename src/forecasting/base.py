"""
Base classes and data contracts for demand forecasting models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class ForecastPoint:
    """A single forecasted day."""
    date: str
    predicted_demand: float
    lower_bound: float
    upper_bound: float


@dataclass
class BacktestMetrics:
    """Accuracy metrics computed via out-of-time validation."""
    mape: float
    rmse: float
    mae: float
    bias: float
    sample_size: int

    def to_dict(self) -> Dict[str, float]:
        return {
            "mape": round(self.mape, 2),
            "rmse": round(self.rmse, 2),
            "mae": round(self.mae, 2),
            "bias": round(self.bias, 2),
            "sample_size": self.sample_size,
        }


@dataclass
class ForecastResult:
    """Complete forecast output for a SKU-Warehouse combination."""
    sku_id: str
    warehouse_id: str
    model_name: str
    horizon_days: int
    predictions: List[ForecastPoint]
    metrics: Optional[BacktestMetrics] = None
    historical_points: List[Dict[str, float]] = field(default_factory=list)

    @property
    def total_projected_demand(self) -> float:
        return sum(p.predicted_demand for p in self.predictions)

    @property
    def avg_daily_projected_demand(self) -> float:
        if not self.predictions:
            return 0.0
        return self.total_projected_demand / len(self.predictions)


def compute_metrics(actuals: np.ndarray, predictions: np.ndarray) -> BacktestMetrics:
    """Compute standard forecasting accuracy metrics."""
    actuals = np.asarray(actuals, dtype=float)
    predictions = np.asarray(predictions, dtype=float)

    mask = ~np.isnan(actuals) & ~np.isnan(predictions)
    act = actuals[mask]
    pred = predictions[mask]

    if len(act) == 0:
        return BacktestMetrics(mape=0.0, rmse=0.0, mae=0.0, bias=0.0, sample_size=0)

    mae = float(np.mean(np.abs(act - pred)))
    rmse = float(np.sqrt(np.mean((act - pred) ** 2)))
    bias = float(np.mean(pred - act))

    # MAPE: avoid zero-division by adding epsilon or filtering act > 0
    non_zero = act > 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs((act[non_zero] - pred[non_zero]) / act[non_zero])) * 100.0)
    else:
        mape = 0.0

    return BacktestMetrics(
        mape=round(mape, 2),
        rmse=round(rmse, 2),
        mae=round(mae, 2),
        bias=round(bias, 2),
        sample_size=len(act),
    )


class BaseForecaster(ABC):
    """Abstract interface for forecasting models."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def fit_predict(
        self,
        historical_df: pd.DataFrame,
        horizon_days: int = 30,
        sku_id: str = "",
        warehouse_id: str = "",
    ) -> ForecastResult:
        """
        Fit model on historical_df (expects columns: 'date' and 'quantity')
        and predict demand for the next horizon_days.
        """
        pass
