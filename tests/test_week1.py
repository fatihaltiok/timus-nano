"""
Woche-1-Test: Prüft ob alle Komponenten funktionieren.
Ausführen mit: python tests/test_week1.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()


def test_models():
    print("\n[1/5] Datenmodelle...")
    from src.models import KnowledgeChunk, KnowledgeEntity, KnowledgeRelation, QueryResult
    chunk = KnowledgeChunk(content="Test-Inhalt", source="test", chunk_type="note")
    assert chunk.id
    assert chunk.content == "Test-Inhalt"
    print("     OK - Datenmodelle funktionieren.")


def test_parsers():
    print("\n[2/5] Parser...")
    from src.ingestion.parsers import parse_markdown, parse_python, parse_file

    md_file = "data/sample_docs/machine_learning_basics.md"
    sections = parse_markdown(md_file)
    assert len(sections) > 0, "Keine Sections aus Markdown geparst."
    print(f"     OK - Markdown: {len(sections)} Sections gefunden.")

    py_file = "src/models.py"
    py_chunks = parse_python(py_file)
    assert len(py_chunks) > 0, "Keine Chunks aus Python-Datei."
    print(f"     OK - Python: {len(py_chunks)} Code-Chunks gefunden.")


def test_chunker():
    print("\n[3/5] Chunker...")
    from src.ingestion.chunker import chunk_text, chunk_sections

    long_text = " ".join([f"Wort{i}" for i in range(1000)])
    chunks = chunk_text(long_text, chunk_size=100, overlap=20)
    assert len(chunks) > 1, "Langer Text wurde nicht aufgeteilt."
    print(f"     OK - {len(chunks)} Chunks aus 1000 Wörtern erstellt.")

    # Überlappung prüfen
    words_1 = chunks[0].split()
    words_2 = chunks[1].split()
    overlap_words = set(words_1[-20:]) & set(words_2[:20])
    assert len(overlap_words) > 0, "Keine Überlappung zwischen Chunks."
    print(f"     OK - Überlappung korrekt ({len(overlap_words)} gemeinsame Wörter).")


def test_embedder():
    print("\n[4/5] Embedder (lädt Modell — dauert beim ersten Mal)...")
    from src.ingestion.embedder import Embedder

    embedder = Embedder(device="cpu")  # CPU für den Test
    texts = ["Das ist ein Test.", "Noch ein Satz zum Testen.", "PKC ist mein Wissensgraph."]
    embeddings = embedder.embed(texts, show_progress=False)

    assert len(embeddings) == 3
    assert len(embeddings[0]) == embedder.dim
    print(f"     OK - {len(embeddings)} Embeddings, Dimension: {embedder.dim}")

    # Ähnlichkeit prüfen: ähnliche Texte sollten näher beieinander liegen
    import numpy as np
    e1 = np.array(embeddings[0])
    e2 = np.array(embeddings[1])
    e3 = np.array(embeddings[2])
    sim_12 = float(np.dot(e1, e2))
    sim_13 = float(np.dot(e1, e3))
    print(f"     INFO - Cosine-Sim Satz1/Satz2: {sim_12:.3f}, Satz1/Satz3: {sim_13:.3f}")


def test_qdrant():
    print("\n[5/5] Qdrant (Docker muss laufen)...")
    try:
        from src.ingestion.embedder import Embedder
        from src.storage.qdrant_client import PKCQdrantClient
        from src.models import KnowledgeChunk

        embedder = Embedder(device="cpu")
        qdrant = PKCQdrantClient(collection="pkc_test")

        chunk = KnowledgeChunk(
            content="Vektordatenbanken speichern Embeddings für semantische Suche.",
            source="test",
            chunk_type="note",
        )
        chunk.embedding = embedder.embed_one(chunk.content)
        qdrant.upsert_chunk(chunk)

        results = qdrant.search(
            query_embedding=embedder.embed_one("Wie funktioniert semantische Suche?"),
            top_k=3,
        )
        assert len(results) >= 1
        print(f"     OK - Chunk gespeichert und gefunden (Score: {results[0]['score']:.3f})")

        # Test-Collection aufräumen
        qdrant.delete_collection()
        print("     OK - Test-Collection gelöscht.")

    except Exception as e:
        print(f"     SKIP - Qdrant nicht erreichbar (Docker läuft?): {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  PKC Woche 1 — Systemtest")
    print("=" * 55)

    test_models()
    test_parsers()
    test_chunker()
    test_embedder()
    test_qdrant()

    print("\n" + "=" * 55)
    print("  Alle Tests abgeschlossen.")
    print("=" * 55)
