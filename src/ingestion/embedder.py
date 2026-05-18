"""
Embedding-Generierung mit sentence-transformers (lokal, GPU-beschleunigt).
"""
import os
from typing import List
from loguru import logger


class Embedder:
    def __init__(self, model_name: str = None, device: str = None):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.device = device or os.getenv("EMBEDDING_DEVICE", "cuda")
        logger.info(f"Lade Embedding-Modell: {self.model_name} auf {self.device}")
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Modell geladen. Embedding-Dimension: {self.dim}")

    def embed(self, texts: List[str], batch_size: int = 64, show_progress: bool = True) -> List[List[float]]:
        """Texte zu Embeddings umwandeln. Gibt Liste von float-Listen zurück."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_one(self, text: str) -> List[float]:
        """Einzelnen Text embedden."""
        return self.embed([text], show_progress=False)[0]
