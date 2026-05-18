"""
Association Network: Co-Occurrence-Analyse und Serendipity-Engine.

Idee:
- Analysiert welche Konzepte häufig zusammen in Chunks vorkommen
- Speichert diese Assoziationen in Neo4j
- Serendipity: findet überraschende aber relevante Verbindungen zu einer Anfrage
"""
import re
from collections import defaultdict, Counter
from itertools import combinations
from typing import List, Dict, Tuple, Optional
from loguru import logger

from src.storage.neo4j_client import PKCNeo4jClient
from src.storage.qdrant_client import PKCQdrantClient
from src.ingestion.embedder import Embedder


# Deutsche + englische Stoppwörter
STOPWORDS = {
    # Deutsche Artikel, Pronomen, Präpositionen
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem",
    "einen", "eines", "und", "oder", "aber", "auch", "noch", "schon", "nur",
    "nicht", "kein", "keine", "keinen", "ist", "sind", "war", "waren", "wird",
    "werden", "wurde", "haben", "hat", "hatte", "sein", "ihre", "ihrer", "ihrem",
    "durch", "mit", "von", "aus", "bei", "nach", "über", "unter", "vor", "für",
    "auf", "an", "in", "zu", "wie", "als", "dass", "wenn", "weil", "damit",
    "alle", "beim", "ohne", "damit", "wobei", "sowie", "bzw", "sehr", "mehr",
    "einer", "eines", "dieses", "diesem", "diesen", "dieser", "dieses",
    "diese", "dieser", "diesem", "diesen", "jetzt", "dann", "hier", "dort",
    "kann", "koennen", "muss", "muessen", "soll", "sollen", "darf", "duerfen",
    "wird", "werden", "wurde", "wurden", "worden", "immer", "schon", "noch",
    "uber", "ueber", "fuer", "nach", "beim", "zum", "zur", "vom", "beim",
    "seit", "doch", "aber", "denn", "weil", "dass", "wenn", "damit", "zwar",
    "jedoch", "dabei", "hierbei", "somit", "daher", "deshalb", "deswegen",
    "erste", "zweite", "dritte", "erste", "letzt", "naechste", "folgende",
    "turn", "true", "false", "none", "null", "self", "class", "return",
    # Englische Füllwörter
    "this", "that", "with", "from", "have", "been", "will", "they", "their",
    "there", "what", "which", "when", "than", "then", "some", "into", "more",
    "also", "your", "each", "such", "these", "those", "about", "other", "after",
    "first", "where", "being", "between", "through", "during", "before",
    "would", "could", "should", "must", "that", "this", "with", "from",
    "just", "only", "very", "well", "even", "much", "many", "most", "both",
    # System/Pfad-Begriffe
    "home", "fatih", "ubuntu", "local", "localhost", "http", "https",
    "true", "false", "none", "null", "python", "import", "return", "class",
    "function", "variable", "string", "integer", "float", "bool", "list",
}


def extract_keywords(text: str, min_length: int = 4, max_keywords: int = 20) -> List[str]:
    """Bedeutungsvolle Keywords aus einem Text extrahieren."""
    words = re.findall(r'\b[a-zA-ZäöüÄÖÜß]{4,}\b', text)
    keywords = []
    seen = set()
    for w in words:
        w_lower = w.lower()
        if w_lower not in STOPWORDS and w_lower not in seen:
            seen.add(w_lower)
            keywords.append(w_lower)
        if len(keywords) >= max_keywords:
            break
    return keywords


