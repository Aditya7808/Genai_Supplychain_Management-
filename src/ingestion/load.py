"""
Data loaders for the GenAI Inventory Assistant.
Reads raw CSV files, normalizes, and upserts into SQLite via SQLAlchemy.

Usage:
    python -m src.ingestion.load              # load all data
    python -m src.ingestion.load --only sales  # load only sales
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from src.config import get_settings, PROJECT_ROOT
from src.database import engine, init_db, SessionLocal
from src.ingestion.models import (
    SalesHistory, InventoryLevel, SkuMaster, SupplierLeadtime,
    WarehouseMetadata, WarehouseDistance
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ── Source file paths (checks project data folder first, then fallback) ──
LOCAL_DATA_DIR = PROJECT_ROOT / "data"
FALLBACK_DATA_DIR = Path(r"c:\Users\91884\Gen_AI_Inventory_Assistance\data")
SOURCE_DIR = LOCAL_DATA_DIR if (LOCAL_DATA_DIR / "processed" / "supply_chain_dataset1_enriched.csv").exists() else FALLBACK_DATA_DIR

ENRICHED_CSV = SOURCE_DIR / "processed" / "supply_chain_dataset1_enriched.csv"
WAREHOUSE_META_CSV = SOURCE_DIR / "metadata" / "warehouse_metadata.csv"
WAREHOUSE_DIST_CSV = SOURCE_DIR / "metadata" / "warehouse_distance_km.csv"
WAREHOUSE_COST_CSV = SOURCE_DIR / "metadata" / "warehouse_transfer_cost_per_unit.csv"
FESTIVAL_CSV = SOURCE_DIR / "rag_sources" / "festival_calendar.csv"
RAG_JSONL = SOURCE_DIR / "rag_sources" / "rag_documents.jsonl"


def _auto_categorize_skus(df: pd.DataFrame) -> dict[str, str]:
    """
    Auto-generate SKU categories based on unit_price tiers.
    Returns a dict mapping SKU_ID -> category name.
    """
    sku_prices = df.groupby("SKU_ID")["Unit_Price"].median().sort_values()

    # Create 5 price-tier categories
    labels = ["Budget", "Economy", "Standard", "Premium", "Luxury"]
    try:
        sku_prices_cat = pd.qcut(sku_prices, q=5, labels=labels, duplicates="drop")
    except ValueError:
        # If not enough distinct values for 5 bins, use fewer
        n_unique = sku_prices.nunique()
        labels = labels[:min(n_unique, 5)]
        sku_prices_cat = pd.qcut(sku_prices, q=len(labels), labels=labels, duplicates="drop")

    return sku_prices_cat.to_dict()


def load_enriched_dataset() -> pd.DataFrame:
    """Load and return the enriched supply chain dataset."""
    logger.info(f"Loading enriched dataset from {ENRICHED_CSV}")
    df = pd.read_csv(ENRICHED_CSV, parse_dates=["Date"])
    logger.info(f"  Loaded {len(df):,} rows | {df['SKU_ID'].nunique()} SKUs | {df['Warehouse_ID'].nunique()} warehouses")
    return df


def ingest_sku_master(df: pd.DataFrame, session):
    """Extract and upsert SKU master data from the enriched dataset."""
    logger.info("Ingesting SKU master...")

    categories = _auto_categorize_skus(df)

    sku_agg = df.groupby("SKU_ID").agg(
        unit_cost=("Unit_Cost", "median"),
        unit_price=("Unit_Price", "median"),
    ).reset_index()

    count = 0
    for _, row in sku_agg.iterrows():
        sku_id = row["SKU_ID"]
        unit_cost = float(row["unit_cost"])
        unit_price = float(row["unit_price"])
        margin = ((unit_price - unit_cost) / unit_price * 100) if unit_price > 0 else 0
        category = categories.get(sku_id, "Standard")

        stmt = sqlite_upsert(SkuMaster).values(
            sku_id=sku_id,
            description=f"SKU {sku_id.replace('SKU_', '')} - {category}",
            category=str(category),
            unit_cost=round(unit_cost, 2),
            unit_price=round(unit_price, 2),
            margin_pct=round(margin, 1),
        ).on_conflict_do_update(
            index_elements=["sku_id"],
            set_=dict(
                category=str(category),
                unit_cost=round(unit_cost, 2),
                unit_price=round(unit_price, 2),
                margin_pct=round(margin, 1),
            )
        )
        session.execute(stmt)
        count += 1

    session.commit()
    logger.info(f"  Upserted {count} SKUs into sku_master")


def ingest_supplier_leadtimes(df: pd.DataFrame, session):
    """Extract and upsert supplier lead times from the enriched dataset."""
    logger.info("Ingesting supplier lead times...")

    lt_agg = df.groupby(["SKU_ID", "Supplier_ID"]).agg(
        lead_time_days=("Supplier_Lead_Time_Days", "median")
    ).reset_index()

    count = 0
    for _, row in lt_agg.iterrows():
        # Check if exists
        existing = session.query(SupplierLeadtime).filter_by(
            sku_id=row["SKU_ID"], supplier_id=row["Supplier_ID"]
        ).first()

        if existing:
            existing.lead_time_days = int(row["lead_time_days"])
        else:
            session.add(SupplierLeadtime(
                sku_id=row["SKU_ID"],
                supplier_id=row["Supplier_ID"],
                lead_time_days=int(row["lead_time_days"]),
            ))
        count += 1

    session.commit()
    logger.info(f"  Upserted {count} supplier lead-time records")


def ingest_sales_history(df: pd.DataFrame, session):
    """Upsert sales history records."""
    logger.info("Ingesting sales history...")

    records = []
    for _, row in df.iterrows():
        records.append(dict(
            sku_id=row["SKU_ID"],
            warehouse_id=row["Warehouse_ID"],
            date=row["Date"].date() if isinstance(row["Date"], datetime) else row["Date"],
            units_sold=int(row["Units_Sold"]),
            unit_price=float(row["Unit_Price"]),
            promotion_flag=int(row["Promotion_Flag"]),
            demand_forecast=float(row["Demand_Forecast"]) if pd.notna(row["Demand_Forecast"]) else None,
            region=row.get("Region", None),
        ))

    # Batch upsert in chunks of 1000
    chunk_size = 1000
    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        for rec in chunk:
            stmt = sqlite_upsert(SalesHistory).values(**rec).on_conflict_do_update(
                index_elements=["sku_id", "warehouse_id", "date"],
                set_=dict(
                    units_sold=rec["units_sold"],
                    unit_price=rec["unit_price"],
                    promotion_flag=rec["promotion_flag"],
                    demand_forecast=rec["demand_forecast"],
                    region=rec["region"],
                )
            )
            session.execute(stmt)
        session.commit()
        total += len(chunk)
        if total % 10000 == 0:
            logger.info(f"  ... {total:,} / {len(records):,} sales records")

    logger.info(f"  Upserted {total:,} sales history records")


def ingest_inventory_levels(df: pd.DataFrame, session):
    """Upsert inventory level records."""
    logger.info("Ingesting inventory levels...")

    records = []
    for _, row in df.iterrows():
        records.append(dict(
            sku_id=row["SKU_ID"],
            warehouse_id=row["Warehouse_ID"],
            date=row["Date"].date() if isinstance(row["Date"], datetime) else row["Date"],
            on_hand=int(row["Inventory_Level"]),
            on_order=int(row["Order_Quantity"]),
            reorder_point=int(row["Reorder_Point"]),
            stockout_flag=int(row["Stockout_Flag"]),
            stockout_risk_flag=int(row.get("Stockout_Risk_Flag", 0)),
            critical_stockout_flag=int(row.get("Critical_Stockout_Flag", 0)),
        ))

    chunk_size = 1000
    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        for rec in chunk:
            stmt = sqlite_upsert(InventoryLevel).values(**rec).on_conflict_do_update(
                index_elements=["sku_id", "warehouse_id", "date"],
                set_=dict(
                    on_hand=rec["on_hand"],
                    on_order=rec["on_order"],
                    reorder_point=rec["reorder_point"],
                    stockout_flag=rec["stockout_flag"],
                    stockout_risk_flag=rec["stockout_risk_flag"],
                    critical_stockout_flag=rec["critical_stockout_flag"],
                )
            )
            session.execute(stmt)
        session.commit()
        total += len(chunk)
        if total % 10000 == 0:
            logger.info(f"  ... {total:,} / {len(records):,} inventory records")

    logger.info(f"  Upserted {total:,} inventory level records")


def ingest_warehouse_metadata(session):
    """Load warehouse metadata from CSV."""
    logger.info(f"Ingesting warehouse metadata from {WAREHOUSE_META_CSV}")
    df = pd.read_csv(WAREHOUSE_META_CSV)

    for _, row in df.iterrows():
        existing = session.query(WarehouseMetadata).filter_by(
            warehouse_id=row["Warehouse_ID"]
        ).first()

        if existing:
            existing.primary_region = row["Primary_Region"]
            existing.city = row["City"]
            existing.capacity_units = int(row["Capacity_Units"])
            existing.fixed_cost_per_day_inr = float(row["Fixed_Cost_Per_Day_INR"])
        else:
            session.add(WarehouseMetadata(
                warehouse_id=row["Warehouse_ID"],
                primary_region=row["Primary_Region"],
                city=row["City"],
                capacity_units=int(row["Capacity_Units"]),
                fixed_cost_per_day_inr=float(row["Fixed_Cost_Per_Day_INR"]),
            ))

    session.commit()
    logger.info(f"  Loaded {len(df)} warehouse records")


def ingest_warehouse_distances(session):
    """Load warehouse distance matrix and transfer costs."""
    logger.info("Ingesting warehouse distances & transfer costs...")

    dist_df = pd.read_csv(WAREHOUSE_DIST_CSV, index_col=0)
    cost_df = pd.read_csv(WAREHOUSE_COST_CSV, index_col=0)

    count = 0
    for from_wh in dist_df.index:
        for to_wh in dist_df.columns:
            distance = float(dist_df.loc[from_wh, to_wh])
            cost = float(cost_df.loc[from_wh, to_wh]) if from_wh in cost_df.index and to_wh in cost_df.columns else 0.0

            existing = session.query(WarehouseDistance).filter_by(
                from_warehouse=from_wh, to_warehouse=to_wh
            ).first()

            if existing:
                existing.distance_km = distance
                existing.transfer_cost_per_unit = cost
            else:
                session.add(WarehouseDistance(
                    from_warehouse=from_wh,
                    to_warehouse=to_wh,
                    distance_km=distance,
                    transfer_cost_per_unit=cost,
                ))
            count += 1

    session.commit()
    logger.info(f"  Loaded {count} distance/cost records")


def copy_rag_sources():
    """Copy RAG source files into the project's promotions_context directory."""
    settings = get_settings()
    dest = Path(settings.promotions_context_path)
    dest.mkdir(parents=True, exist_ok=True)

    import shutil
    for src_file in [FESTIVAL_CSV, RAG_JSONL]:
        if src_file.exists():
            dst_file = dest / src_file.name
            shutil.copy2(src_file, dst_file)
            logger.info(f"  Copied {src_file.name} -> {dst_file}")


