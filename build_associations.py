"""
Association Network aufbauen — einmalig oder nach großer Ingestion ausführen.
python build_associations.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.embedder import Embedder
from src.storage.neo4j_client import PKCNeo4jClient
from src.storage.qdrant_client import PKCQdrantClient
from src.retrieval.association import AssociationNetwork

embedder = Embedder()
neo4j    = PKCNeo4jClient()
qdrant   = PKCQdrantClient()

network = AssociationNetwork(neo4j, qdrant, embedder)
concepts, pairs = network.build_from_chunks()

print(f"\n✓ Association Network aufgebaut:")
print(f"  Konzepte: {concepts}")
print(f"  Assoziationspaare: {pairs}")
