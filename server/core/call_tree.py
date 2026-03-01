"""
Call Tree Builder - Extract function definitions and call relationships from code.
"""
import ast
import os
from collections import defaultdict
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class CallTreeBuilder(ast.NodeVisitor):
    """
    AST visitor to build a call tree from Python code.
    Extracts function definitions and their call relationships.
    """

    def __init__(self, filepath: str):
        """
        Initialize the call tree builder.

        Args:
            filepath: Relative path to the file being analyzed
        """
        self.filepath = filepath
        self.current_func: Optional[str] = None
        self.calls: Dict[str, List[dict]] = defaultdict(list)
        self.func_locations: Dict[str, dict] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a function definition node."""
        # Compute qualified name (file::function)
        qualified_name = f"{self.filepath}::{node.name}"

        # Store function location
        self.func_locations[qualified_name] = {
            "file": self.filepath,
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno if node.end_lineno else node.lineno,
            "qualified": qualified_name,
        }

        # Save current function context and set new one
        prev_func = self.current_func
        self.current_func = qualified_name

        # Visit child nodes (function body)
        self.generic_visit(node)

        # Restore previous context
        self.current_func = prev_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition - same as regular function."""
        # Treat async functions the same as regular functions
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit a function call node."""
        callee_name = None

        # Extract callee name based on call type
        if isinstance(node.func, ast.Name):
            # Simple call: foo()
            callee_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Method call: obj.method() or self.method()
            callee_name = node.func.attr
        # For other cases (complex expressions), skip

        # If we extracted a name and we're inside a function, record the call
        if callee_name and self.current_func:
            self.calls[self.current_func].append({
                "callee": callee_name,
                "line": node.lineno,
            })

        # Continue visiting child nodes
        self.generic_visit(node)


def parse_file(filepath: str, root_dir: str) -> dict:
    """
    Parse a single Python file and extract its call tree.

    Args:
        filepath: Relative path to the file from root_dir
        root_dir: Absolute path to project root

    Returns:
        Dict with "functions" and "calls" keys
    """
    full_path = os.path.join(root_dir, filepath)

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read {filepath}: {e}")
        return {"functions": {}, "calls": {}}

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        logger.warning(f"Syntax error in {filepath}: {e}")
        return {"functions": {}, "calls": {}}

    # Build call tree
    builder = CallTreeBuilder(filepath)
    builder.visit(tree)

    return {
        "functions": builder.func_locations,
        "calls": dict(builder.calls),
    }


def parse_file_any_language(filepath: str, root_dir: str) -> dict:
    """
    Parse a file using the appropriate parser based on extension.

    Args:
        filepath: Relative path to the file
        root_dir: Project root directory

    Returns:
        Dict with "functions" and "calls" keys
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.py':
        return parse_file(filepath, root_dir)
    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
        from core.js_parser import parse_js_file
        return parse_js_file(filepath, root_dir)
    else:
        # Unsupported extension
        return {"functions": {}, "calls": {}}


def build_codemap(root_dir: str) -> dict:
    """
    Build a complete codemap for a project directory.

    Args:
        root_dir: Absolute path to project root

    Returns:
        Codemap dict with functions, calls, and metadata
    """
    from utils import should_exclude_dir

    functions = {}
    calls = {}
    file_count = 0

    # Supported extensions
    supported_exts = {'.py', '.js', '.jsx', '.ts', '.tsx'}

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out excluded directories (modifies dirnames in-place)
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]

        # Process supported files
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported_exts:
                continue

            # Get relative path
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            # Parse the file using appropriate parser
            result = parse_file_any_language(rel_path, root_dir)

            # Merge results
            functions.update(result["functions"])
            calls.update(result["calls"])
            file_count += 1

    return {
        "version": "1.0",
        "root": root_dir,
        "functions": functions,
        "calls": calls,
        "file_count": file_count,
        "function_count": len(functions),
    }


def resolve_callees(codemap: dict) -> dict:
    """
    Post-process codemap to resolve callee names to qualified names.

    Since callees are stored as short names (e.g., "foo") but we need to know
    which specific function they refer to, we match against all known functions.

    Args:
        codemap: The codemap to process

    Returns:
        Updated codemap with resolved_to field in call entries
    """
    # Build a map from short name to list of qualified names
    short_to_qualified = defaultdict(list)
    for qualified_name, func_meta in codemap["functions"].items():
        short_name = func_meta["name"]
        short_to_qualified[short_name].append(qualified_name)

    # Update each call with resolved targets
    updated_calls = {}
    for caller_qname, call_list in codemap["calls"].items():
        updated_call_list = []
        for call in call_list:
            callee_short = call["callee"]
            resolved = short_to_qualified.get(callee_short, [])

            updated_call = call.copy()
            updated_call["resolved_to"] = resolved
            updated_call_list.append(updated_call)

        updated_calls[caller_qname] = updated_call_list

    codemap["calls"] = updated_calls
    return codemap
