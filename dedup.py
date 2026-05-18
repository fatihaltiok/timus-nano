"""
Duplikate aus dem Index entfernen.
Chunks mit Cosine-Similarity > 0.97 gelten als Duplikate.
python dedup.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import numpy as np
from loguru import logger
from src.storage.qdrant_client import PKCQdrantClient

qdrant = PKCQdrantClient()

logger.info("Lade alle Chunks für Deduplication...")
chunks = []
offset = None
while True:
    results, next_offset = qdrant.client.scroll(
        collection_name=qdrant.collection,
        limit=500,
        offset=offset,
        with_payload=True,
        with_vectors=True,
    )
    chunks.extend(results)
    if next_offset is None:
        break
    offset = next_offset

logger.info(f"{len(chunks)} Chunks geladen.")

# Duplikate finden
to_delete = set()
THRESHOLD = 0.97

for i in range(len(chunks)):
    if chunks[i].id in to_delete:
        continue
    vec_i = np.array(chunks[i].vector)

    for j in range(i + 1, len(chunks)):
        if chunks[j].id in to_delete:
            continue
        # Nur gleiche Quelle vergleichen (spart Zeit)
        src_i = chunks[i].payload.get("source", "")
        src_j = chunks[j].payload.get("source", "")
        if src_i != src_j:
            continue

        vec_j = np.array(chunks[j].vector)
        sim = float(np.dot(vec_i, vec_j))
        if sim > THRESHOLD:
            to_delete.add(chunks[j].id)

logger.info(f"{len(to_delete)} Duplikate gefunden.")

if to_delete:
    ids = list(to_delete)
    # In Batches löschen
    batch = 100
    for i in range(0, len(ids), batch):
        qdrant.client.delete(
            collection_name=qdrant.collection,
            points_selector=ids[i:i+batch],
        )
    logger.success(f"{len(to_delete)} Duplikate entfernt.")
else:
    logger.info("Keine Duplikate gefunden.")

print(f"\n✓ Index bereinigt. Verbleibende Chunks: {qdrant.count()}")
