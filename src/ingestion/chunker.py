"""
Teilt langen Text in überlappende Chunks auf.
"""
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[str]:
    """
    Teilt Text in Chunks fester Wortanzahl mit Überlappung.
    chunk_size: maximale Wörter pro Chunk
    overlap: Wörter, die zwischen zwei aufeinanderfolgenden Chunks geteilt werden
    """
    words = text.split()
    if not words:
        return []

    # Text ist kurz genug → kein Aufteilen nötig
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap

    return chunks


def chunk_sections(
    sections: list,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list:
    """
    Nimmt geparste Sections [(text, metadata), ...] und chunked jede Section.
    Gibt [(chunk_text, metadata), ...] zurück.
    """
    result = []
    for text, metadata in sections:
        sub_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for i, chunk in enumerate(sub_chunks):
            meta = dict(metadata)
            meta["chunk_index"] = i
            meta["total_chunks"] = len(sub_chunks)
            result.append((chunk, meta))
    return result
