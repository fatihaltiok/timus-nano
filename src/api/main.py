"""
FastAPI-Server für PKC.
Start: uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import tempfile, shutil, json, asyncio, re
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from src.ingestion.embedder import Embedder
from src.ingestion.pipeline import IngestionPipeline
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.neo4j_client import PKCNeo4jClient
from src.storage.postgres_client import PKCPostgresClient
from src.retrieval.query_engine import QueryEngine
from src.retrieval.association import SerendipityEngine
from src.retrieval.research_agent import ResearchAgent
from src.llm.inference import GemmaInference


# Globale Instanzen (werden beim Start geladen)
_embedder: Optional[Embedder] = None
_qdrant: Optional[PKCQdrantClient] = None
_neo4j: Optional[PKCNeo4jClient] = None
_postgres: Optional[PKCPostgresClient] = None
_query_engine: Optional[QueryEngine] = None
_pipeline: Optional[IngestionPipeline] = None
_serendipity = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _qdrant, _neo4j, _postgres, _query_engine, _pipeline
    logger.info("PKC startet — lade Komponenten...")

    _embedder = Embedder()
    _qdrant = PKCQdrantClient()
    _neo4j = PKCNeo4jClient()
    _postgres = PKCPostgresClient()
    _serendipity = SerendipityEngine(_neo4j, _embedder)
    llm = GemmaInference()
    _query_engine = QueryEngine(_embedder, _qdrant, _neo4j, llm=llm, serendipity=_serendipity)
    _pipeline = IngestionPipeline(_embedder, _qdrant, _postgres)

    logger.success("PKC bereit.")
    yield
    _neo4j.close()
    logger.info("PKC heruntergefahren.")


app = FastAPI(
    title="Personal Knowledge Companion",
    description="Dein lokales KI-Gedächtnis",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response-Modelle ---

class QueryRequest(BaseModel):
    query: str
    top_k: int = 8
    chunk_type: Optional[str] = None


class IngestPathRequest(BaseModel):
    path: str
    source_label: str = ""


class IngestDirectoryRequest(BaseModel):
    directory: str
    extensions: list[str] = [".md", ".txt", ".py"]


# --- Endpoints ---

@app.get("/")
def root():
    return {"status": "online", "service": "Personal Knowledge Companion"}


@app.get("/status")
def status():
    chunk_count = _qdrant.count() if _qdrant else 0
    entity_count = _neo4j.count_entities() if _neo4j else 0
    return {
        "status": "online",
        "chunks_indexed": chunk_count,
        "entities_in_graph": entity_count,
    }


@app.post("/query")
def query(req: QueryRequest):
    if not _query_engine:
        raise HTTPException(503, "Query Engine nicht bereit.")
    result = _query_engine.search(
        query=req.query,
        top_k=req.top_k,
        chunk_type=req.chunk_type,
    )
    return {
        "query": result.query,
        "latency_ms": round(result.latency_ms, 1),
        "sources": result.sources,
        "chunks": [
            {
                "content": c.content[:500],
                "source": c.source,
                "score": round(c.metadata.get("score", 0), 3),
                "type": c.chunk_type,
            }
            for c in result.chunks
        ],
        "entities": [
            {"name": e.name, "type": e.entity_type}
            for e in result.entities
        ],
    }


@app.post("/ingest/file")
def ingest_file(req: IngestPathRequest):
    if not _pipeline:
        raise HTTPException(503, "Pipeline nicht bereit.")
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(404, f"Datei nicht gefunden: {req.path}")
    chunks = _pipeline.ingest_file(str(path), source_label=req.source_label)
    return {"status": "ok", "chunks_added": len(chunks), "source": req.source_label or path.name}


@app.post("/ingest/directory")
def ingest_directory(req: IngestDirectoryRequest):
    if not _pipeline:
        raise HTTPException(503, "Pipeline nicht bereit.")
    path = Path(req.directory)
    if not path.exists():
        raise HTTPException(404, f"Verzeichnis nicht gefunden: {req.directory}")
    total = _pipeline.ingest_directory(str(path), extensions=req.extensions)
    return {"status": "ok", "chunks_added": total, "directory": req.directory}


class SuggestRequest(BaseModel):
    query: str
    top_n: int = 4


@app.post("/suggest")
def suggest(req: SuggestRequest):
    """Serendipity-Vorschläge: überraschende aber relevante Verbindungen zur Anfrage."""
    if not _query_engine or not _serendipity:
        raise HTTPException(503, "Serendipity Engine nicht bereit.")

    result = _query_engine.search(req.query, top_k=5)
    raw_chunks = [{"content": c.content, "source": c.source} for c in result.chunks]
    suggestions = _serendipity.suggest(req.query, raw_chunks, top_n=req.top_n)

    return {
        "query": req.query,
        "suggestions": suggestions,
        "message": "Das könnte dich auch interessieren:" if suggestions else "Noch keine Assoziationen — baue das Netzwerk mit build_associations.py auf.",
    }


class AskRequest(BaseModel):
    query: str
    top_k: int = 5
    history: list = []
    use_web: bool = True  # Web-Suche standardmäßig aktiv


@app.post("/ask")
def ask(req: AskRequest):
    """Vollständige RAG-Antwort mit LLM (blockierend)."""
    if not _query_engine:
        raise HTTPException(503, "Query Engine nicht bereit.")
    if not _query_engine.llm:
        raise HTTPException(503, "Kein LLM geladen.")
    result = _query_engine.ask(req.query, top_k=req.top_k)
    return {
        "query": result.query,
        "response": result.response,
        "sources": result.sources,
        "latency_ms": round(result.latency_ms, 1),
        "suggestions": result.metadata.get("suggestions", []),
    }



class FeedbackRequest(BaseModel):
    query: str
    rating: int         # +1 = hilfreich, -1 = nicht hilfreich
    response: str = ""
    comment: str = ""
    sources: list = []


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Feedback zu einer Antwort speichern."""
    if req.rating not in (1, -1):
        raise HTTPException(400, "rating muss +1 oder -1 sein.")
    _postgres.save_feedback(
        query=req.query,
        rating=req.rating,
        response=req.response,
        comment=req.comment,
        sources=req.sources,
    )
    return {"status": "gespeichert"}


