"""
Ingestion pipeline for RAG domain documents into ChromaDB.
Ingests festival calendar entries and contextual supply chain documents.

Usage:
    python -m src.rag.ingest
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.config import get_settings, PROJECT_ROOT
from src.rag.store import get_vector_store

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def load_festival_documents(festival_csv_path: Path) -> tuple[List[str], List[str], List[Dict[str, Any]]]:
    """Parse festival calendar CSV into indexed knowledge documents."""
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    if not festival_csv_path.exists():
        logger.warning(f"Festival calendar not found at: {festival_csv_path}")
        return ids, documents, metadatas

    df = pd.read_csv(festival_csv_path)
    for idx, row in df.iterrows():
        date_str = str(row.get("Date", "")).strip()
        name = str(row.get("Festival_Name", "")).strip()
        region = str(row.get("Primary_Region", "")).strip()
        notes = str(row.get("Notes", "")).strip()

        doc_id = f"FEST_{date_str.replace('-', '')}_{region}_{idx}"
        text_content = (
            f"Festival: {name}. Date: {date_str}. Primary Region: {region}. "
            f"Impact & Notes: {notes}."
        )

        ids.append(doc_id)
        documents.append(text_content)
        metadatas.append({
            "doc_id": doc_id,
            "type": "festival",
            "name": name,
            "date": date_str,
            "region": region,
            "source": "festival_calendar.csv",
        })

    logger.info(f"Prepared {len(ids)} festival calendar documents")
    return ids, documents, metadatas


def load_jsonl_documents(jsonl_path: Path) -> tuple[List[str], List[str], List[Dict[str, Any]]]:
    """Parse rag_documents.jsonl into indexed knowledge documents."""
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    if not jsonl_path.exists():
        logger.warning(f"RAG JSONL not found at: {jsonl_path}")
        return ids, documents, metadatas

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            doc_id = item.get("doc_id", f"DOC_{idx}")
            text_content = item.get("text", "")
            if not text_content:
                continue

            metadata = {
                "doc_id": doc_id,
                "type": item.get("type", "general"),
                "region": item.get("region", "All"),
                "date": item.get("date", ""),
                "sku_id": item.get("sku_id", ""),
                "warehouse_id": item.get("warehouse_id", ""),
                "source": "rag_documents.jsonl",
            }

            ids.append(doc_id)
            documents.append(text_content)
            metadatas.append(metadata)

    logger.info(f"Prepared {len(ids)} documents from rag_documents.jsonl")
    return ids, documents, metadatas


def run_rag_ingestion() -> int:
    """Run full RAG ingestion pipeline into ChromaDB."""
    settings = get_settings()
    data_dir = PROJECT_ROOT / "data"

    festival_path = data_dir / "rag_sources" / "festival_calendar.csv"
    if not festival_path.exists():
        festival_path = data_dir / "promotions_context" / "festival_calendar.csv"

    jsonl_path = data_dir / "rag_sources" / "rag_documents.jsonl"
    if not jsonl_path.exists():
        jsonl_path = data_dir / "promotions_context" / "rag_documents.jsonl"

    store = get_vector_store()
    total_added = 0

    # Ingest festivals
    f_ids, f_docs, f_metas = load_festival_documents(festival_path)
    if f_ids:
        total_added += store.add_documents(f_ids, f_docs, f_metas)

    # Ingest JSONL knowledge docs
    j_ids, j_docs, j_metas = load_jsonl_documents(jsonl_path)
    if j_ids:
        total_added += store.add_documents(j_ids, j_docs, j_metas)

    logger.info(f"RAG Ingestion Complete. Total ChromaDB documents: {store.count()}")
    return total_added


if __name__ == "__main__":
    run_rag_ingestion()
