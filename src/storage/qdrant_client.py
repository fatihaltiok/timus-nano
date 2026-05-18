"""
Qdrant-Client: Chunks speichern und per Vektorsuche abrufen.
"""
import os
from typing import List, Dict, Optional
from loguru import logger

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    ScoredPoint,
)

from src.models import KnowledgeChunk


class PKCQdrantClient:
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection: str = None,
        embedding_dim: int = None,
    ):
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = int(port or os.getenv("QDRANT_PORT", 6333))
        self.collection = collection or os.getenv("QDRANT_COLLECTION", "pkc_chunks")
        self.dim = int(embedding_dim or os.getenv("EMBEDDING_DIM", 384))

        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()

    def _ensure_collection(self):
        """Collection anlegen, falls sie nicht existiert."""
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant Collection '{self.collection}' erstellt.")
        else:
            logger.info(f"Qdrant Collection '{self.collection}' bereits vorhanden.")

    def upsert_chunk(self, chunk: KnowledgeChunk):
        """Einen Chunk in Qdrant speichern."""
        if not chunk.embedding:
            raise ValueError(f"Chunk {chunk.id} hat kein Embedding.")

        payload = chunk.to_dict()
        payload.pop("id")  # ID wird als Qdrant-Punkt-ID gesetzt

        self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=chunk.id,
                    vector=chunk.embedding,
                    payload=payload,
                )
            ],
        )

    def upsert_chunks(self, chunks: List[KnowledgeChunk], batch_size: int = 100):
        """Mehrere Chunks auf einmal speichern (schneller)."""
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            points = []
            for chunk in batch:
                if not chunk.embedding:
                    logger.warning(f"Chunk {chunk.id} übersprungen (kein Embedding).")
                    continue
                payload = chunk.to_dict()
                payload.pop("id")
                points.append(
                    PointStruct(id=chunk.id, vector=chunk.embedding, payload=payload)
                )
            if points:
                self.client.upsert(collection_name=self.collection, points=points)
        logger.info(f"{len(chunks)} Chunks in Qdrant gespeichert.")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        chunk_type: Optional[str] = None,
    ) -> List[Dict]:
        """Ähnlichkeitssuche. Gibt Liste von Dicts mit score und payload zurück."""
        query_filter = None
        if chunk_type:
            query_filter = Filter(
                must=[FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type))]
            )

        results: List[ScoredPoint] = self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {"id": str(r.id), "score": r.score, **r.payload}
            for r in results
        ]

    def count(self) -> int:
        """Anzahl der gespeicherten Chunks."""
        return self.client.count(collection_name=self.collection).count

    def delete_collection(self):
        """Collection löschen (für Tests)."""
        self.client.delete_collection(self.collection)
        logger.warning(f"Collection '{self.collection}' gelöscht.")