def main():
    """Main ingestion CLI entry point."""
    parser = argparse.ArgumentParser(description="Load data into GenAI Inventory DB")
    parser.add_argument("--only", choices=["sales", "inventory", "sku", "supplier", "warehouse", "rag"],
                        help="Load only a specific dataset")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GenAI Inventory Assistant — Data Ingestion")
    logger.info("=" * 60)

    # Ensure data directories exist
    for d in ["data/raw", "data/processed", "data/promotions_context", "data/vector_store"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    init_db()
    logger.info("Database tables created/verified")

    # Load enriched dataset
    df = load_enriched_dataset()
    session = SessionLocal()

    try:
        if args.only is None or args.only == "sku":
            ingest_sku_master(df, session)
        if args.only is None or args.only == "supplier":
            ingest_supplier_leadtimes(df, session)
        if args.only is None or args.only == "sales":
            ingest_sales_history(df, session)
        if args.only is None or args.only == "inventory":
            ingest_inventory_levels(df, session)
        if args.only is None or args.only == "warehouse":
            ingest_warehouse_metadata(session)
            ingest_warehouse_distances(session)
        if args.only is None or args.only == "rag":
            copy_rag_sources()

        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Ingestion Summary:")
        for table_name in ["sku_master", "supplier_leadtimes", "sales_history",
                           "inventory_levels", "warehouse_metadata", "warehouse_distances"]:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            logger.info(f"  {table_name}: {count:,} rows")
        logger.info("=" * 60)

    finally:
        session.close()


if __name__ == "__main__":
    main()
