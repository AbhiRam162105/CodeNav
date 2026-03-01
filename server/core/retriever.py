"""
Context retrieval through graph traversal.
"""
from collections import deque
from typing import List, Set, Dict, Tuple
import logging

from embeddings.snippets import extract_snippet

logger = logging.getLogger(__name__)


def traverse(codemap: dict, entry_qname: str, depth: int = 2) -> List[dict]:
    """
    Traverse the call graph using BFS from an entry point.

    Args:
        codemap: The codemap
        entry_qname: Qualified name of the entry function
        depth: Maximum depth to traverse

    Returns:
        List of function metadata dicts in discovery order
    """
    if entry_qname not in codemap["functions"]:
        logger.warning(f"Entry function not found: {entry_qname}")
        return []

    # BFS queue: (qualified_name, current_depth)
    queue = deque([(entry_qname, 0)])
    visited: Set[str] = set()
    results = []

    while queue:
        qname, current_depth = queue.popleft()

        # Skip if already visited
        if qname in visited:
            continue

        visited.add(qname)

        # Add to results
        if qname in codemap["functions"]:
            results.append(codemap["functions"][qname])

        # Stop if we've reached max depth
        if current_depth >= depth:
            continue

        # Get callees
        if qname in codemap["calls"]:
            for call in codemap["calls"][qname]:
                # Add all resolved targets
                for resolved_qname in call.get("resolved_to", []):
                    if resolved_qname not in visited:
                        queue.append((resolved_qname, current_depth + 1))

    return results


def find_callers(codemap: dict, target_qname: str) -> List[dict]:
    """
    Find all functions that call the target function.

    Args:
        codemap: The codemap
        target_qname: Qualified name of target function

    Returns:
        List of caller function metadata dicts
    """
    callers = []

    for caller_qname, call_list in codemap["calls"].items():
        # Check if this function calls the target
        for call in call_list:
            if target_qname in call.get("resolved_to", []):
                # This function calls the target
                if caller_qname in codemap["functions"]:
                    callers.append(codemap["functions"][caller_qname])
                break

    return callers


def get_context(
    task: str,
    codemap: dict,
    index,
    metadata: List[dict],
    root_dir: str,
    depth: int = 2,
    max_tokens: int = 2000
) -> dict:
    """
    Assemble context for a task using semantic search + graph traversal.

    Args:
        task: Natural language task description
        codemap: The codemap
        index: FAISS index
        metadata: Index metadata
        root_dir: Project root directory
        depth: Traversal depth
        max_tokens: Maximum tokens to include

    Returns:
        Dict with context_string, functions, token_estimate, entry_functions
    """
    from embeddings.index import search

    # Step 1: Semantic search for entry points
    search_results = search(task, index, metadata, top_k=3, min_score=0.3)

    if not search_results:
        logger.warning(f"No search results for task: {task}")
        return {
            "context_string": "",
            "functions": [],
            "token_estimate": 0,
            "entry_functions": [],
        }

    # Step 2: Traverse from each entry point
    all_functions = {}  # qualified_name -> metadata
    entry_functions = []

    for result in search_results:
        qname = result["qualified_name"]
        entry_functions.append(qname)

        # Traverse from this entry
        traversed = traverse(codemap, qname, depth)

        # Add to collection (deduplicates by qualified name)
        for func_meta in traversed:
            all_functions[func_meta["qualified"]] = func_meta

    # Step 3: Extract snippets and build context string
    snippets = []
    total_chars = 0

    # Prioritize entry functions first
    for qname in entry_functions:
        if qname in all_functions:
            func_meta = all_functions[qname]
            snippet = extract_snippet(func_meta, root_dir)

            # Add function header comment
            header = f"\n# {func_meta['qualified']} ({func_meta['file']}:{func_meta['line_start']})\n"
            full_snippet = header + snippet

            snippets.append(full_snippet)
            total_chars += len(full_snippet)

    # Add remaining functions
    for qname, func_meta in all_functions.items():
        if qname in entry_functions:
            continue  # Already added

        snippet = extract_snippet(func_meta, root_dir)
        header = f"\n# {func_meta['qualified']} ({func_meta['file']}:{func_meta['line_start']})\n"
        full_snippet = header + snippet

        # Check token budget (rough estimate: 1 token ≈ 3.5 chars)
        estimated_tokens = total_chars / 3.5
        if estimated_tokens + len(full_snippet) / 3.5 > max_tokens:
            logger.info(f"Reached token limit at {len(snippets)} functions")
            break

        snippets.append(full_snippet)
        total_chars += len(full_snippet)

    # Combine all snippets
    context_string = "".join(snippets)
    token_estimate = int(total_chars / 3.5)

    return {
        "context_string": context_string,
        "functions": list(all_functions.values()),
        "token_estimate": token_estimate,
        "entry_functions": entry_functions,
    }
