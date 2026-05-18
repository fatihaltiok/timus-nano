from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
import uuid


@dataclass
class KnowledgeChunk:
    content: str
    source: str
    chunk_type: str  # "note", "code", "article", "conversation"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: List[float] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "chunk_type": self.chunk_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "confidence": self.confidence,
        }


@dataclass
class KnowledgeEntity:
    name: str
    entity_type: str  # "concept", "person", "project", "tool", "algorithm"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    confidence: float = 0.8
    first_mentioned: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    sources: List[str] = field(default_factory=list)
    properties: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "confidence": self.confidence,
            "first_mentioned": self.first_mentioned.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "sources": self.sources,
            "properties": self.properties,
        }


@dataclass
class KnowledgeRelation:
    source_id: str
    target_id: str
    relation_type: str  # "learns_from", "uses", "builds", "solves", "relates_to"
    confidence: float = 0.7
    evidence_count: int = 1
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QueryResult:
    query: str
    chunks: List[KnowledgeChunk]
    entities: List[KnowledgeEntity]
    response: str = ""
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "chunks": [c.to_dict() for c in self.chunks],
            "entities": [e.to_dict() for e in self.entities],
            "response": self.response,
            "confidence": self.confidence,
            "sources": self.sources,
            "latency_ms": self.latency_ms,
        }
