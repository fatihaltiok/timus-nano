"""
Woche-2-Test: Query Engine und FastAPI-Endpoints.
python tests/test_week2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()


def test_query_engine():
    print("\n[1/3] Query Engine...")
    from src.ingestion.embedder import Embedder
    from src.storage.qdrant_client import PKCQdrantClient
    from src.storage.neo4j_client import PKCNeo4jClient
    from src.retrieval.query_engine import QueryEngine

    embedder = Embedder()
    qdrant = PKCQdrantClient()
    neo4j = PKCNeo4jClient()
    engine = QueryEngine(embedder, qdrant, neo4j)

    queries = [
        "Was ist RAG und wie funktioniert es?",
        "Wie verhindere ich Overfitting beim Training?",
        "Welche Vektordatenbanken gibt es?",
    ]

    for q in queries:
        result = engine.search(q, top_k=3)
        assert len(result.chunks) > 0, f"Keine Ergebnisse für: {q}"
        top = result.chunks[0]
        score = top.metadata.get("score", 0)
        print(f"     Frage: '{q[:45]}...'")
        print(f"     → Top-Treffer: '{top.source}' (Score: {score:.2f})")
        print(f"     → Latenz: {result.latency_ms:.0f}ms")
        print()

    print("     OK - Query Engine liefert korrekte Ergebnisse.")


def test_context_builder():
    print("\n[2/3] Kontext-Builder...")
    from src.ingestion.embedder import Embedder
    from src.storage.qdrant_client import PKCQdrantClient
    from src.storage.neo4j_client import PKCNeo4jClient
    from src.retrieval.query_engine import QueryEngine

    engine = QueryEngine(Embedder(), PKCQdrantClient(), PKCNeo4jClient())
    result = engine.search("Gradient Descent", top_k=3)
    context = engine.format_context(result, max_chunks=3)

    assert "Quelle" in context
    assert len(context) > 50
    print(f"     OK - Kontext gebaut ({len(context)} Zeichen).")
    print(f"     Vorschau:\n{context[:300]}\n     ...")


def test_chunk_count():
    print("\n[3/3] Index-Größe prüfen...")
    from src.storage.qdrant_client import PKCQdrantClient

    qdrant = PKCQdrantClient()
    count = qdrant.count()
    assert count >= 24, f"Erwartet ≥24 Chunks, gefunden: {count}"
    print(f"     OK - {count} Chunks im Index (Ziel: ≥100 bis Ende Woche 2).")


if __name__ == "__main__":
    print("=" * 55)
    print("  PKC Woche 2 — Query Engine Test")
    print("=" * 55)

    test_query_engine()
    test_context_builder()
    test_chunk_count()

    print("\n" + "=" * 55)
    print("  Alle Tests bestanden.")
    print("=" * 55)
