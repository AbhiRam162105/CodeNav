"""
FAISS index building and searching.
"""
import os
import pickle
import numpy as np
import faiss
from typing import List, Tuple, Optional
import logging

from embeddings.embedder import get_embedder
from embeddings.snippets import extract_snippet, function_to_search_text

logger = logging.getLogger(__name__)


def build_index(codemap: dict, root_dir: str) -> Tuple[faiss.Index, List[dict]]:
    """
    Build a FAISS index from a codemap.

    Args:
        codemap: The codemap dict with functions
        root_dir: Project root directory

    Returns:
        (FAISS index, metadata list) where metadata[i] corresponds to vector i
    """
    embedder = get_embedder()
    functions = codemap["functions"]

    if not functions:
        # Empty index
        empty_index = faiss.IndexFlatIP(embedder.embedding_dim)
        return empty_index, []

    # Extract snippets and build text representations
    texts = []
    metadata = []

    for qualified_name, func_meta in functions.items():
        # Extract code snippet
        snippet = extract_snippet(func_meta, root_dir)

        # Convert to searchable text
        text = function_to_search_text(func_meta, snippet)
        texts.append(text)

        # Store metadata
        metadata.append(func_meta.copy())

    # Embed all texts
    logger.info(f"Embedding {len(texts)} functions...")
    embeddings = embedder.embed_texts(texts)

    # Normalize for cosine similarity (IndexFlatIP with normalized vectors = cosine)
    faiss.normalize_L2(embeddings)

    # Create FAISS index (inner product = cosine similarity with normalized vectors)
    index = faiss.IndexFlatIP(embedder.embedding_dim)
    index.add(embeddings)

    logger.info(f"Built FAISS index with {index.ntotal} vectors")

    return index, metadata


def save_index(index: faiss.Index, metadata: List[dict], project_root: str) -> None:
    """
    Save FAISS index and metadata to disk.

    Args:
        index: FAISS index
        metadata: Metadata list
        project_root: Project root directory
    """
    codenav_dir = os.path.join(project_root, '.codenav')
    os.makedirs(codenav_dir, exist_ok=True)

    # Save FAISS index
    index_path = os.path.join(codenav_dir, 'index.faiss')
    faiss.write_index(index, index_path)

    # Save metadata
    metadata_path = os.path.join(codenav_dir, 'metadata.pkl')
    with open(metadata_path, 'wb') as f:
        pickle.dump(metadata, f)

    logger.info(f"Saved index to {index_path}")


def load_index(project_root: str) -> Optional[Tuple[faiss.Index, List[dict]]]:
    """
    Load FAISS index and metadata from disk.

    Args:
        project_root: Project root directory

    Returns:
        (index, metadata) tuple or None if not found
    """
    index_path = os.path.join(project_root, '.codenav', 'index.faiss')
    metadata_path = os.path.join(project_root, '.codenav', 'metadata.pkl')

    if not os.path.exists(index_path) or not os.path.exists(metadata_path):
        return None

    try:
        # Load FAISS index
        index = faiss.read_index(index_path)

        # Load metadata
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)

        logger.info(f"Loaded index with {index.ntotal} vectors")
        return index, metadata

    except Exception as e:
        logger.error(f"Error loading index: {e}")
        return None


def search(
    query: str,
    index: faiss.Index,
    metadata: List[dict],
    top_k: int = 5,
    min_score: float = 0.3
) -> List[dict]:
    """
    Search for functions matching a query.

    Args:
        query: Natural language query
        index: FAISS index
        metadata: Metadata list
        top_k: Number of results to return
        min_score: Minimum similarity score (0-1)

    Returns:
        List of result dicts with score, function metadata
    """
    if index.ntotal == 0:
        return []

    # Embed query
    embedder = get_embedder()
    query_embedding = embedder.embed_texts([query])

    # Normalize
    faiss.normalize_L2(query_embedding)

    # Search
    scores, indices = index.search(query_embedding, top_k)

    # Build results
    results = []
    for score, idx in zip(scores[0], indices[0]):
        # Filter by minimum score
        if score < min_score:
            continue

        # Get metadata
        func_meta = metadata[idx]

        # Build result
        result = {
            "score": float(score),
            "qualified_name": func_meta["qualified"],
            "file": func_meta["file"],
            "name": func_meta["name"],
            "line_start": func_meta["line_start"],
            "line_end": func_meta["line_end"],
        }
        results.append(result)

    return results
