"""
ChromaDB vector store implementation for the GenAI Inventory Assistant.
Provides persistent storage, semantic embedding, and metadata-filtered retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import get_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "inventory_knowledge"


class ChromaVectorStore:
    """Wrapper around ChromaDB PersistentClient for inventory domain knowledge."""

    def __init__(self, persist_directory: Optional[str] = None):
        app_settings = get_settings()
        self.persist_dir = Path(persist_directory or app_settings.vector_db_path) / "chroma"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB client at: {self.persist_dir}")
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Supply chain, festival, supplier, and warehouse context"},
        )

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Upsert documents into the ChromaDB collection."""
        if not ids:
            return 0

        # Clean metadatas: Chroma requires int, float, str, or bool values
        cleaned_metadatas = []
        if metadatas:
            for m in metadatas:
                cleaned = {}
                for k, v in m.items():
                    if v is None:
                        continue
                    if isinstance(v, (str, int, float, bool)):
                        cleaned[k] = v
                    else:
                        cleaned[k] = str(v)
                cleaned_metadatas.append(cleaned)
        else:
            cleaned_metadatas = None

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=cleaned_metadatas,
        )
        logger.info(f"Upserted {len(ids)} documents into ChromaDB collection '{COLLECTION_NAME}'")
        return len(ids)

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the ChromaDB collection for nearest neighbors.
        Supports metadata filtering with `where`.
        """
        count = self.collection.count()
        if count == 0:
            logger.warning("ChromaDB collection is empty.")
            return []

        actual_n = min(n_results, count)
        results = self.collection.query(
            query_texts=[query_text],
            n_results=actual_n,
            where=where if where else None,
        )

        formatted: List[Dict[str, Any]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return formatted

        docs = results["documents"][0]
        ids = results["ids"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        for doc_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
            formatted.append({
                "id": doc_id,
                "text": doc_text,
                "metadata": meta,
                "distance": dist,
            })

        return formatted

    def count(self) -> int:
        """Return total document count in collection."""
        return self.collection.count()

    def reset(self) -> None:
        """Clear the collection."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Supply chain, festival, supplier, and warehouse context"},
        )


_store_instance: Optional[ChromaVectorStore] = None


def get_vector_store() -> ChromaVectorStore:
    """Singleton getter for ChromaVectorStore."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ChromaVectorStore()
    return _store_instance
