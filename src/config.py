"""
Application configuration using Pydantic BaseSettings.
Reads from .env file and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


# Project root = the directory containing this src/ folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central configuration for the GenAI Inventory Assistant."""

    # ── Database ──
    database_url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT / 'data' / 'inventory.db'}",
        alias="DATABASE_URL",
    )

    # ── OpenRouter (GenAI) ──
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free",
        alias="OPENROUTER_MODEL",
    )
    openrouter_fallback_models_raw: str = Field(
        default="openai/gpt-oss-20b:free,deepseek/deepseek-r1-distill:free,qwen/qwen3-32b:free",
        alias="OPENROUTER_FALLBACK_MODELS",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )

    @property
    def openrouter_fallback_models(self) -> List[str]:
        """Parse comma-separated fallback model IDs."""
        if not self.openrouter_fallback_models_raw:
            return []
        return [m.strip() for m in self.openrouter_fallback_models_raw.split(",") if m.strip()]

    @property
    def all_models(self) -> List[str]:
        """Primary model + fallback models in order."""
        return [self.openrouter_model] + self.openrouter_fallback_models

    # ── Vector DB (RAG) ──
    vector_db_type: str = Field(default="chroma", alias="VECTOR_DB_TYPE")
    vector_db_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "vector_store"),
        alias="VECTOR_DB_PATH",
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )

    # ── Data Paths ──
    raw_data_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "raw"),
        alias="RAW_DATA_PATH",
    )
    processed_data_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "processed"),
        alias="PROCESSED_DATA_PATH",
    )
    promotions_context_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "promotions_context"),
        alias="PROMOTIONS_CONTEXT_PATH",
    )

    # ── App Config ──
    app_name: str = Field(default="GenAI Inventory Assistant", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    # ── Forecasting ──
    default_forecast_horizon_days: int = Field(
        default=30, alias="DEFAULT_FORECAST_HORIZON_DAYS"
    )
    default_forecaster: str = Field(default="prophet", alias="DEFAULT_FORECASTER")
    safety_stock_multiplier: float = Field(
        default=1.5, alias="SAFETY_STOCK_MULTIPLIER"
    )

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
