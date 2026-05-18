"""
PKC Gradio-Interface — startet eine Browser-Oberfläche.
Start: python ui.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from loguru import logger

from src.ingestion.embedder import Embedder
from src.ingestion.pipeline import IngestionPipeline
from src.storage.qdrant_client import PKCQdrantClient
from src.storage.neo4j_client import PKCNeo4jClient
from src.storage.postgres_client import PKCPostgresClient
from src.retrieval.query_engine import QueryEngine

# Einmalig laden
logger.info("Lade PKC-Komponenten...")
embedder = Embedder()
qdrant = PKCQdrantClient()
neo4j = PKCNeo4jClient()
postgres = PKCPostgresClient()
query_engine = QueryEngine(embedder, qdrant, neo4j)
pipeline = IngestionPipeline(embedder, qdrant, postgres)
logger.success("PKC bereit.")


def suche(query: str, top_k: int, nur_typ: str):
    """Semantische Suche ausführen und Ergebnis formatieren."""
    if not query.strip():
        return "Bitte eine Frage eingeben.", ""

    chunk_type = nur_typ if nur_typ != "Alle" else None
    result = query_engine.search(query=query, top_k=top_k, chunk_type=chunk_type)

    if not result.chunks:
        return "Keine passenden Inhalte gefunden. Hast du schon Dokumente indexiert?", ""

    # Ergebnisse formatieren
    output_lines = [f"**{len(result.chunks)} Treffer** in {result.latency_ms:.0f}ms\n"]
    for i, chunk in enumerate(result.chunks, 1):
        score = chunk.metadata.get("score", 0)
        output_lines.append(f"---\n**#{i} | Quelle: `{chunk.source}` | Relevanz: {score:.0%}**\n")
        output_lines.append(chunk.content[:600])
        if len(chunk.content) > 600:
            output_lines.append("*(…)*")
        output_lines.append("")

    entities_text = ""
    if result.entities:
        entities_text = "**Verwandte Konzepte im Graph:**\n" + ", ".join(
            f"`{e.name}` ({e.entity_type})" for e in result.entities
        )

    return "\n".join(output_lines), entities_text


def datei_indexieren(datei_pfad: str, quelle: str):
    """Eine Datei in PKC indexieren."""
    if not datei_pfad.strip():
        return "Bitte einen Dateipfad eingeben."
    path = Path(datei_pfad.strip())
    if not path.exists():
        return f"Datei nicht gefunden: {datei_pfad}"
    try:
        chunks = pipeline.ingest_file(str(path), source_label=quelle.strip() or path.name)
        return f"Fertig! **{len(chunks)} Chunks** aus `{path.name}` indexiert."
    except Exception as e:
        return f"Fehler: {e}"


def ordner_indexieren(ordner_pfad: str):
    """Alle Dokumente in einem Ordner indexieren."""
    if not ordner_pfad.strip():
        return "Bitte einen Ordnerpfad eingeben."
    path = Path(ordner_pfad.strip())
    if not path.exists():
        return f"Ordner nicht gefunden: {ordner_pfad}"
    try:
        total = pipeline.ingest_directory(str(path))
        return f"Fertig! **{total} Chunks** aus `{path.name}/` indexiert."
    except Exception as e:
        return f"Fehler: {e}"


def system_status():
    """Aktuellen Stand des Systems anzeigen."""
    chunks = qdrant.count()
    entities = neo4j.count_entities()
    logs = postgres.get_ingestion_stats()
    status = f"""**PKC System-Status**

- Indexierte Chunks: **{chunks}**
- Entities im Graph: **{entities}**
- Letzte Indexierungen: **{len(logs)}**
"""
    if logs:
        status += "\n**Zuletzt indexiert:**\n"
        for log in logs[:5]:
            status += f"- `{log['source']}`: {log['chunks_count']} Chunks ({log['status']})\n"
    return status


# --- Gradio Interface ---
with gr.Blocks(title="PKC — Personal Knowledge Companion", theme=gr.themes.Soft()) as demo:

    gr.Markdown("# 🧠 Personal Knowledge Companion\nDein lokales KI-Gedächtnis")

    with gr.Tab("Suche"):
        gr.Markdown("### Wissen abfragen")
        with gr.Row():
            with gr.Column(scale=3):
                query_input = gr.Textbox(
                    label="Deine Frage",
                    placeholder="Was weißt du über RAG-Systeme?",
                    lines=2,
                )
            with gr.Column(scale=1):
                top_k = gr.Slider(1, 20, value=8, step=1, label="Anzahl Treffer")
                typ_filter = gr.Dropdown(
                    ["Alle", "note", "code", "article"],
                    value="Alle",
                    label="Typ-Filter",
                )
        search_btn = gr.Button("Suchen", variant="primary")
        results_output = gr.Markdown(label="Ergebnisse")
        entities_output = gr.Markdown(label="Graph-Verbindungen")

        search_btn.click(
            fn=suche,
            inputs=[query_input, top_k, typ_filter],
            outputs=[results_output, entities_output],
        )
        query_input.submit(
            fn=suche,
            inputs=[query_input, top_k, typ_filter],
            outputs=[results_output, entities_output],
        )

    with gr.Tab("Indexieren"):
        gr.Markdown("### Dokumente hinzufügen")

        with gr.Group():
            gr.Markdown("**Einzelne Datei indexieren**")
            with gr.Row():
                file_path_input = gr.Textbox(
                    label="Dateipfad",
                    placeholder="/home/fatih/meine_notizen.md",
                )
                source_label = gr.Textbox(
                    label="Quell-Label (optional)",
                    placeholder="lernnotizen_2024",
                )
            ingest_file_btn = gr.Button("Datei indexieren", variant="primary")
            file_result = gr.Markdown()
            ingest_file_btn.click(
                fn=datei_indexieren,
                inputs=[file_path_input, source_label],
                outputs=file_result,
            )

        with gr.Group():
            gr.Markdown("**Ganzen Ordner indexieren** (alle .md, .txt, .py Dateien)")
            dir_path_input = gr.Textbox(
                label="Ordnerpfad",
                placeholder="/home/fatih/meine_notizen/",
            )
            ingest_dir_btn = gr.Button("Ordner indexieren", variant="primary")
            dir_result = gr.Markdown()
            ingest_dir_btn.click(
                fn=ordner_indexieren,
                inputs=[dir_path_input],
                outputs=dir_result,
            )

    with gr.Tab("Status"):
        gr.Markdown("### System-Übersicht")
        status_btn = gr.Button("Status abrufen", variant="secondary")
        status_output = gr.Markdown()
        status_btn.click(fn=system_status, outputs=status_output)
        # Beim Tab-Laden direkt anzeigen
        demo.load(fn=system_status, outputs=status_output)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
