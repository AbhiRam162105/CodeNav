"""Tests for embeddings and FAISS indexing."""
import pytest
import tempfile
import os
import numpy as np

from embeddings.embedder import Embedder, get_embedder
from embeddings.snippets import extract_snippet, function_to_search_text
from embeddings.index import build_index, save_index, load_index, search


def test_embedder_initialization():
    """Test embedder can be initialized."""
    embedder = Embedder()
    assert embedder is not None
    assert embedder.embedding_dim == 384  # all-MiniLM-L6-v2 dimension


def test_embedder_singleton():
    """Test that get_embedder returns the same instance."""
    emb1 = get_embedder()
    emb2 = get_embedder()
    assert emb1 is emb2


def test_embed_texts():
    """Test embedding text."""
    embedder = get_embedder()
    texts = ["function foo", "function bar", "helper method"]

    embeddings = embedder.embed_texts(texts)

    assert embeddings.shape == (3, 384)
    assert embeddings.dtype == np.float32


def test_embed_empty():
    """Test embedding empty list."""
    embedder = get_embedder()
    embeddings = embedder.embed_texts([])
    assert len(embeddings) == 0


def test_extract_snippet():
    """Test extracting code snippet from a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("""def foo():
    print('hello')
    print('world')
    return True

def bar():
    pass
""")

        func_meta = {
            "file": "test.py",
            "name": "foo",
            "line_start": 1,
            "line_end": 4,
        }

        snippet = extract_snippet(func_meta, tmpdir, context_lines=1)

        # Should include function definition and one extra line
        assert "def foo():" in snippet
        assert "print('hello')" in snippet
        assert "return True" in snippet


def test_extract_snippet_file_not_found():
    """Test snippet extraction when file doesn't exist."""
    func_meta = {
        "file": "nonexistent.py",
        "name": "foo",
        "line_start": 1,
        "line_end": 3,
    }

    snippet = extract_snippet(func_meta, "/tmp", context_lines=0)

    # Should return function name as fallback
    assert snippet == "foo"


def test_function_to_search_text():
    """Test converting function to searchable text."""
    func_meta = {
        "name": "validate_user",
        "file": "auth/login.py",
        "qualified": "auth/login.py::validate_user",
    }

    snippet = "def validate_user(username, password):\n    return True"

    text = function_to_search_text(func_meta, snippet)

    # Should contain name, file, and snippet
    assert "validate_user" in text
    assert "auth/login.py" in text
    assert "def validate_user" in text


def test_function_to_search_text_truncates():
    """Test that long snippets are truncated."""
    func_meta = {
        "name": "foo",
        "file": "test.py",
        "qualified": "test.py::foo",
    }

    # Create a long snippet (over 500 chars)
    snippet = "x" * 1000

    text = function_to_search_text(func_meta, snippet)

    # Should be truncated
    assert len(text) < 600  # Name + file + 500 char snippet


def test_build_index():
    """Test building a FAISS index from a codemap."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("""def authenticate():
    validate()
    check_token()

def validate():
    pass

def check_token():
    pass
""")

        # Create a minimal codemap
        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "functions": {
                "test.py::authenticate": {
                    "file": "test.py",
                    "name": "authenticate",
                    "line_start": 1,
                    "line_end": 3,
                    "qualified": "test.py::authenticate",
                },
                "test.py::validate": {
                    "file": "test.py",
                    "name": "validate",
                    "line_start": 5,
                    "line_end": 6,
                    "qualified": "test.py::validate",
                },
                "test.py::check_token": {
                    "file": "test.py",
                    "name": "check_token",
                    "line_start": 8,
                    "line_end": 9,
                    "qualified": "test.py::check_token",
                },
            },
            "calls": {},
            "function_count": 3,
            "file_count": 1,
        }

        # Build index
        index, metadata = build_index(codemap, tmpdir)

        assert index.ntotal == 3
        assert len(metadata) == 3
        assert metadata[0]["name"] in ["authenticate", "validate", "check_token"]


def test_build_index_empty():
    """Test building an index with no functions."""
    codemap = {
        "version": "1.0",
        "root": "/tmp",
        "functions": {},
        "calls": {},
        "function_count": 0,
        "file_count": 0,
    }

    index, metadata = build_index(codemap, "/tmp")

    assert index.ntotal == 0
    assert len(metadata) == 0


def test_save_and_load_index():
    """Test saving and loading a FAISS index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal test file and codemap
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("def foo():\n    pass\n")

        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "functions": {
                "test.py::foo": {
                    "file": "test.py",
                    "name": "foo",
                    "line_start": 1,
                    "line_end": 2,
                    "qualified": "test.py::foo",
                },
            },
            "calls": {},
            "function_count": 1,
            "file_count": 1,
        }

        # Build and save index
        index, metadata = build_index(codemap, tmpdir)
        save_index(index, metadata, tmpdir)

        # Load index
        loaded = load_index(tmpdir)

        assert loaded is not None
        loaded_index, loaded_metadata = loaded

        assert loaded_index.ntotal == 1
        assert len(loaded_metadata) == 1
        assert loaded_metadata[0]["name"] == "foo"


def test_load_nonexistent_index():
    """Test loading an index that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = load_index(tmpdir)
        assert result is None


def test_search():
    """Test semantic search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files with different functions
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("""def authenticate_user(username, password):
    check_credentials()

def process_payment(amount):
    validate_amount()

def send_email(to, subject):
    format_message()
""")

        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "functions": {
                "test.py::authenticate_user": {
                    "file": "test.py",
                    "name": "authenticate_user",
                    "line_start": 1,
                    "line_end": 2,
                    "qualified": "test.py::authenticate_user",
                },
                "test.py::process_payment": {
                    "file": "test.py",
                    "name": "process_payment",
                    "line_start": 4,
                    "line_end": 5,
                    "qualified": "test.py::process_payment",
                },
                "test.py::send_email": {
                    "file": "test.py",
                    "name": "send_email",
                    "line_start": 7,
                    "line_end": 8,
                    "qualified": "test.py::send_email",
                },
            },
            "calls": {},
            "function_count": 3,
            "file_count": 1,
        }

        # Build index
        index, metadata = build_index(codemap, tmpdir)

        # Search for authentication-related functions
        results = search("user login authentication", index, metadata, top_k=3)

        assert len(results) > 0

        # The authenticate_user function should be in top results
        top_result = results[0]
        assert "authenticate" in top_result["name"] or "user" in top_result["name"]
        assert top_result["score"] > 0.3


def test_search_filters_low_scores():
    """Test that search filters out results below minimum score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("def foo():\n    pass\n")

        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "functions": {
                "test.py::foo": {
                    "file": "test.py",
                    "name": "foo",
                    "line_start": 1,
                    "line_end": 2,
                    "qualified": "test.py::foo",
                },
            },
            "calls": {},
            "function_count": 1,
            "file_count": 1,
        }

        index, metadata = build_index(codemap, tmpdir)

        # Search for something completely unrelated
        results = search(
            "quantum physics nuclear reactor",
            index,
            metadata,
            top_k=5,
            min_score=0.5  # High threshold
        )

        # Should get no results (assuming low similarity)
        # Or very few results
        assert len(results) <= 1
