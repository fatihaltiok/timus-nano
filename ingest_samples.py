"""
Beispieldokumente indexieren — einmalig ausführen.
python ingest_samples.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.embedder import Embedder
from src.ingestion.pipeline import IngestionPipeline
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.postgres_client import PKCPostgresClient

embedder = Embedder()
qdrant = PKCQdrantClient()
postgres = PKCPostgresClient()
pipeline = IngestionPipeline(embedder, qdrant, postgres)

total = pipeline.ingest_directory("data/sample_docs")
print(f"\n✓ {total} Chunks indexiert. PKC ist bereit.")
print(f"  Starte die UI mit: conda run -n pkc python ui.py")