@app.get("/feedback/stats")
def feedback_stats():
    """Feedback-Statistiken anzeigen."""
    stats = _postgres.get_feedback_stats()
    schlechte = _postgres.get_schlechte_queries(limit=10)
    return {"stats": stats, "schlechte_queries": schlechte}


class ReportRequest(BaseModel):
    topic: str
    history: list = []
    use_web: bool = True
    save_dir: str = ""


class ResearchRequest(BaseModel):
    topic: str
    use_web: bool = True
    max_rounds: int = 5


class SummarizeRequest(BaseModel):
    messages: list  # [{"role": "user"/"assistant", "content": "..."}]


@app.post("/report")
def create_report(req: ReportRequest):
    """
    Erstellt einen strukturierten Bericht zu einem Thema.
    Kombiniert Vault-Wissen + Web-Suche + Gesprächskontext.
    Speichert den Bericht als Markdown-Datei und indexiert ihn in PKC.
    """
    if not _query_engine or not _query_engine.llm:
        raise HTTPException(503, "LLM nicht bereit.")

    from src.llm.prompts import build_report_prompt
    from src.retrieval.web_search import search_and_fetch, format_web_context
    import datetime

    # 1. Vault-Suche
    result = _query_engine.search(req.topic, top_k=6)
    vault_context = _query_engine.format_context(result, max_chunks=6)

    # 2. Web-Suche
    web_context = ""
    web_sources = []
    if req.use_web:
        web_results = search_and_fetch(req.topic, max_results=4)
        web_context = format_web_context(web_results)
        web_sources = [r["url"] for r in web_results]

    # 3. Gesprächskontext
    history_text = ""
    if req.history:
        history_text = "\n".join(
            f"{'Nutzer' if m['role'] == 'user' else 'PKC'}: {m['content']}"
            for m in req.history[-8:]
            if m.get("content")
        )

    # 4. Bericht generieren
    prompt = build_report_prompt(req.topic, vault_context, web_context, history_text)
    report_text = _query_engine.llm.chat(prompt, max_new_tokens=16384, temperature=0.3)

    # 5. Metadaten-Header anhängen
    now = datetime.datetime.now()
    vault_sources = list(set(c.source for c in result.chunks))
    header = (
        f"---\n"
        f"title: {req.topic}\n"
        f"created: {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"vault_sources: {', '.join(vault_sources)}\n"
        f"web_sources: {', '.join(web_sources)}\n"
        f"---\n\n"
    )
    full_report = header + report_text.strip()

    # 6. Datei speichern
    reports_dir = Path(req.save_dir) if req.save_dir else Path(__file__).parents[2] / "reports"
    reports_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', req.topic.lower())[:60]
    filename = f"{now.strftime('%Y-%m-%d')}_{safe_name}.md"
    filepath = reports_dir / filename
    filepath.write_text(full_report, encoding="utf-8")
    logger.success(f"Bericht gespeichert: {filepath}")

    # 7. In PKC-Datenbank indexieren
    if _pipeline:
        try:
            _pipeline.ingest_file(str(filepath), source_label=f"Bericht: {req.topic}")
            logger.success(f"Bericht indexiert: {filename}")
        except Exception as e:
            logger.warning(f"Indexierung fehlgeschlagen: {e}")

    return {
        "status": "ok",
        "filename": filename,
        "filepath": str(filepath),
        "report": full_report,
        "web_sources": web_sources,
        "vault_sources": vault_sources,
    }


