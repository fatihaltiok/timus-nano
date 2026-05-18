"""
Query Engine: kombiniert Vektorsuche (Qdrant) und Graph-Traversal (Neo4j).
Optional mit LLM für generierte Antworten.
"""
import time
from typing import List, Optional, TYPE_CHECKING
from loguru import logger

from src.models import KnowledgeChunk, KnowledgeEntity, QueryResult
from src.ingestion.embedder import Embedder
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.neo4j_client import PKCNeo4jClient

if TYPE_CHECKING:
    from src.llm.inference import GemmaInference
    from src.retrieval.association import SerendipityEngine


class QueryEngine:
    def __init__(
        self,
        embedder: Embedder,
        qdrant: PKCQdrantClient,
        neo4j: PKCNeo4jClient,
        llm: Optional["GemmaInference"] = None,
        serendipity: Optional["SerendipityEngine"] = None,
    ):
        self.llm = llm
        self.serendipity = serendipity
        self.embedder = embedder
        self.qdrant = qdrant
        self.neo4j = neo4j

    def ask(self, query: str, top_k: int = 5) -> QueryResult:
        """
        Vollständige RAG-Pipeline: Suche + LLM-Antwort.
        Benötigt ein geladenes LLM (self.llm).
        """
        from src.llm.prompts import build_rag_prompt

        result = self.search(query, top_k=top_k)
        if not self.llm:
            result.response = "(Kein LLM geladen — nur Retrieval-Ergebnisse)"
            return result

        context = self.format_context(result, max_chunks=top_k)
        messages = build_rag_prompt(query, context)

        logger.info("Generiere Antwort mit Gemma 4...")
        llm_start = time.time()
        result.response = self.llm.chat(messages)
        result.latency_ms += (time.time() - llm_start) * 1000
        logger.success(f"Antwort generiert ({result.latency_ms:.0f}ms gesamt)")
        return result

    def search(
        self,
        query: str,
        top_k: int = 8,
        chunk_type: Optional[str] = None,
    ) -> QueryResult:
        """
        Semantische Suche + Graph-Lookup kombiniert.
        Gibt ein QueryResult mit Chunks und verwandten Entities zurück.
        """
        start = time.time()

        # 1. Query embedden
        query_embedding = self.embedder.embed_one(query)

        # 2. Vektorsuche in Qdrant
        raw_results = self.qdrant.search(
            query_embedding=query_embedding,
            top_k=top_k,
            chunk_type=chunk_type,
        )

        # 3. Ergebnisse in KnowledgeChunk-Objekte umwandeln
        chunks = []
        sources = []
        for r in raw_results:
            chunk = KnowledgeChunk(
                id=r["id"],
                content=r.get("content", ""),
                source=r.get("source", ""),
                chunk_type=r.get("chunk_type", "note"),
                metadata={**r.get("metadata", {}), "score": r["score"]},
            )
            chunks.append(chunk)
            if chunk.source not in sources:
                sources.append(chunk.source)

        # 4. Graph: bekannte Entities zu den Sources suchen
        entities = self._find_related_entities(query)

        # 5. Serendipity: überraschende Verbindungen
        suggestions = []
        if self.serendipity:
            raw_chunks = [{"content": c.content, "source": c.source} for c in chunks]
            suggestions = self.serendipity.suggest(query, raw_chunks)

        latency = (time.time() - start) * 1000
        logger.info(f"Query '{query[:50]}' → {len(chunks)} Chunks, {len(suggestions)} Vorschläge ({latency:.0f}ms)")

        result = QueryResult(
            query=query,
            chunks=chunks,
            entities=entities,
            sources=sources,
            latency_ms=latency,
        )
        result.metadata = {"suggestions": suggestions}
        return result

    def _find_related_entities(self, query: str) -> List[KnowledgeEntity]:
        """Einfache Keyword-basierte Entity-Suche im Graph."""
        entities = []
        keywords = [w for w in query.split() if len(w) > 4]
        seen_ids = set()

        for keyword in keywords[:5]:
            entity_data = self.neo4j.find_entity_by_name(keyword)
            if entity_data and entity_data["id"] not in seen_ids:
                seen_ids.add(entity_data["id"])
                entities.append(KnowledgeEntity(
                    id=entity_data["id"],
                    name=entity_data["name"],
                    entity_type=entity_data.get("entity_type", "concept"),
                    description=entity_data.get("description", ""),
                    confidence=entity_data.get("confidence", 0.8),
                ))
        return entities

    def format_context(self, result: QueryResult, max_chunks: int = 5) -> str:
        """Kontext für das LLM aus den gefundenen Chunks zusammenbauen."""
        lines = []
        for i, chunk in enumerate(result.chunks[:max_chunks], 1):
            score = chunk.metadata.get("score", 0)
            lines.append(f"[Quelle {i}: {chunk.source} | Relevanz: {score:.2f}]")
            lines.append(chunk.content)
            lines.append("")
        return "\n".join(lines)
