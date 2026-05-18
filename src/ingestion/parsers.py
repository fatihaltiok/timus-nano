"""
Parser für verschiedene Dokumenttypen.
Gibt immer eine Liste von (text, metadata) Tupeln zurück.
"""
import re
import ast
from pathlib import Path
from typing import List, Tuple, Dict


def parse_markdown(file_path: str) -> List[Tuple[str, Dict]]:
    """Markdown-Datei in Abschnitte aufteilen (nach Überschriften)."""
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    sections = []
    current_heading = "intro"
    current_lines = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((content, {
                        "heading": current_heading,
                        "file": path.name,
                        "type": "note",
                    }))
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((content, {
                "heading": current_heading,
                "file": path.name,
                "type": "note",
            }))

    return sections


def parse_python(file_path: str) -> List[Tuple[str, Dict]]:
    """Python-Datei: Funktionen und Klassen als einzelne Chunks extrahieren."""
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    chunks = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Wenn parsen fehlschlägt, ganzes File als einen Chunk
        return [(source, {"file": path.name, "type": "code"})]

    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = node.end_lineno
            block = "\n".join(lines[start:end])
            docstring = ast.get_docstring(node) or ""
            chunks.append((block, {
                "file": path.name,
                "name": node.name,
                "type": "code",
                "docstring": docstring,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
            }))

    # Falls keine Funktionen/Klassen gefunden → ganzes File
    if not chunks:
        chunks.append((source, {"file": path.name, "type": "code"}))

    return chunks


def parse_text(file_path: str) -> List[Tuple[str, Dict]]:
    """Einfache Textdatei als einen Chunk."""
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    return [(text, {"file": path.name, "type": "article"})]


def parse_pdf(file_path: str) -> List[Tuple[str, Dict]]:
    """
    PDF seitenweise lesen. Jede Seite wird ein eigener Chunk.
    Leere oder sehr kurze Seiten (z.B. nur Bilder) werden übersprungen.
    """
    import fitz  # PyMuPDF
    path = Path(file_path)
    sections = []

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        return [(f"[PDF konnte nicht geöffnet werden: {e}]", {"file": path.name, "type": "article"})]

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        # Seiten mit weniger als 80 Zeichen überspringen (Bilder, Leerseiten)
        if len(text) < 80:
            continue
        # Zeilenumbrüche bereinigen
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        sections.append((text, {
            "file": path.name,
            "page": page_num,
            "total_pages": len(doc),
            "type": "article",
        }))

    doc.close()
    return sections


def parse_file(file_path: str) -> List[Tuple[str, Dict]]:
    """Automatisch den richtigen Parser anhand der Dateiendung wählen."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".md", ".markdown"):
        return parse_markdown(file_path)
    elif suffix == ".py":
        return parse_python(file_path)
    elif suffix in (".txt", ".rst"):
        return parse_text(file_path)
    elif suffix == ".pdf":
        return parse_pdf(file_path)
    else:
        return parse_text(file_path)
