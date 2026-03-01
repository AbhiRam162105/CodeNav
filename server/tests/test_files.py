"""Tests for file operation endpoints."""
import pytest
import tempfile
import os
from httpx import AsyncClient
from main import app
from state import app_state


@pytest.fixture
def temp_project():
    """Create a temporary project directory with some files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set as project root
        app_state.project_root = tmpdir

        # Create some test files and directories
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "tests"), exist_ok=True)

        # Create test files
        with open(os.path.join(tmpdir, "README.md"), "w") as f:
            f.write("# Test Project\n\nThis is a test.\n")

        with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
            f.write("def main():\n    print('Hello')\n")

        with open(os.path.join(tmpdir, "tests", "test_main.py"), "w") as f:
            f.write("def test_main():\n    assert True\n")

        yield tmpdir

        # Reset state
        app_state.reset()


@pytest.mark.asyncio
async def test_file_tree(temp_project):
    """Test getting the file tree."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/files/tree")

    assert response.status_code == 200
    tree = response.json()

    # Should have README.md, src/, and tests/ at top level
    assert len(tree) == 3
    names = {node["name"] for node in tree}
    assert names == {"README.md", "src", "tests"}

    # Check structure
    for node in tree:
        if node["name"] == "src":
            assert node["type"] == "dir"
            assert len(node["children"]) == 1
            assert node["children"][0]["name"] == "main.py"
            assert node["children"][0]["type"] == "file"


@pytest.mark.asyncio
async def test_file_tree_no_project():
    """Test file tree fails when no project is opened."""
    app_state.reset()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/files/tree")

    assert response.status_code == 400
    assert "no project" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_read_file(temp_project):
    """Test reading a file."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/files/read?path=README.md")

    assert response.status_code == 200
    data = response.json()
    assert "# Test Project" in data["content"]
    assert data["language"] == "markdown"
    assert data["line_count"] == 3
    assert data["size_bytes"] > 0


@pytest.mark.asyncio
async def test_read_file_not_found(temp_project):
    """Test reading a non-existent file."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/files/read?path=nonexistent.txt")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_read_file_path_traversal(temp_project):
    """Test that path traversal is prevented."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/files/read?path=../../etc/passwd")

    assert response.status_code == 400
    assert "traversal" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_write_file(temp_project):
    """Test writing a file."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/files/write",
            json={
                "path": "new_file.py",
                "content": "print('hello world')\n"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["line_count"] == 1

    # Verify file was written
    file_path = os.path.join(temp_project, "new_file.py")
    assert os.path.exists(file_path)
    with open(file_path) as f:
        assert f.read() == "print('hello world')\n"


@pytest.mark.asyncio
async def test_write_file_create_subdirectory(temp_project):
    """Test writing a file in a new subdirectory."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/files/write",
            json={
                "path": "new_dir/new_file.txt",
                "content": "test content"
            }
        )

    assert response.status_code == 200

    # Verify file and directory were created
    file_path = os.path.join(temp_project, "new_dir", "new_file.txt")
    assert os.path.exists(file_path)


@pytest.mark.asyncio
async def test_apply_diff(temp_project):
    """Test applying a diff to a file."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/files/apply_diff",
            json={
                "path": "src/main.py",
                "original": "print('Hello')",
                "modified": "print('Hello, World!')"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["diff"] is not None

    # Verify the file was modified
    file_path = os.path.join(temp_project, "src", "main.py")
    with open(file_path) as f:
        content = f.read()
    assert "Hello, World!" in content


@pytest.mark.asyncio
async def test_apply_diff_stale(temp_project):
    """Test that stale diffs are rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/files/apply_diff",
            json={
                "path": "src/main.py",
                "original": "this string does not exist",
                "modified": "new content"
            }
        )

    assert response.status_code == 409
    assert "stale" in response.json()["detail"].lower()
