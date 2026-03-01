"""Tests for codemap serialization."""
import pytest
import tempfile
import os
import time
from core.serialization import (
    save_codemap,
    load_codemap,
    is_codemap_stale,
    compute_source_hash,
    update_codemap_for_file,
)


@pytest.fixture
def sample_codemap():
    """Create a sample codemap for testing."""
    return {
        "version": "1.0",
        "root": "/test",
        "functions": {
            "test.py::foo": {
                "file": "test.py",
                "name": "foo",
                "line_start": 1,
                "line_end": 3,
                "qualified": "test.py::foo",
            }
        },
        "calls": {
            "test.py::foo": [
                {"callee": "bar", "line": 2}
            ]
        },
        "function_count": 1,
        "file_count": 1,
    }


def test_save_and_load_codemap(sample_codemap):
    """Test saving and loading a codemap."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Add a source file for hash computation
        with open(os.path.join(tmpdir, "test.py"), 'w') as f:
            f.write("def foo():\n    bar()\n")

        # Update root in codemap
        sample_codemap["root"] = tmpdir

        # Save codemap
        save_codemap(sample_codemap, tmpdir)

        # Check file was created
        codemap_path = os.path.join(tmpdir, '.codenav', 'codemap.json')
        assert os.path.exists(codemap_path)

        # Load codemap
        loaded = load_codemap(tmpdir)

        assert loaded is not None
        assert loaded["version"] == sample_codemap["version"]
        assert loaded["function_count"] == sample_codemap["function_count"]
        assert "source_hash" in loaded


def test_load_nonexistent_codemap():
    """Test loading a codemap that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loaded = load_codemap(tmpdir)
        assert loaded is None


def test_is_codemap_stale():
    """Test staleness detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source file
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w') as f:
            f.write("def foo():\n    pass\n")

        # Compute hash
        hash1 = compute_source_hash(tmpdir)

        # Create codemap with this hash
        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "source_hash": hash1,
            "functions": {},
            "calls": {},
            "function_count": 0,
            "file_count": 0,
        }

        # Should not be stale
        assert not is_codemap_stale(codemap, tmpdir)

        # Modify the file
        time.sleep(0.1)  # Ensure different mtime
        with open(test_file, 'w') as f:
            f.write("def foo():\n    print('modified')\n")

        # Should now be stale
        assert is_codemap_stale(codemap, tmpdir)


def test_update_codemap_for_file():
    """Test incremental codemap update."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two files
        file1 = os.path.join(tmpdir, "file1.py")
        file2 = os.path.join(tmpdir, "file2.py")

        with open(file1, 'w') as f:
            f.write("def old_func():\n    pass\n")

        with open(file2, 'w') as f:
            f.write("def unchanged():\n    pass\n")

        # Create initial codemap
        codemap = {
            "version": "1.0",
            "root": tmpdir,
            "functions": {
                "file1.py::old_func": {
                    "file": "file1.py",
                    "name": "old_func",
                    "line_start": 1,
                    "line_end": 2,
                },
                "file2.py::unchanged": {
                    "file": "file2.py",
                    "name": "unchanged",
                    "line_start": 1,
                    "line_end": 2,
                },
            },
            "calls": {},
            "function_count": 2,
            "file_count": 2,
        }

        # Modify file1
        with open(file1, 'w') as f:
            f.write("def new_func():\n    pass\n")

        # Update codemap
        updated = update_codemap_for_file(codemap, "file1.py", tmpdir)

        # Old function should be gone
        assert "file1.py::old_func" not in updated["functions"]

        # New function should exist
        assert "file1.py::new_func" in updated["functions"]

        # Unchanged file should still be there
        assert "file2.py::unchanged" in updated["functions"]

        # Function count should be updated
        assert updated["function_count"] == 2


def test_compute_source_hash_excludes_dirs():
    """Test that excluded directories don't affect the hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source file
        with open(os.path.join(tmpdir, "main.py"), 'w') as f:
            f.write("def main():\n    pass\n")

        # Compute initial hash
        hash1 = compute_source_hash(tmpdir)

        # Add file in excluded directory
        os.makedirs(os.path.join(tmpdir, "node_modules"))
        with open(os.path.join(tmpdir, "node_modules", "lib.py"), 'w') as f:
            f.write("def lib():\n    pass\n")

        # Hash should be unchanged
        hash2 = compute_source_hash(tmpdir)
        assert hash1 == hash2
