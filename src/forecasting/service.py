"""
Forecasting service: coordinates data retrieval from DB, model execution,
result persistence, and metric logging.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.ingestion.models import SalesHistory, Forecast
from src.forecasting.base import ForecastResult
from src.forecasting.prophet_engine import ProphetForecaster
from src.forecasting.sarima_engine import SarimaForecaster

logger = logging.getLogger(__name__)

# Cached forecaster instances
_prophet_model: Optional[ProphetForecaster] = None
_sarima_model: Optional[SarimaForecaster] = None


def get_forecaster(model_name: str = "prophet"):
    """Get or instantiate the requested forecasting engine."""
    global _prophet_model, _sarima_model
    m_name = model_name.lower().strip()
    if m_name == "sarima":
        if _sarima_model is None:
            _sarima_model = SarimaForecaster()
        return _sarima_model
    else:
        if _prophet_model is None:
            _prophet_model = ProphetForecaster()
        return _prophet_model


def load_historical_sales_df(
    sku_id: str,
    warehouse_id: Optional[str] = None,
    session: Optional[Session] = None,
) -> pd.DataFrame:
    """Fetch daily sales timeseries for a given SKU and optional warehouse."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        query = select(
            SalesHistory.date,
            SalesHistory.units_sold.label("quantity"),
        ).where(SalesHistory.sku_id == sku_id)

        if warehouse_id:
            query = query.where(SalesHistory.warehouse_id == warehouse_id)

        query = query.order_by(SalesHistory.date.asc())
        results = session.execute(query).fetchall()

        if not results:
            return pd.DataFrame(columns=["date", "quantity"])

        df = pd.DataFrame(results, columns=["date", "quantity"])
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
        return df
    finally:
        if close_session:
            session.close()


def generate_forecast(
    sku_id: str,
    warehouse_id: str,
    horizon_days: int = 30,
    model_name: str = "prophet",
    save_to_db: bool = True,
) -> ForecastResult:
    """
    Generate demand forecast for a SKU and warehouse.
    Optionally saves the predicted points into the forecasts table.
    """
    df = load_historical_sales_df(sku_id=sku_id, warehouse_id=warehouse_id)
    forecaster = get_forecaster(model_name)

    logger.info(f"Fitting {model_name} for SKU={sku_id}, Warehouse={warehouse_id}, rows={len(df)}")
    result = forecaster.fit_predict(
        historical_df=df,
        horizon_days=horizon_days,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    if save_to_db and result.predictions:
        session = SessionLocal()
        try:
            today_date = date.today()
            # Remove previous forecasts for same sku, warehouse, and model created today
            session.query(Forecast).filter(
                and_(
                    Forecast.sku_id == sku_id,
                    Forecast.warehouse_id == warehouse_id,
                    Forecast.model_used == model_name,
                )
            ).delete()

            mape = result.metrics.mape if result.metrics else None
            rmse = result.metrics.rmse if result.metrics else None

            for pt in result.predictions:
                forecast_entry = Forecast(
                    sku_id=sku_id,
                    warehouse_id=warehouse_id,
                    forecast_date=datetime.strptime(pt.date, "%Y-%m-%d").date(),
                    point_forecast=pt.predicted_demand,
                    lower_bound=pt.lower_bound,
                    upper_bound=pt.upper_bound,
                    model_used=model_name,
                    mape=mape,
                    rmse=rmse,
                )
                session.add(forecast_entry)
            session.commit()
            logger.info(f"Saved {len(result.predictions)} forecast points to database")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save forecast to database: {e}")
        finally:
            session.close()

    return result
