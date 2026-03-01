"""
Utility functions for file operations and path handling.
"""
import os
from typing import List
from models import FileNode

# Directories to exclude from file tree and indexing
EXCLUDED_DIRS = {
    '__pycache__',
    '.git',
    'node_modules',
    'venv',
    '.venv',
    'codenav-env',
    '.codenav',
    'dist',
    'build',
    'out',
    '.pytest_cache',
    '.mypy_cache',
    'coverage',
    '.coverage',
    '.tox',
    '.eggs',
}

# Directories that match these patterns (ends with)
EXCLUDED_DIR_PATTERNS = [
    '.egg-info',
]


def should_exclude_dir(dirname: str) -> bool:
    """Check if a directory should be excluded."""
    if dirname in EXCLUDED_DIRS:
        return True
    for pattern in EXCLUDED_DIR_PATTERNS:
        if dirname.endswith(pattern):
            return True
    return False


def build_file_tree(root_dir: str, current_path: str = "") -> List[FileNode]:
    """
    Build a recursive file tree structure.

    Args:
        root_dir: Absolute path to the project root
        current_path: Relative path from root (for recursion)

    Returns:
        List of FileNode objects representing the tree
    """
    tree = []
    full_path = os.path.join(root_dir, current_path) if current_path else root_dir

    try:
        entries = sorted(os.listdir(full_path))
    except (PermissionError, FileNotFoundError):
        return tree

    for entry in entries:
        entry_rel_path = os.path.join(current_path, entry) if current_path else entry
        entry_full_path = os.path.join(full_path, entry)

        try:
            if os.path.isdir(entry_full_path):
                # Skip excluded directories
                if should_exclude_dir(entry):
                    continue

                # Recursively build subtree
                children = build_file_tree(root_dir, entry_rel_path)
                tree.append(FileNode(
                    name=entry,
                    path=entry_rel_path,
                    type="dir",
                    children=children
                ))
            else:
                # It's a file
                tree.append(FileNode(
                    name=entry,
                    path=entry_rel_path,
                    type="file",
                    children=[]
                ))
        except (PermissionError, OSError):
            # Skip entries we can't access
            continue

    return tree


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    language_map = {
        '.py': 'python',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.json': 'json',
        '.md': 'markdown',
        '.txt': 'plaintext',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.sh': 'shell',
        '.bash': 'shell',
        '.css': 'css',
        '.html': 'html',
        '.xml': 'xml',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
    }
    return language_map.get(ext, 'plaintext')
