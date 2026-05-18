"""
Iterativer Recherche-Agent für PKC.
Recherchiert ein Thema in mehreren Runden und erstellt tiefe Berichte.
"""
import json
import datetime
import re
from pathlib import Path
from typing import Generator, List, Dict
from loguru import logger

from src.retrieval.web_search import search_and_fetch, format_web_context
from src.retrieval.query_engine import QueryEngine

TOKENS_PER_SECTION = 4096
TOKENS_SYNTHESIS   = 8192
TOKENS_PLAN        = 1024


def _clean(text: str) -> str:
    return re.sub(r'\n{4,}', '\n\n', (text or "").strip())


class ResearchAgent:
    def __init__(
        self,
        llm,
        query_engine: QueryEngine,
        pipeline,
        max_rounds: int = 5,
        reports_dir: str = "",
    ):
        self.llm = llm
        self.query_engine = query_engine
        self.pipeline = pipeline
        self.max_rounds = max_rounds
        self.reports_dir = Path(reports_dir) if reports_dir else Path(__file__).parents[2] / "reports"
        self.reports_dir.mkdir(exist_ok=True)

    def research(self, topic: str, use_web: bool = True) -> Generator[Dict, None, None]:
        """
        Iterative Tiefenrecherche — yieldet SSE-kompatible Status-Updates.
        """
        yield {"type": "status", "phase": "plan", "message": f"Erstelle Recherche-Plan für: {topic}"}

        # ── Runde 1: Plan ──────────────────────────────────────────────
        plan = self._create_plan(topic, use_web)
        subtopics = plan.get("subtopics", [topic])[:self.max_rounds]

        yield {
            "type": "plan",
            "topic": topic,
            "subtopics": subtopics,
            "message": f"Plan: {len(subtopics)} Subtopics identifiziert",
        }

        # ── Runden 2-N: Pro Subtopic ───────────────────────────────────
        sections: List[Dict] = []
        all_sources: List[str] = []

        for i, subtopic in enumerate(subtopics, 1):
            yield {
                "type": "status",
                "phase": f"section_{i}",
                "message": f"[{i}/{len(subtopics)}] Recherchiere: {subtopic}",
            }

            section = self._research_subtopic(subtopic, topic, use_web, prev_sections=sections)
            sections.append(section)
            all_sources.extend(section.get("sources", []))

            yield {
                "type": "section",
                "index": i,
                "subtopic": subtopic,
                "tokens": len(section["content"].split()),
                "message": f"Abschnitt {i} fertig (~{len(section['content'].split())} Wörter)",
            }

        # ── Finale Synthese ────────────────────────────────────────────
        yield {"type": "status", "phase": "synthesis", "message": "Synthesiere alle Abschnitte zum Gesamtbericht…"}

        report_body = self._synthesize(topic, sections, use_web)

        # ── Bericht zusammenbauen ──────────────────────────────────────
        now = datetime.datetime.now()
        unique_sources = list(dict.fromkeys(all_sources))

        header = (
            f"---\n"
            f"title: {topic}\n"
            f"created: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"subtopics: {len(subtopics)}\n"
            f"sources: {len(unique_sources)}\n"
            f"---\n\n"
        )
        source_section = "\n\n---\n## Quellen\n" + "\n".join(f"- {s}" for s in unique_sources)
        full_report = header + report_body.strip() + source_section

        # ── Speichern ──────────────────────────────────────────────────
        safe = re.sub(r'[^\w\-]', '_', topic.lower())[:60]
        filename = f"{now.strftime('%Y-%m-%d')}_{safe}_tiefenrecherche.md"
        filepath = self.reports_dir / filename
        filepath.write_text(full_report, encoding="utf-8")
        logger.success(f"Bericht gespeichert: {filepath} ({len(full_report)} Zeichen)")

        # ── In PKC indexieren ──────────────────────────────────────────
        if self.pipeline:
            try:
                self.pipeline.ingest_file(str(filepath), source_label=f"Tiefenrecherche: {topic}")
                logger.success(f"Bericht indexiert: {filename}")
            except Exception as e:
                logger.warning(f"Indexierung fehlgeschlagen: {e}")

        total_words = sum(len(s["content"].split()) for s in sections)
        yield {
            "type": "done",
            "filename": filename,
            "filepath": str(filepath),
            "total_words": total_words + len(report_body.split()),
            "sections": len(subtopics),
            "sources": len(unique_sources),
            "message": f"Fertig — {len(sections)} Abschnitte, ~{total_words:,} Wörter",
        }

    # ── Interne Methoden ───────────────────────────────────────────────

    def _create_plan(self, topic: str, use_web: bool) -> Dict:
        """Recherche-Plan erstellen: Subtopics identifizieren."""
        vault_result = self.query_engine.search(topic, top_k=5)
        vault_ctx = self.query_engine.format_context(vault_result, max_chunks=5)

        web_ctx = ""
        if use_web:
            web_results = search_and_fetch(topic, max_results=3)
            web_ctx = format_web_context(web_results, max_per_result=600)

        prompt = [
            {
                "role": "system",
                "content": (
                    "Du bist ein Recherche-Assistent. Erstelle einen strukturierten Recherche-Plan. "
                    "Antworte NUR mit einem JSON-Objekt, kein anderer Text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Thema: {topic}\n\n"
                    f"Verfügbarer Kontext:\n{vault_ctx[:1500]}\n\n"
                    f"{web_ctx[:1000]}\n\n"
                    f"Erstelle einen Recherche-Plan mit 3-5 Subtopics.\n"
                    f"Antworte mit diesem JSON:\n"
                    f'{{"subtopics": ["Subtopic 1", "Subtopic 2", "Subtopic 3"]}}'
                ),
            },
        ]

        raw = self.llm.chat(prompt, max_new_tokens=TOKENS_PLAN)
        try:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass

        # Fallback: Zeilen als Subtopics
        lines = [l.strip("- •*123456789. ") for l in raw.split("\n") if len(l.strip()) > 5]
        return {"subtopics": lines[:5] or [topic]}

    def _research_subtopic(
        self,
        subtopic: str,
        main_topic: str,
        use_web: bool,
        prev_sections: List[Dict] = None,
    ) -> Dict:
        """Einen Subtopic gründlich recherchieren."""
        # Vault-Suche mit kombiniertem Query
        query = f"{main_topic} {subtopic}"
        vault_result = self.query_engine.search(query, top_k=6)
        vault_ctx = self.query_engine.format_context(vault_result, max_chunks=6)

        # Web-Suche
        web_ctx = ""
        web_sources = []
        if use_web:
            web_results = search_and_fetch(subtopic, max_results=4)
            web_ctx = format_web_context(web_results, max_per_result=900)
            web_sources = [r["url"] for r in web_results if r.get("url")]

        # Kontext aus vorherigen Abschnitten (Kurzfassung)
        prev_ctx = ""
        if prev_sections:
            prev_summaries = "\n".join(
                f"- {s['subtopic']}: {s['content'][:300]}…"
                for s in prev_sections[-3:]
            )
            prev_ctx = f"\nBisherige Erkenntnisse:\n{prev_summaries}\n"

        sources = list(set(c.source for c in vault_result.chunks)) + web_sources

        prompt = [
            {
                "role": "system",
                "content": (
                    "Du bist PKC, ein tiefgründiger Wissensassistent. "
                    "Erstelle eine umfassende, detaillierte Analyse auf Deutsch. "
                    "Sei präzise, konkret und erschöpfend — kein Fülltext."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Hauptthema: {main_topic}\n"
                    f"Aktueller Abschnitt: {subtopic}\n\n"
                    f"Vault-Wissen:\n{vault_ctx}\n\n"
                    f"{web_ctx}\n"
                    f"{prev_ctx}\n"
                    f"Schreibe einen tiefen, detaillierten Abschnitt über '{subtopic}' "
                    f"im Kontext von '{main_topic}'. "
                    f"Verbinde mit bisherigen Erkenntnissen. Mindestens 600 Wörter."
                ),
            },
        ]

        content = _clean(self.llm.chat(prompt, max_new_tokens=TOKENS_PER_SECTION))
        return {"subtopic": subtopic, "content": content, "sources": sources}

    def _synthesize(self, topic: str, sections: List[Dict], use_web: bool) -> str:
        """Alle Abschnitte zum finalen Bericht synthetisieren."""
        sections_text = "\n\n".join(
            f"## {s['subtopic']}\n{s['content']}" for s in sections
        )

        # Aktueller Überblick via Web
        web_ctx = ""
        if use_web:
            web_results = search_and_fetch(f"{topic} overview current state", max_results=2)
            web_ctx = format_web_context(web_results, max_per_result=600)

        prompt = [
            {
                "role": "system",
                "content": (
                    "Du bist PKC. Erstelle einen professionellen, umfassenden Forschungsbericht auf Deutsch. "
                    "Struktur: Titel, Zusammenfassung, alle Abschnitte ausgebaut, Verbindungen, Fazit. "
                    "Kein Fülltext, maximale Informationsdichte."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"# Synthese-Auftrag: {topic}\n\n"
                    f"Folgende Tiefenanalysen liegen vor:\n\n{sections_text}\n\n"
                    f"{web_ctx}\n\n"
                    f"Erstelle den finalen Gesamtbericht:\n"
                    f"1. Fasse alle Erkenntnisse kohärent zusammen\n"
                    f"2. Hebe die wichtigsten Verbindungen zwischen den Abschnitten hervor\n"
                    f"3. Identifiziere offene Fragen und nächste Schritte\n"
                    f"4. Schreibe ein substanzielles Fazit\n\n"
                    f"Sei erschöpfend und präzise."
                ),
            },
        ]

        return _clean(self.llm.chat(prompt, max_new_tokens=TOKENS_SYNTHESIS))
