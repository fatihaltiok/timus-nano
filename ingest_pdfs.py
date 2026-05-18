"""
PDF-Ingestion aus allen Quellen.
python ingest_pdfs.py
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
        "pfad":  "/run/user/1000/gvfs/smb-share:server=server.local,share=programmeundtools/Docs",
        "label": "netzlaufwerk_docs",
    },
    {
        "pfad":  "/home/fatih-ubuntu/Downloads",
        "label": "downloads_pdfs",
    },
    {
        "pfad":  "/home/fatih-ubuntu/Dokumente",
        "label": "dokumente",
    },
]

total = 0
for q in QUELLEN:
    pfad = Path(q["pfad"])
    if not pfad.exists():
        logger.warning(f"Nicht erreichbar, überspringe: {pfad}")
        continue
    pdfs = list(pfad.rglob("*.pdf"))
    logger.info(f"{len(pdfs)} PDFs gefunden in {pfad.name}")
    for pdf in pdfs:
        try:
            chunks = pipeline.ingest_file(str(pdf), source_label=q["label"] + "/" + pdf.stem)
            total += len(chunks)
        except Exception as e:
            logger.error(f"Fehler bei '{pdf.name}': {e}")

print(f"\n✓ {total} neue Chunks aus PDFs indexiert.")
print(f"  Gesamt im Index: {qdrant.count()}")
