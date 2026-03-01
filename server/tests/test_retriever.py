"""Tests for context retrieval and graph traversal."""
import pytest
import tempfile
import os

from core.retriever import traverse, find_callers, get_context
from core.call_tree import build_codemap, resolve_callees
from embeddings.index import build_index


@pytest.fixture
def sample_codemap():
    """Create a sample codemap with a call chain."""
    return {
        "version": "1.0",
        "root": "/test",
        "functions": {
            "main.py::entry": {
                "file": "main.py",
                "name": "entry",
                "line_start": 1,
                "line_end": 3,
                "qualified": "main.py::entry",
            },
            "main.py::process": {
                "file": "main.py",
                "name": "process",
                "line_start": 5,
                "line_end": 8,
                "qualified": "main.py::process",
            },
            "utils.py::helper": {
                "file": "utils.py",
                "name": "helper",
                "line_start": 1,
                "line_end": 3,
                "qualified": "utils.py::helper",
            },
            "utils.py::validator": {
                "file": "utils.py",
                "name": "validator",
                "line_start": 5,
                "line_end": 7,
                "qualified": "utils.py::validator",
            },
        },
        "calls": {
            "main.py::entry": [
                {
                    "callee": "process",
                    "line": 2,
                    "resolved_to": ["main.py::process"],
                }
            ],
            "main.py::process": [
                {
                    "callee": "helper",
                    "line": 6,
                    "resolved_to": ["utils.py::helper"],
                },
                {
                    "callee": "validator",
                    "line": 7,
                    "resolved_to": ["utils.py::validator"],
                },
            ],
        },
        "function_count": 4,
        "file_count": 2,
    }


def test_traverse_depth_1(sample_codemap):
    """Test traversal with depth 1."""
    results = traverse(sample_codemap, "main.py::entry", depth=1)

    # Should get entry and process (1 hop)
    names = [func["name"] for func in results]
    assert "entry" in names
    assert "process" in names
    assert len(results) == 2


def test_traverse_depth_2(sample_codemap):
    """Test traversal with depth 2."""
    results = traverse(sample_codemap, "main.py::entry", depth=2)

    # Should get entry, process, helper, validator (2 hops)
    names = [func["name"] for func in results]
    assert "entry" in names
    assert "process" in names
    assert "helper" in names
    assert "validator" in names
    assert len(results) == 4


def test_traverse_nonexistent_entry(sample_codemap):
    """Test traversal from non-existent function."""
    results = traverse(sample_codemap, "nonexistent::function", depth=2)
    assert len(results) == 0


def test_traverse_leaf_function(sample_codemap):
    """Test traversal from a leaf function (no outgoing calls)."""
    results = traverse(sample_codemap, "utils.py::helper", depth=2)

    # Should only get the helper itself
    assert len(results) == 1
    assert results[0]["name"] == "helper"


def test_traverse_handles_cycles():
    """Test that traversal doesn't infinite loop on cycles."""
    # Create a codemap with a cycle: A -> B -> C -> A
    codemap = {
        "version": "1.0",
        "root": "/test",
        "functions": {
            "test.py::A": {
                "file": "test.py",
                "name": "A",
                "qualified": "test.py::A",
            },
            "test.py::B": {
                "file": "test.py",
                "name": "B",
                "qualified": "test.py::B",
            },
            "test.py::C": {
                "file": "test.py",
                "name": "C",
                "qualified": "test.py::C",
            },
        },
        "calls": {
            "test.py::A": [
                {"callee": "B", "resolved_to": ["test.py::B"]}
            ],
            "test.py::B": [
                {"callee": "C", "resolved_to": ["test.py::C"]}
            ],
            "test.py::C": [
                {"callee": "A", "resolved_to": ["test.py::A"]}
            ],
        },
    }

    results = traverse(codemap, "test.py::A", depth=5)

    # Should visit all 3 functions exactly once (no infinite loop)
    assert len(results) == 3
    names = [func["name"] for func in results]
    assert set(names) == {"A", "B", "C"}


def test_find_callers(sample_codemap):
    """Test finding functions that call a target."""
    # Find who calls "process"
    callers = find_callers(sample_codemap, "main.py::process")

    assert len(callers) == 1
    assert callers[0]["name"] == "entry"


