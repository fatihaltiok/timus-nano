"""
PostgreSQL-Client: Rohdokumente und Audit-Logs speichern.
"""
import os
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

import psycopg2
from psycopg2.extras import RealDictCursor


class PKCPostgresClient:
    def __init__(self):
        self.conn_params = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "pkc"),
            "user": os.getenv("POSTGRES_USER", "pkc_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "pkc_password"),
        }
        self._create_tables()
        logger.info("PostgreSQL verbunden.")

    def _connect(self):
        return psycopg2.connect(**self.conn_params)

    def _create_tables(self):
        """Tabellen anlegen, falls nicht vorhanden."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id          TEXT PRIMARY KEY,
                        source      TEXT NOT NULL,
                        file_path   TEXT,
                        content     TEXT,
                        doc_type    TEXT,
                        ingested_at TIMESTAMP DEFAULT NOW(),
                        metadata    JSONB
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ingestion_log (
                        id          SERIAL PRIMARY KEY,
                        source      TEXT,
                        chunks_count INT,
                        status      TEXT,
                        error       TEXT,
                        created_at  TIMESTAMP DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS feedback (
                        id          SERIAL PRIMARY KEY,
                        query       TEXT NOT NULL,
                        response    TEXT,
                        rating      SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
                        comment     TEXT,
                        sources     JSONB,
                        created_at  TIMESTAMP DEFAULT NOW()
                    );
                """)
                conn.commit()

    def save_document(
        self,
        doc_id: str,
        source: str,
        content: str,
        doc_type: str,
        file_path: str = "",
        metadata: Dict = None,
    ):
        """Rohdokument speichern."""
        import json
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (id, source, file_path, content, doc_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata
                    """,
                    (doc_id, source, file_path, content, doc_type, json.dumps(metadata or {})),
                )
                conn.commit()

    def log_ingestion(self, source: str, chunks_count: int, status: str, error: str = ""):
        """Ingestion-Ergebnis protokollieren."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ingestion_log (source, chunks_count, status, error) VALUES (%s, %s, %s, %s)",
                    (source, chunks_count, status, error),
                )
                conn.commit()

    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Dokument anhand der ID abrufen."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def save_feedback(
        self,
        query: str,
        rating: int,
        response: str = "",
        comment: str = "",
        sources: List[str] = None,
    ):
        """Feedback speichern. rating: +1 = hilfreich, -1 = nicht hilfreich."""
        import json
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO feedback (query, response, rating, comment, sources) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (query, response, rating, comment, json.dumps(sources or [])),
                )
                conn.commit()

    def get_feedback_stats(self) -> Dict:
        """Feedback-Statistiken für Qualitätsanalyse."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN rating = 1  THEN 1 ELSE 0 END) AS positiv,
                        SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) AS negativ
                    FROM feedback
                """)
                row = cur.fetchone()
                total, positiv, negativ = row
                return {
                    "total": total,
                    "positiv": positiv,
                    "negativ": negativ,
                    "zufriedenheit": round(positiv / total * 100, 1) if total else 0,
                }

    def get_schlechte_queries(self, limit: int = 20) -> List[Dict]:
        """Queries die schlecht bewertet wurden — für manuelle Analyse."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT query, comment, created_at FROM feedback "
                    "WHERE rating = -1 ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_ingestion_stats(self) -> List[Dict]:
        """Letzte 50 Ingestion-Einträge."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM ingestion_log ORDER BY created_at DESC LIMIT 50"
                )
                return [dict(r) for r in cur.fetchall()]
