"""
JavaScript/TypeScript call tree parser using tree-sitter.
"""
import os
from collections import defaultdict
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Try to import tree-sitter
try:
    from tree_sitter_languages import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter not available - JS/TS parsing disabled")


class JSCallTreeBuilder:
    """Extract function definitions and calls from JavaScript/TypeScript code."""

    def __init__(self, filepath: str):
        """
        Initialize the JS call tree builder.

        Args:
            filepath: Relative path to the file being analyzed
        """
        self.filepath = filepath
        self.func_locations: Dict[str, dict] = {}
        self.calls: Dict[str, List[dict]] = defaultdict(list)

    def parse(self, source: str, language: str = "javascript") -> dict:
        """
        Parse JavaScript/TypeScript source code.

        Args:
            source: Source code string
            language: "javascript" or "typescript"

        Returns:
            Dict with "functions" and "calls" keys
        """
        if not TREE_SITTER_AVAILABLE:
            return {"functions": {}, "calls": {}}

        try:
            # Get parser for the language
            parser = get_parser(language)
            tree = parser.parse(bytes(source, "utf-8"))
            root_node = tree.root_node

            # Extract functions
            self._extract_functions(root_node, source)

            # Extract calls
            self._extract_calls(root_node, source)

            return {
                "functions": self.func_locations,
                "calls": dict(self.calls),
            }
        except Exception as e:
            logger.warning(f"Error parsing {self.filepath}: {e}")
            return {"functions": {}, "calls": {}}

    def _extract_functions(self, node, source: str):
        """Recursively extract function definitions."""
        # Function types to look for
        function_types = {
            "function_declaration",
            "function",
            "arrow_function",
            "method_definition",
            "function_expression",
        }

        if node.type in function_types:
            # Try to get function name
            func_name = self._get_function_name(node, source)

            if func_name:
                qualified_name = f"{self.filepath}::{func_name}"

                self.func_locations[qualified_name] = {
                    "file": self.filepath,
                    "name": func_name,
                    "line_start": node.start_point[0] + 1,  # tree-sitter is 0-indexed
                    "line_end": node.end_point[0] + 1,
                    "qualified": qualified_name,
                }

        # Recurse on children
        for child in node.children:
            self._extract_functions(child, source)

    def _extract_calls(self, node, source: str):
        """Recursively extract function calls."""
        if node.type == "call_expression":
            # Try to get the function being called
            callee_name = self._get_callee_name(node, source)

            if callee_name:
                # Find which function this call is inside
                containing_func = self._find_containing_function(node.start_point[0] + 1)

                if containing_func:
                    self.calls[containing_func].append({
                        "callee": callee_name,
                        "line": node.start_point[0] + 1,
                    })

        # Recurse on children
        for child in node.children:
            self._extract_calls(child, source)

    def _get_function_name(self, node, source: str) -> str:
        """Extract function name from a function node."""
        # For function declarations and expressions with names
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte:child.end_byte]

        # For method definitions
        if node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return source[child.start_byte:child.end_byte]

        # For arrow functions assigned to variables
        # Look at parent assignment
        if node.parent and node.parent.type == "variable_declarator":
            for child in node.parent.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte]

        return None

    def _get_callee_name(self, node, source: str) -> str:
        """Extract the name of the function being called."""
        # The function node is typically the first child
        if node.children:
            func_node = node.children[0]

            # Direct function name
            if func_node.type == "identifier":
                return source[func_node.start_byte:func_node.end_byte]

            # Method call (obj.method)
            if func_node.type == "member_expression":
                # Get the property (method name)
                for child in func_node.children:
                    if child.type == "property_identifier":
                        return source[child.start_byte:child.end_byte]

        return None

    def _find_containing_function(self, line: int) -> str:
        """Find which function contains the given line number."""
        for qname, meta in self.func_locations.items():
            if meta["line_start"] <= line <= meta["line_end"]:
                return qname
        return None


def parse_js_file(filepath: str, root_dir: str) -> dict:
    """
    Parse a JavaScript/TypeScript file.

    Args:
        filepath: Relative path to the file
        root_dir: Project root directory

    Returns:
        Dict with "functions" and "calls" keys
    """
    full_path = os.path.join(root_dir, filepath)

    # Determine language
    ext = os.path.splitext(filepath)[1]
    language = "typescript" if ext in ['.ts', '.tsx'] else "javascript"

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read {filepath}: {e}")
        return {"functions": {}, "calls": {}}

    builder = JSCallTreeBuilder(filepath)
    return builder.parse(source, language)
