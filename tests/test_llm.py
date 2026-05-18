"""
LLM-Integrationstest: Gemma 4 + RAG-Pipeline.
python tests/test_llm.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()


def test_gemma_gpu():
    print("\n[1/3] Gemma 4 auf GPU laden...")
    import torch
    from src.llm.inference import GemmaInference

    assert torch.cuda.is_available(), "CUDA nicht verfügbar!"
    vram_vorher = torch.cuda.memory_allocated() / 1e9

    llm = GemmaInference()
    vram_nachher = torch.cuda.memory_allocated() / 1e9
    print(f"     OK - Modell geladen. VRAM: {vram_nachher:.1f} GB (+{vram_nachher - vram_vorher:.1f} GB)")
    return llm


def test_direkte_antwort(llm):
    print("\n[2/3] Direkte Antwort ohne Kontext...")
    antwort = llm.chat([
        {"role": "user", "content": "Was ist der Unterschied zwischen RAG und Fine-Tuning? Antworte in 3 Sätzen."}
    ])
    assert len(antwort) > 20
    print(f"     OK - Antwort ({len(antwort)} Zeichen):")
    print(f"     {antwort[:300]}...")


def test_rag_pipeline(llm):
    print("\n[3/3] Vollständige RAG-Pipeline mit eigenem Wissen...")
    from src.ingestion.embedder import Embedder
    from src.storage.qdrant_client import PKCQdrantClient
    from src.storage.neo4j_client import PKCNeo4jClient
    from src.retrieval.query_engine import QueryEngine

    engine = QueryEngine(
        embedder=Embedder(),
        qdrant=PKCQdrantClient(),
        neo4j=PKCNeo4jClient(),
        llm=llm,
    )

    frage = "Was ist die Architektur von Timus und welche Komponenten hat es?"
    print(f"     Frage: '{frage}'")

    result = engine.ask(frage, top_k=4)

    assert result.response
    assert len(result.chunks) > 0
    print(f"     OK - {len(result.chunks)} Quellen gefunden, Antwort generiert ({result.latency_ms:.0f}ms)")
    print(f"\n     --- ANTWORT ---")
    print(f"     {result.response}")
    print(f"     --- QUELLEN ---")
    for c in result.chunks[:3]:
        print(f"     - {c.source} (Score: {c.metadata.get('score', 0):.2f})")


if __name__ == "__main__":
    print("=" * 55)
    print("  PKC Woche 4 — LLM Integration Test")
    print("=" * 55)

    llm = test_gemma_gpu()
    test_direkte_antwort(llm)
    test_rag_pipeline(llm)

    print("\n" + "=" * 55)
    print("  Alle Tests bestanden.")
    print("=" * 55)
