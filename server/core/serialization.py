"""
Codemap serialization and caching.
"""
import os
import json
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def compute_source_hash(root_dir: str) -> str:
    """
    Compute a hash of all source files and their modification times.
    Used to detect if the codemap is stale.

    Args:
        root_dir: Project root directory

    Returns:
        MD5 hash string
    """
    from utils import should_exclude_dir

    hash_data = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter excluded directories
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]

        # Process source files
        for filename in filenames:
            if filename.endswith(('.py', '.js', '.ts', '.tsx', '.jsx')):
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir)

                # Get modification time
                try:
                    mtime = os.path.getmtime(full_path)
                    hash_data.append(f"{rel_path}:{mtime}")
                except OSError:
                    continue

    # Sort for consistency
    hash_data.sort()

    # Compute MD5 hash
    hash_str = '\n'.join(hash_data)
    md5 = hashlib.md5(hash_str.encode('utf-8')).hexdigest()
    return md5


def save_codemap(codemap: dict, project_root: str) -> None:
    """
    Save codemap to .codenav/codemap.json with source hash.

    Args:
        codemap: The codemap to save
        project_root: Project root directory
    """
    # Create .codenav directory
    codenav_dir = os.path.join(project_root, '.codenav')
    os.makedirs(codenav_dir, exist_ok=True)

    # Compute source hash
    source_hash = compute_source_hash(project_root)
    codemap["source_hash"] = source_hash

    # Save to file
    codemap_path = os.path.join(codenav_dir, 'codemap.json')
    with open(codemap_path, 'w', encoding='utf-8') as f:
        json.dump(codemap, f, indent=2)

    logger.info(f"Saved codemap with {codemap['function_count']} functions to {codemap_path}")


def load_codemap(project_root: str) -> Optional[dict]:
    """
    Load codemap from .codenav/codemap.json.

    Args:
        project_root: Project root directory

    Returns:
        Codemap dict or None if not found
    """
    codemap_path = os.path.join(project_root, '.codenav', 'codemap.json')

    if not os.path.exists(codemap_path):
        return None

    try:
        with open(codemap_path, 'r', encoding='utf-8') as f:
            codemap = json.load(f)
        logger.info(f"Loaded codemap with {codemap.get('function_count', 0)} functions")
        return codemap
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load codemap: {e}")
        return None


def is_codemap_stale(codemap: dict, project_root: str) -> bool:
    """
    Check if a codemap is stale by comparing source hashes.

    Args:
        codemap: The codemap to check
        project_root: Project root directory

    Returns:
        True if stale, False if fresh
    """
    if "source_hash" not in codemap:
        return True

    current_hash = compute_source_hash(project_root)
    return current_hash != codemap["source_hash"]


def update_codemap_for_file(codemap: dict, changed_file: str, root_dir: str) -> dict:
    """
    Incrementally update codemap for a single changed file.

    Args:
        codemap: Existing codemap
        changed_file: Relative path to changed file
        root_dir: Project root directory

    Returns:
        Updated codemap
    """
    from core.call_tree import parse_file

    # Remove all entries from this file
    # Functions to remove
    functions_to_remove = [
        qname for qname, meta in codemap["functions"].items()
        if meta["file"] == changed_file
    ]

    for qname in functions_to_remove:
        del codemap["functions"][qname]
        if qname in codemap["calls"]:
            del codemap["calls"][qname]

    # Re-parse the file
    result = parse_file(changed_file, root_dir)

    # Merge new results
    codemap["functions"].update(result["functions"])
    codemap["calls"].update(result["calls"])

    # Update counts
    codemap["function_count"] = len(codemap["functions"])

    logger.info(f"Updated codemap for {changed_file}")
    return codemap
