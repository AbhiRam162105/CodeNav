"""
Embedder using SentenceTransformer for function semantic search.
"""
import numpy as np
from typing import List
import logging

logger = logging.getLogger(__name__)

# Singleton instance
_embedder_instance = None


class Embedder:
    """Wrapper around SentenceTransformer for embedding functions."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedder.

        Args:
            model_name: SentenceTransformer model to use
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])

        # Encode with sentence-transformers
        embeddings = self.model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # Convert to float32 for FAISS
        return embeddings.astype(np.float32)

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()


def get_embedder() -> Embedder:
    """
    Get or create the singleton embedder instance.

    Returns:
        Embedder instance
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = Embedder()

    return _embedder_instance
