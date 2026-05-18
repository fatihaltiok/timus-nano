"""
Ingestion-Pipeline: Datei einlesen → Chunken → Embedden → Speichern.
"""
import uuid
from pathlib import Path
from typing import List
from loguru import logger

from src.models import KnowledgeChunk
from src.ingestion.parsers import parse_file
from src.ingestion.chunker import chunk_sections
from src.ingestion.embedder import Embedder
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.postgres_client import PKCPostgresClient


class IngestionPipeline:
    def __init__(
        self,
        embedder: Embedder,
        qdrant: PKCQdrantClient,
        postgres: PKCPostgresClient,
        chunk_size: int = 512,
        overlap: int = 64,
    ):
        self.embedder = embedder
        self.qdrant = qdrant
        self.postgres = postgres
        self.chunk_size = chunk_size
        self.overlap = overlap

    def ingest_file(self, file_path: str, source_label: str = "") -> List[KnowledgeChunk]:
        """Eine Datei vollständig verarbeiten und indexieren."""
        path = Path(file_path)
        source = source_label or path.name
        logger.info(f"Verarbeite: {path.name}")

        # 1. Parsen
        sections = parse_file(file_path)
        if not sections:
            logger.warning(f"Keine Inhalte in {path.name} gefunden.")
            return []

        # 2. Chunken
        chunks_raw = chunk_sections(sections, self.chunk_size, self.overlap)

        # 3. KnowledgeChunk-Objekte erstellen
        chunks: List[KnowledgeChunk] = []
        for text, meta in chunks_raw:
            if not text.strip():
                continue
            chunk = KnowledgeChunk(
                content=text,
                source=source,
                chunk_type=meta.get("type", "note"),
                metadata=meta,
            )
            chunks.append(chunk)

        if not chunks:
            logger.warning(f"Keine verwertbaren Chunks aus {path.name}.")
            return []

        # 4. Embeddings generieren (batch)
        texts = [c.content for c in chunks]
        logger.info(f"Generiere Embeddings für {len(texts)} Chunks...")
        embeddings = self.embedder.embed(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        # 5. In Qdrant speichern
        self.qdrant.upsert_chunks(chunks)

        # 6. Rohdokument in PostgreSQL speichern
        full_text = "\n\n".join(s[0] for s in sections)
        self.postgres.save_document(
            doc_id=str(uuid.uuid5(uuid.NAMESPACE_URL, file_path)),
            source=source,
            content=full_text,
            doc_type=chunks[0].chunk_type,
            file_path=str(path.absolute()),
            metadata={"chunks": len(chunks)},
        )
        self.postgres.log_ingestion(source=source, chunks_count=len(chunks), status="success")

        logger.success(f"Fertig: {len(chunks)} Chunks aus '{path.name}' indexiert.")
        return chunks

    def ingest_directory(self, dir_path: str, extensions: List[str] = None) -> int:
        """Alle Dateien in einem Verzeichnis ingesten."""
        extensions = extensions or [".md", ".txt", ".py", ".pdf"]
        path = Path(dir_path)
        files = [f for f in path.rglob("*") if f.suffix.lower() in extensions]
        logger.info(f"{len(files)} Dateien gefunden in {dir_path}")

        total = 0
        for f in files:
            try:
                chunks = self.ingest_file(str(f))
                total += len(chunks)
            except Exception as e:
                logger.error(f"Fehler bei {f.name}: {e}")
                self.postgres.log_ingestion(source=f.name, chunks_count=0, status="error", error=str(e))

        logger.success(f"Verzeichnis abgeschlossen: {total} Chunks total.")
        return total
