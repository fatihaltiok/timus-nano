"""
Neo4j-Client: Entities und Relations im Graphen speichern und abfragen.
"""
import os
from typing import List, Dict, Optional
from loguru import logger

from neo4j import GraphDatabase

from src.models import KnowledgeEntity, KnowledgeRelation


class PKCNeo4jClient:
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "pkc_password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._create_constraints()
        logger.info(f"Neo4j verbunden: {self.uri}")

    def _create_constraints(self):
        """Unique-Constraint auf Entity-ID sicherstellen."""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )

    def upsert_entity(self, entity: KnowledgeEntity):
        """Entity in Neo4j anlegen oder aktualisieren."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.entity_type = $entity_type,
                    e.description = $description,
                    e.confidence = $confidence,
                    e.last_updated = $last_updated
                """,
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                confidence=entity.confidence,
                last_updated=entity.last_updated.isoformat(),
            )

    def upsert_relation(self, relation: KnowledgeRelation):
        """Beziehung zwischen zwei Entities anlegen oder Zähler erhöhen."""
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (a:Entity {{id: $source_id}})
                MATCH (b:Entity {{id: $target_id}})
                MERGE (a)-[r:{relation.relation_type}]->(b)
                ON CREATE SET r.confidence = $confidence, r.evidence_count = 1
                ON MATCH  SET r.evidence_count = r.evidence_count + 1,
                              r.confidence = $confidence
                """,
                source_id=relation.source_id,
                target_id=relation.target_id,
                confidence=relation.confidence,
            )

    def find_entity_by_name(self, name: str) -> Optional[Dict]:
        """Entity anhand des Namens suchen (case-insensitive)."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (e:Entity) WHERE toLower(e.name) = toLower($name) RETURN e",
                name=name,
            )
            record = result.single()
            if record:
                return dict(record["e"])
        return None

    def get_related_entities(self, entity_id: str, hops: int = 2) -> List[Dict]:
        """Alle Entities finden, die über max. `hops` Kanten erreichbar sind."""
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (start:Entity {{id: $id}})-[*1..{hops}]-(related:Entity)
                WHERE related.id <> $id
                RETURN DISTINCT related
                LIMIT 50
                """,
                id=entity_id,
            )
            return [dict(r["related"]) for r in result]

    def get_all_entities(self) -> List[Dict]:
        """Alle Entities zurückgeben (für Debugging)."""
        with self.driver.session() as session:
            result = session.run("MATCH (e:Entity) RETURN e LIMIT 200")
            return [dict(r["e"]) for r in result]

    def count_entities(self) -> int:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE n:Entity OR n:Concept RETURN count(n) AS n"
            )
            return result.single()["n"]

    def close(self):
        self.driver.close()
