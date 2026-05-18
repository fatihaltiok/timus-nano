"""
Woche-5-Test: Association Network + Serendipity Engine.
python tests/test_week5.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()


def test_keyword_extraction():
    print("\n[1/3] Keyword-Extraktion...")
    from src.retrieval.association import extract_keywords

    text = "Die Architektur von Timus nutzt Multi-Agent-Orchestrierung und lokale Sprachmodelle für Inference."
    keywords = extract_keywords(text)
    assert len(keywords) > 3
    assert "timus" in keywords or "architektur" in keywords
    print(f"     OK - {len(keywords)} Keywords: {keywords[:8]}")


def test_association_network():
    print("\n[2/3] Association Network in Neo4j...")
    from src.storage.neo4j_client import PKCNeo4jClient
    neo4j = PKCNeo4jClient()

    with neo4j.driver.session() as session:
        result = session.run("MATCH (c:Concept) RETURN count(c) AS n")
        concept_count = result.single()["n"]

        result = session.run("MATCH ()-[r:ASSOCIATED_WITH]->() RETURN count(r) AS n")
        assoc_count = result.single()["n"]

    assert concept_count > 100, f"Zu wenige Konzepte: {concept_count}"
    assert assoc_count > 100, f"Zu wenige Assoziationen: {assoc_count}"
    print(f"     OK - {concept_count} Konzepte, {assoc_count} Assoziationen im Graph.")

    # Top-10 häufigste Konzepte
    with neo4j.driver.session() as session:
        result = session.run(
            "MATCH (c:Concept) RETURN c.name AS name, c.frequency AS freq "
            "ORDER BY freq DESC LIMIT 10"
        )
        top = [(r["name"], r["freq"]) for r in result]
    print(f"     Top-Konzepte: {top[:5]}")


def test_serendipity():
    print("\n[3/3] Serendipity Engine...")
    from src.ingestion.embedder import Embedder
    from src.storage.neo4j_client import PKCNeo4jClient
    from src.storage.qdrant_client import PKCQdrantClient
    from src.retrieval.association import SerendipityEngine
    from src.retrieval.query_engine import QueryEngine

    embedder = Embedder()
    neo4j = PKCNeo4jClient()
    qdrant = PKCQdrantClient()
    serendipity = SerendipityEngine(neo4j, embedder)
    engine = QueryEngine(embedder, qdrant, neo4j, serendipity=serendipity)

    fragen = [
        "Was ist die Speicherarchitektur von Timus?",
        "Wie funktioniert das Embedding-System?",
    ]

    for frage in fragen:
        result = engine.search(frage, top_k=4)
        suggestions = result.metadata.get("suggestions", [])
        print(f"\n     Frage: '{frage}'")
        print(f"     Gefundene Chunks: {len(result.chunks)}")
        if suggestions:
            print(f"     Serendipity-Vorschläge ({len(suggestions)}):")
            for s in suggestions:
                print(f"       - '{s['concept']}' (via '{s['connected_to']}', Stärke: {s['association_strength']})")
        else:
            print("     Keine Vorschläge (Netzwerk noch dünn oder Query zu spezifisch)")


if __name__ == "__main__":
    print("=" * 55)
    print("  PKC Woche 5 — Association Network & Serendipity")
    print("=" * 55)

    test_keyword_extraction()
    test_association_network()
    test_serendipity()

    print("\n" + "=" * 55)
    print("  Alle Tests abgeschlossen.")
    print("=" * 55)