def test_find_callers_multiple(sample_codemap):
    """Test finding multiple callers."""
    # Find who calls "helper"
    callers = find_callers(sample_codemap, "utils.py::helper")

    assert len(callers) == 1
    assert callers[0]["name"] == "process"


def test_find_callers_none(sample_codemap):
    """Test finding callers when there are none."""
    # Find who calls "entry" (nothing does)
    callers = find_callers(sample_codemap, "main.py::entry")

    assert len(callers) == 0


def test_get_context_integration():
    """Test full context assembly with real files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a realistic project structure
        os.makedirs(os.path.join(tmpdir, "auth"))

        # Create auth files
        with open(os.path.join(tmpdir, "auth", "login.py"), 'w') as f:
            f.write("""def authenticate_user(username, password):
    if validate_credentials(username, password):
        return generate_token(username)
    return None

def validate_credentials(username, password):
    # Check password hash
    return True

def generate_token(username):
    return f"token_{username}"
""")

        # Build codemap
        codemap = build_codemap(tmpdir)
        codemap = resolve_callees(codemap)

        # Build index
        index, metadata = build_index(codemap, tmpdir)

        # Get context for authentication task
        context = get_context(
            task="fix authentication bug",
            codemap=codemap,
            index=index,
            metadata=metadata,
            root_dir=tmpdir,
            depth=2,
            max_tokens=2000
        )

        # Verify context structure
        assert "context_string" in context
        assert "functions" in context
        assert "token_estimate" in context
        assert "entry_functions" in context

        # Should find authentication-related functions
        assert len(context["functions"]) > 0

        # Context string should contain code
        assert "def" in context["context_string"]

        # Token estimate should be reasonable
        assert context["token_estimate"] < 2000


def test_get_context_respects_token_limit():
    """Test that context assembly respects token limits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create many functions
        with open(os.path.join(tmpdir, "test.py"), 'w') as f:
            for i in range(20):
                f.write(f"""
def function_{i}():
    # This is function {i}
    # It does something
    # With multiple lines of code
    print('Function {i}')
    x = {i} * 2
    y = x + 1
    return y
""")

        # Build codemap
        codemap = build_codemap(tmpdir)
        codemap = resolve_callees(codemap)

        # Build index
        index, metadata = build_index(codemap, tmpdir)

        # Get context with small token limit
        context = get_context(
            task="test functions",
            codemap=codemap,
            index=index,
            metadata=metadata,
            root_dir=tmpdir,
            depth=1,
            max_tokens=500  # Small limit
        )

        # Should respect the limit
        assert context["token_estimate"] <= 500

        # Should have fewer than all functions
        assert len(context["functions"]) < 20


def test_get_context_no_results():
    """Test context assembly when search finds nothing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with unrelated functions
        with open(os.path.join(tmpdir, "test.py"), 'w') as f:
            f.write("def foo():\n    pass\n")

        codemap = build_codemap(tmpdir)
        codemap = resolve_callees(codemap)
        index, metadata = build_index(codemap, tmpdir)

        # Search for something completely unrelated
        context = get_context(
            task="quantum physics equations",
            codemap=codemap,
            index=index,
            metadata=metadata,
            root_dir=tmpdir,
            depth=2,
            max_tokens=2000
        )

        # Might get results with low scores or empty results
        # Either way, should return valid structure
        assert "context_string" in context
        assert "functions" in context
        assert isinstance(context["functions"], list)


def test_get_context_entry_functions_prioritized():
    """Test that entry functions appear first in context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files with clear entry points
        with open(os.path.join(tmpdir, "main.py"), 'w') as f:
            f.write("""def main_entry():
    helper_a()
    helper_b()

def helper_a():
    pass

def helper_b():
    pass
""")

        codemap = build_codemap(tmpdir)
        codemap = resolve_callees(codemap)
        index, metadata = build_index(codemap, tmpdir)

        context = get_context(
            task="main entry point",
            codemap=codemap,
            index=index,
            metadata=metadata,
            root_dir=tmpdir,
            depth=2,
            max_tokens=2000
        )

        # Entry function should be listed
        assert len(context["entry_functions"]) > 0

        # Context string should start with entry function
        assert "main_entry" in context["context_string"][:200]
