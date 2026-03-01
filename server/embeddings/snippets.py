"""
Function snippet extraction for embeddings.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_snippet(func_meta: dict, root_dir: str, context_lines: int = 3) -> str:
    """
    Extract code snippet for a function.

    Args:
        func_meta: Function metadata dict with file, line_start, line_end
        root_dir: Project root directory
        context_lines: Number of extra lines to include after function

    Returns:
        Code snippet string
    """
    file_path = os.path.join(root_dir, func_meta["file"])

    # Fallback if file not found
    if not os.path.exists(file_path):
        logger.warning(f"File not found for snippet: {file_path}")
        return func_meta["name"]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return func_meta["name"]

    # Extract lines (convert to 0-indexed)
    start_idx = func_meta["line_start"] - 1
    end_idx = func_meta["line_end"] + context_lines

    # Clamp to valid range
    start_idx = max(0, start_idx)
    end_idx = min(len(lines), end_idx)

    snippet_lines = lines[start_idx:end_idx]
    return ''.join(snippet_lines)


def function_to_search_text(func_meta: dict, snippet: str) -> str:
    """
    Convert function metadata and snippet to searchable text.

    Format: function_name\nfile_path\nsnippet (first 500 chars)

    Args:
        func_meta: Function metadata
        snippet: Code snippet

    Returns:
        Text representation for embedding
    """
    # Truncate snippet to 500 chars
    truncated_snippet = snippet[:500]

    # Combine name, file, and snippet
    text = f"{func_meta['name']}\n{func_meta['file']}\n{truncated_snippet}"

    return text
