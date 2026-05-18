"""
Ingestion der eigenen Dokumente in PKC.
python ingest_meine_docs.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.ingestion.embedder import Embedder
from src.ingestion.pipeline import IngestionPipeline
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.postgres_client import PKCPostgresClient

embedder = Embedder()
qdrant   = PKCQdrantClient()
postgres = PKCPostgresClient()
pipeline = IngestionPipeline(embedder, qdrant, postgres)

QUELLEN = [
    {
        "pfad":  "/home/fatih-ubuntu/dev/timus/docs",
        "label": "timus_docs",
        "typ":   "verzeichnis",
    },
    {
        "pfad":  "/home/fatih-ubuntu/dev/timus/ARCHITECTURE.md",
        "label": "timus_architektur",
        "typ":   "datei",
    },
    {
        "pfad":  "/home/fatih-ubuntu/Downloads",
        "label": "downloads",
        "typ":   "verzeichnis",
    },
]

total = 0
for quelle in QUELLEN:
    pfad = Path(quelle["pfad"])
    if not pfad.exists():
        logger.warning(f"Pfad nicht gefunden, überspringe: {pfad}")
        continue

    if quelle["typ"] == "datei":
        chunks = pipeline.ingest_file(str(pfad), source_label=quelle["label"])
        total += len(chunks)
    else:
        n = pipeline.ingest_directory(str(pfad), extensions=[".md", ".txt", ".py"])
        total += n

print(f"\n✓ Fertig — {total} Chunks insgesamt indexiert.")
print(f"  Chunks im Index: {qdrant.count()}")
