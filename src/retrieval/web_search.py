"""
Web-Suche und Seitenabruf für PKC.
Nutzt DuckDuckGo (kein API-Key nötig) + trafilatura für saubere Textextraktion.
"""
import re
import httpx
from typing import List, Dict
from loguru import logger

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo-search nicht installiert — Web-Suche deaktiviert.")

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

# Vertrauenswürdige Domains (Whitelist)
TRUSTED_DOMAINS = {
    "arxiv.org", "wikipedia.org", "github.com", "huggingface.co",
    "news.ycombinator.com", "developer.mozilla.org", "docs.python.org",
    "medium.com", "towardsdatascience.com", "openai.com", "anthropic.com",
    "deepmind.google", "research.google", "paperswithcode.com",
    "lobste.rs", "techcrunch.com", "theverge.com",
}

# Anfragen die KEINE Web-Suche brauchen (rein persönliches Wissen)
SKIP_WEB_PATTERNS = [
    r"\b(mein|meine|meiner|meinem|meinen)\b",
    r"\b(ich habe|ich hatte|ich will|erinnere|notiz)\b",
    r"\b(gestern|letzte woche|letzten monat)\b",
]


def should_search(query: str) -> bool:
    """
    Heuristik: Lohnt sich eine Web-Suche für diese Anfrage?
    Standard ist JA — nur bei rein persönlichen Fragen wird übersprungen.
    """
    q = query.lower()
    for pattern in SKIP_WEB_PATTERNS:
        if re.search(pattern, q):
            return False
    return True


def fetch_page(url: str, max_chars: int = 2500) -> str:
    """Seite fetchen und sauberen Text extrahieren."""
    try:
        r = httpx.get(
            url,
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "PKC/1.0 (personal knowledge assistant)"},
        )
        if not r.is_success:
            return ""

        if TRAFILATURA_AVAILABLE:
            text = trafilatura.extract(r.text, include_comments=False, include_tables=False)
            if text:
                return text[:max_chars]

        # Fallback: BeautifulSoup
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text[:max_chars]

    except Exception as e:
        logger.debug(f"Fetch fehlgeschlagen für {url}: {e}")
        return ""


def search_and_fetch(query: str, max_results: int = 4) -> List[Dict]:
    """
    DuckDuckGo-Suche + Seiteninhalte abrufen.
    Gibt Liste von {title, url, content, snippet} zurück.
    """
    if not DDGS_AVAILABLE:
        return []

    results = []
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=max_results * 2))

        for hit in hits:
            if len(results) >= max_results:
                break
            url = hit.get("href", "")
            title = hit.get("title", "")
            snippet = hit.get("body", "")

            content = fetch_page(url)
            if not content:
                content = snippet  # Fallback auf Snippet

            results.append({
                "title": title,
                "url": url,
                "content": content,
                "snippet": snippet,
            })
            logger.debug(f"Web: {title[:60]} ({url[:50]})")

    except Exception as e:
        logger.warning(f"Web-Suche fehlgeschlagen: {e}")

    logger.info(f"Web-Suche '{query[:50]}': {len(results)} Ergebnisse")
    return results


def format_web_context(results: List[Dict], max_per_result: int = 800) -> str:
    """Web-Ergebnisse als Kontext-String formatieren."""
    if not results:
        return ""
    lines = ["=== Aktuelle Web-Informationen ==="]
    for i, r in enumerate(results, 1):
        lines.append(f"\n[Web {i}: {r['title']} | {r['url']}]")
        content = r["content"] or r["snippet"]
        lines.append(content[:max_per_result])
    return "\n".join(lines)
