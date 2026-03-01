"""Tests for call tree extraction."""
import pytest
import tempfile
import os
from core.call_tree import (
    CallTreeBuilder,
    parse_file,
    build_codemap,
    resolve_callees,
    parse_file_any_language,
)
import ast


def test_function_visitor():
    """Test that function definitions are extracted correctly."""
    source = """
def foo():
    pass

def bar():
    pass

async def baz():
    pass
"""
    tree = ast.parse(source)
    builder = CallTreeBuilder("test.py")
    builder.visit(tree)

    assert len(builder.func_locations) == 3
    assert "test.py::foo" in builder.func_locations
    assert "test.py::bar" in builder.func_locations
    assert "test.py::baz" in builder.func_locations

    # Check line numbers
    assert builder.func_locations["test.py::foo"]["line_start"] == 2
    assert builder.func_locations["test.py::bar"]["line_start"] == 5
    assert builder.func_locations["test.py::baz"]["line_start"] == 8


def test_nested_functions():
    """Test that nested functions are extracted."""
    source = """
def outer():
    def inner():
        pass
    return inner
"""
    tree = ast.parse(source)
    builder = CallTreeBuilder("test.py")
    builder.visit(tree)

    assert len(builder.func_locations) == 2
    assert "test.py::outer" in builder.func_locations
    assert "test.py::inner" in builder.func_locations


def test_call_extraction():
    """Test that function calls are extracted."""
    source = """
def foo():
    bar()
    baz()

def bar():
    pass

def baz():
    pass
"""
    tree = ast.parse(source)
    builder = CallTreeBuilder("test.py")
    builder.visit(tree)

    # Check calls from foo
    foo_calls = builder.calls["test.py::foo"]
    assert len(foo_calls) == 2
    callee_names = {call["callee"] for call in foo_calls}
    assert callee_names == {"bar", "baz"}


def test_method_calls():
    """Test that method calls are extracted."""
    source = """
class MyClass:
    def method1(self):
        self.method2()
        self.method3()

    def method2(self):
        pass

    def method3(self):
        pass
"""
    tree = ast.parse(source)
    builder = CallTreeBuilder("test.py")
    builder.visit(tree)

    # Check method calls
    method1_calls = builder.calls["test.py::method1"]
    assert len(method1_calls) == 2
    callee_names = {call["callee"] for call in method1_calls}
    assert callee_names == {"method2", "method3"}


def test_parse_file():
    """Test parsing a single file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("""
def function_a():
    function_b()

def function_b():
    function_c()

def function_c():
    pass
""")

        result = parse_file("test.py", tmpdir)

        # Check functions
        assert len(result["functions"]) == 3
        assert "test.py::function_a" in result["functions"]
        assert "test.py::function_b" in result["functions"]
        assert "test.py::function_c" in result["functions"]

        # Check calls
        assert "function_b" in [c["callee"] for c in result["calls"]["test.py::function_a"]]
        assert "function_c" in [c["callee"] for c in result["calls"]["test.py::function_b"]]


def test_build_codemap():
    """Test building a codemap for a project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        os.makedirs(os.path.join(tmpdir, "src"))
        os.makedirs(os.path.join(tmpdir, "tests"))

        # Create test files
        with open(os.path.join(tmpdir, "src", "main.py"), 'w') as f:
            f.write("def main():\n    helper()\n\ndef helper():\n    pass\n")

        with open(os.path.join(tmpdir, "tests", "test_main.py"), 'w') as f:
            f.write("def test_main():\n    assert True\n")

        # Build codemap
        codemap = build_codemap(tmpdir)

        # Check metadata
        assert codemap["version"] == "1.0"
        assert codemap["root"] == tmpdir
        assert codemap["function_count"] == 3
        assert codemap["file_count"] == 2

        # Check functions exist
        assert any("main" in qname for qname in codemap["functions"])
        assert any("helper" in qname for qname in codemap["functions"])
        assert any("test_main" in qname for qname in codemap["functions"])


def test_resolve_callees():
    """Test resolving short callee names to qualified names."""
    # Create a codemap with ambiguous function names
    codemap = {
        "version": "1.0",
        "root": "/test",
        "functions": {
            "file1.py::foo": {"name": "foo", "file": "file1.py"},
            "file2.py::foo": {"name": "foo", "file": "file2.py"},
            "file1.py::bar": {"name": "bar", "file": "file1.py"},
        },
        "calls": {
            "file1.py::bar": [
                {"callee": "foo", "line": 10}
            ]
        },
        "function_count": 3,
        "file_count": 2,
    }

    # Resolve callees
    resolved = resolve_callees(codemap)

    # Check that foo resolves to both definitions
    bar_calls = resolved["calls"]["file1.py::bar"]
    assert len(bar_calls) == 1
    assert "resolved_to" in bar_calls[0]
    assert len(bar_calls[0]["resolved_to"]) == 2
    assert "file1.py::foo" in bar_calls[0]["resolved_to"]
    assert "file2.py::foo" in bar_calls[0]["resolved_to"]


def test_syntax_error_handling():
    """Test that syntax errors are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with syntax error
        test_file = os.path.join(tmpdir, "bad.py")
        with open(test_file, 'w') as f:
            f.write("def foo(\n")  # Incomplete function

        result = parse_file("bad.py", tmpdir)

        # Should return empty results, not crash
        assert result["functions"] == {}
        assert result["calls"] == {}


def test_excluded_directories():
    """Test that excluded directories are not indexed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create excluded directories
        os.makedirs(os.path.join(tmpdir, "node_modules"))
        os.makedirs(os.path.join(tmpdir, "__pycache__"))
        os.makedirs(os.path.join(tmpdir, ".git"))
        os.makedirs(os.path.join(tmpdir, "src"))

        # Add files
        with open(os.path.join(tmpdir, "node_modules", "lib.py"), 'w') as f:
            f.write("def excluded():\n    pass\n")

        with open(os.path.join(tmpdir, "src", "main.py"), 'w') as f:
            f.write("def included():\n    pass\n")

        # Build codemap
        codemap = build_codemap(tmpdir)

        # Should only include src/main.py
        assert codemap["file_count"] == 1
        assert any("included" in qname for qname in codemap["functions"])
        assert not any("excluded" in qname for qname in codemap["functions"])