@app.post("/research/stream")
def research_stream(req: ResearchRequest):
    """
    Iterative Tiefenrecherche als SSE-Stream.
    Liefert Echtzeit-Status-Updates während der Agent arbeitet.
    """
    if not _query_engine or not _query_engine.llm:
        raise HTTPException(503, "LLM nicht bereit.")
    if not _pipeline:
        raise HTTPException(503, "Pipeline nicht bereit.")

    agent = ResearchAgent(
        llm=_query_engine.llm,
        query_engine=_query_engine,
        pipeline=_pipeline,
        max_rounds=req.max_rounds,
    )

    def sse():
        for event in agent.research(req.topic, use_web=req.use_web):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@app.post("/summarize")
def summarize_conversation(req: SummarizeRequest):
    """Erstellt eine detaillierte Zusammenfassung des bisherigen Gesprächsverlaufs."""
    if not _query_engine or not _query_engine.llm:
        raise HTTPException(503, "LLM nicht bereit.")
    if not req.messages:
        raise HTTPException(400, "Keine Nachrichten übergeben.")

    from src.llm.prompts import build_conversation_summary_prompt
    prompt = build_conversation_summary_prompt(req.messages)
    summary = _query_engine.llm.chat(prompt, max_new_tokens=4096)
    return {"summary": summary.strip()}


SUPPORTED_EXTENSIONS = {".md", ".txt", ".py", ".pdf", ".rst", ".markdown"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Datei hochladen und direkt in PKC indexieren."""
    if not _pipeline:
        raise HTTPException(503, "Pipeline nicht bereit.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Format '{suffix}' noch nicht unterstützt. "
            f"Unterstützt: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Temporäre Datei speichern
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        chunks = _pipeline.ingest_file(tmp_path, source_label=Path(file.filename).stem)
        return {
            "status": "ok",
            "dateiname": file.filename,
            "chunks_hinzugefuegt": len(chunks),
            "index_gesamt": _qdrant.count(),
        }
    except Exception as e:
        logger.error(f"Upload-Fehler bei {file.filename}: {e}")
        raise HTTPException(500, f"Fehler beim Indexieren: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/ask/stream")
def ask_stream_sse(req: AskRequest):
    """
    RAG-Antwort als Server-Sent Events Stream.
    Sendet zuerst die Quellen als Metadaten, dann die Tokens.
    """
    if not _query_engine or not _query_engine.llm:
        raise HTTPException(503, "LLM nicht bereit.")

    from src.llm.prompts import build_conversational_rag_prompt
    from src.retrieval.web_search import search_and_fetch, format_web_context, should_search

    # Query mit Gesprächskontext anreichern — besseres Retrieval
    enriched_query = req.query
    if req.history:
        recent = " ".join(m["content"] for m in req.history[-4:] if m.get("content"))
        enriched_query = f"{recent} {req.query}"

    result = _query_engine.search(enriched_query, top_k=req.top_k)
    context = _query_engine.format_context(result, max_chunks=req.top_k)

    # Web-Suche
    web_context = ""
    web_sources = []
    if req.use_web and should_search(req.query):
        web_results = search_and_fetch(req.query, max_results=3)
        web_context = format_web_context(web_results)
        web_sources = [{"source": r["title"], "url": r["url"], "web": True} for r in web_results]

    messages = build_conversational_rag_prompt(
        req.query, context, history=req.history, web_context=web_context
    )

    sources = [
        {"source": c.source, "score": round(c.metadata.get("score", 0), 3)}
        for c in result.chunks[:req.top_k]
    ] + web_sources
    suggestions = result.metadata.get("suggestions", [])

    def sse_generator():
        # Zuerst Metadaten senden
        meta = {"type": "meta", "sources": sources, "suggestions": suggestions}
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # Dann Tokens streamen
        for token in _query_engine.llm.chat_stream(messages):
            payload = {"type": "token", "text": token}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # Abschluss
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/stats")
def stats():
    logs = _postgres.get_ingestion_stats() if _postgres else []
    return {
        "total_chunks": _qdrant.count() if _qdrant else 0,
        "total_entities": _neo4j.count_entities() if _neo4j else 0,
        "recent_ingestions": logs[:10],
    }
