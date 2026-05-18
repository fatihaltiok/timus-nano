"""
PKC — Neue Dokumente hinzufügen.

Verwendung:
  python pkc_add.py /pfad/zu/ordner
  python pkc_add.py /pfad/zu/datei.pdf
  python pkc_add.py /pfad/zu/ordner1 /pfad/zu/ordner2
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
from src.storage.neo4j_client import PKCNeo4jClient
from src.retrieval.association import AssociationNetwork

if len(sys.argv) < 2:
    print("Verwendung: python pkc_add.py /pfad/zu/ordner_oder_datei")
    print("Beispiel:   python pkc_add.py ~/Downloads/neues_buch.pdf")
    sys.exit(1)

embedder = Embedder()
qdrant   = PKCQdrantClient()
postgres = PKCPostgresClient()
neo4j    = PKCNeo4jClient()
pipeline = IngestionPipeline(embedder, qdrant, postgres)

vorher = qdrant.count()
total  = 0

for arg in sys.argv[1:]:
    pfad = Path(arg).expanduser()
    if not pfad.exists():
        print(f"Nicht gefunden: {pfad}")
        continue

    if pfad.is_file():
        chunks = pipeline.ingest_file(str(pfad), source_label=pfad.stem)
        total += len(chunks)
    elif pfad.is_dir():
        total += pipeline.ingest_directory(str(pfad))
    else:
        print(f"Unbekannter Typ: {pfad}")

nachher = qdrant.count()
neu     = nachher - vorher

print(f"\n✓ {neu} neue Chunks hinzugefügt (gesamt: {nachher})")

if neu > 0:
    print("  Aktualisiere Association Network...")
    with neo4j.driver.session() as s:
        s.run("MATCH (c:Concept) DETACH DELETE c")
    network = AssociationNetwork(neo4j, qdrant, embedder)
    concepts, pairs = network.build_from_chunks()
    print(f"  Association Network: {concepts} Konzepte, {pairs} Assoziationen")

print("\nFertig. PKC kennt jetzt deine neuen Dokumente.")
