"""
RAG Retriever for querying ChromaDB knowledge base.
Provides semantic search with metadata filtering and formatting for LLM prompt context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.rag.store import get_vector_store

logger = logging.getLogger(__name__)


def retrieve_context(
    query: str,
    n_results: int = 5,
    doc_type: Optional[str] = None,
    region: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    sku_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant domain context from ChromaDB.

    Args:
        query: Natural language query (e.g. "Diwali impact on Delhi warehouse")
        n_results: Max number of documents to return
        doc_type: Filter by type ("festival", "supplier", "disruption", "promotion")
        region: Filter by region ("North", "South", "East", "West", "Central")
        warehouse_id: Filter by warehouse ID (e.g. "WH_01")
        sku_id: Filter by SKU ID (e.g. "SKU_001")

    Returns:
        List of dicts with keys: id, text, metadata, distance
    """
    store = get_vector_store()

    # Build Chroma metadata filter
    where_clauses: List[Dict[str, Any]] = []
    if doc_type:
        where_clauses.append({"type": doc_type})
    if region:
        where_clauses.append({"region": region})
    if warehouse_id:
        where_clauses.append({"warehouse_id": warehouse_id})
    if sku_id:
        where_clauses.append({"sku_id": sku_id})

    where_filter: Optional[Dict[str, Any]] = None
    if len(where_clauses) == 1:
        where_filter = where_clauses[0]
    elif len(where_clauses) > 1:
        where_filter = {"$and": where_clauses}

    try:
        results = store.query(
            query_text=query,
            n_results=n_results,
            where=where_filter,
        )
    except Exception as e:
        logger.warning(f"Filtered query failed ({e}), falling back to unfiltered search")
        results = store.query(query_text=query, n_results=n_results)

    return results


def format_context_as_markdown(docs: List[Dict[str, Any]]) -> str:
    """
    Format retrieved knowledge documents into clean, structured executive Markdown (without emojis or square brackets).
    """
    if not docs:
        return "*No regional festival disruptions or active promotional campaigns registered for this SKU window.*"

    cards = []
    for doc in docs:
        meta = doc.get("metadata", {})
        doc_type = str(meta.get("type", "INSIGHT")).title()
        region = meta.get("region") or "National / Multi-Region"
        date_info = meta.get("date") or meta.get("period")
        text = doc.get("text", "").strip()

        cleaned_text = text
        if cleaned_text.startswith("Promotion Campaign: "):
            cleaned_text = cleaned_text[len("Promotion Campaign: "):]

        date_suffix = f" ({date_info})" if date_info else ""

        cards.append(
            f"- **{doc_type} Context - {region} Region{date_suffix}**\n"
            f"  {cleaned_text}"
        )

    return "\n\n".join(cards)


def format_context_for_prompt(docs: List[Dict[str, Any]]) -> str:
    """
    Format retrieved knowledge documents into a clear context block for LLM prompts and tools.
    """
    return format_context_as_markdown(docs)