class AssociationNetwork:
    def __init__(
        self,
        neo4j: PKCNeo4jClient,
        qdrant: PKCQdrantClient,
        embedder: Embedder,
    ):
        self.neo4j = neo4j
        self.qdrant = qdrant
        self.embedder = embedder
        self._ensure_schema()

    def _ensure_schema(self):
        """Neo4j-Indizes für Assoziationen anlegen."""
        with self.neo4j.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT concept_name IF NOT EXISTS "
                "FOR (c:Concept) REQUIRE c.name IS UNIQUE"
            )

    def build_from_chunks(self, batch_size: int = 200):
        """
        Alle Chunks aus Qdrant lesen, Co-Occurrences berechnen
        und als Concept-Nodes + ASSOCIATED_WITH-Kanten in Neo4j speichern.
        """
        logger.info("Starte Co-Occurrence-Analyse...")

        # Alle Chunks laden (seitenweise)
        all_chunks = self._load_all_chunks(batch_size)
        logger.info(f"{len(all_chunks)} Chunks geladen.")

        # Co-Occurrences zählen
        pair_counts: Counter = Counter()
        concept_counts: Counter = Counter()
        concept_sources: Dict[str, set] = defaultdict(set)

        for chunk in all_chunks:
            content = chunk.get("content", "")
            source = chunk.get("source", "")
            keywords = extract_keywords(content)

            for kw in keywords:
                concept_counts[kw] += 1
                concept_sources[kw].add(source)

            # Alle Paare innerhalb eines Chunks
            for a, b in combinations(sorted(set(keywords)), 2):
                pair_counts[(a, b)] += 1

        logger.info(f"{len(concept_counts)} einzigartige Konzepte, {len(pair_counts)} Paare gefunden.")

        # In Neo4j speichern
        self._save_concepts(concept_counts, concept_sources)
        self._save_associations(pair_counts, concept_counts)

        logger.success("Association Network aufgebaut.")
        return len(concept_counts), len(pair_counts)

    def _load_all_chunks(self, batch_size: int) -> List[Dict]:
        """Alle Chunks aus Qdrant laden."""
        from qdrant_client.models import ScrollRequest
        chunks = []
        offset = None

        while True:
            results, next_offset = self.qdrant.client.scroll(
                collection_name=self.qdrant.collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend([r.payload for r in results])
            if next_offset is None:
                break
            offset = next_offset

        return chunks

    def _save_concepts(self, counts: Counter, sources: Dict[str, set]):
        """Concept-Nodes in Neo4j anlegen."""
        with self.neo4j.driver.session() as session:
            for name, count in counts.most_common(500):
                session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    SET c.frequency = $frequency,
                        c.source_count = $source_count
                    """,
                    name=name,
                    frequency=count,
                    source_count=len(sources[name]),
                )

    def _save_associations(self, pair_counts: Counter, concept_counts: Counter):
        """ASSOCIATED_WITH-Kanten in Neo4j anlegen."""
        with self.neo4j.driver.session() as session:
            for (a, b), count in pair_counts.most_common(2000):
                if count < 2:
                    continue
                # Normalisierte Assoziationsstärke (Jaccard-ähnlich)
                strength = count / (concept_counts[a] + concept_counts[b] - count)
                session.run(
                    """
                    MATCH (a:Concept {name: $name_a})
                    MATCH (b:Concept {name: $name_b})
                    MERGE (a)-[r:ASSOCIATED_WITH]->(b)
                    SET r.count = $count, r.strength = $strength
                    """,
                    name_a=a,
                    name_b=b,
                    count=count,
                    strength=strength,
                )


class SerendipityEngine:
    def __init__(self, neo4j: PKCNeo4jClient, embedder: Embedder):
        self.neo4j = neo4j
        self.embedder = embedder

    def suggest(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        top_n: int = 4,
    ) -> List[Dict]:
        """
        Findet überraschende aber relevante Verbindungen zur Anfrage.

        Strategie:
        1. Extrahiere Keywords aus Query + Top-Chunks
        2. Finde Konzepte im Neo4j-Graph, die mit diesen Keywords assoziiert sind
        3. Filtere direkt offensichtliche Treffer heraus
        4. Ranke nach: Assoziationsstärke * (1 - Direktrelevanz) → Überraschungsfaktor
        """
        # Keywords aus Query und gefundenen Chunks
        query_keywords = set(extract_keywords(query))
        chunk_keywords = set()
        for chunk in retrieved_chunks[:4]:
            chunk_keywords.update(extract_keywords(chunk.get("content", "")))

        all_known = query_keywords | chunk_keywords

        # Assoziierte Konzepte im Graph suchen
        candidates = self._find_associated_concepts(list(all_known)[:10])

        if not candidates:
            return []

        # Überraschungsfaktor: stark assoziiert aber nicht direkt im Query
        suggestions = []
        for c in candidates:
            name = c["name"]
            if name in all_known:
                continue  # Bereits bekannt → überspringen

            # Überraschungsfaktor: je stärker die Assoziation, je seltener direkt erwähnt
            surprise = c["strength"] * (1.0 - (1.0 / max(c["frequency"], 1)))
            suggestions.append({
                "concept": name,
                "connected_to": c["connected_to"],
                "association_strength": round(c["strength"], 3),
                "frequency": c["frequency"],
                "surprise_score": round(surprise, 3),
            })

        # Nach Überraschungsfaktor sortieren
        suggestions.sort(key=lambda x: x["surprise_score"], reverse=True)
        return suggestions[:top_n]

    def _find_associated_concepts(self, keywords: List[str]) -> List[Dict]:
        """Konzepte finden, die mit den gegebenen Keywords assoziiert sind."""
        if not keywords:
            return []

        with self.neo4j.driver.session() as session:
            result = session.run(
                """
                UNWIND $keywords AS kw
                MATCH (a:Concept {name: kw})-[r:ASSOCIATED_WITH]-(b:Concept)
                WHERE NOT b.name IN $keywords
                RETURN b.name AS name,
                       b.frequency AS frequency,
                       max(r.strength) AS strength,
                       collect(DISTINCT a.name)[0] AS connected_to
                ORDER BY strength DESC
                LIMIT 30
                """,
                keywords=keywords,
            )
            return [dict(r) for r in result]
