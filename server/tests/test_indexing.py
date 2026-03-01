"""Tests for indexing endpoints."""
import pytest
import tempfile
import os
import time
from httpx import AsyncClient
from main import app
from state import app_state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset app state before each test."""
    app_state.reset()
    yield
    app_state.reset()


@pytest.fixture
def sample_project():
    """Create a sample project for indexing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some Python files
        os.makedirs(os.path.join(tmpdir, "src"))

        with open(os.path.join(tmpdir, "src", "main.py"), 'w') as f:
            f.write("""
def main():
    process_data()
    save_results()

def process_data():
    load_data()
    transform_data()

def load_data():
    pass

def transform_data():
    pass

def save_results():
    pass
""")

        with open(os.path.join(tmpdir, "src", "utils.py"), 'w') as f:
            f.write("""
def helper():
    pass

def validator():
    pass
""")

        yield tmpdir


@pytest.mark.asyncio
async def test_index_status_no_project():
    """Test index status when no project is open."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/index/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_project"
    assert data["progress"] == 0
    assert data["function_count"] == 0


@pytest.mark.asyncio
async def test_start_indexing_no_project():
    """Test that indexing fails when no project is open."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/index/start")

    assert response.status_code == 400
    assert "no project" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_indexing_workflow(sample_project):
    """Test the complete indexing workflow."""
    # Open project
    app_state.project_root = sample_project

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Start indexing
        response = await client.post("/index/start")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

        # Wait for indexing to complete (poll status)
        max_wait = 10  # seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = await client.get("/index/status")
            data = response.json()

            if data["status"] == "ready":
                break

            time.sleep(0.5)

        # Check final status
        response = await client.get("/index/status")
        data = response.json()

        assert data["status"] == "ready"
        assert data["progress"] == 100
        assert data["function_count"] > 0
        assert data["file_count"] == 2

        # Verify codemap was built
        assert app_state.codemap is not None
        assert app_state.codemap["function_count"] > 0

        # Check specific functions exist
        functions = app_state.codemap["functions"]
        assert any("main" in qname for qname in functions)
        assert any("process_data" in qname for qname in functions)
        assert any("helper" in qname for qname in functions)


@pytest.mark.asyncio
async def test_indexing_creates_codenav_dir(sample_project):
    """Test that indexing creates .codenav directory and files."""
    app_state.project_root = sample_project

    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/index/start")

        # Wait for completion
        max_wait = 10
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = await client.get("/index/status")
            if response.json()["status"] == "ready":
                break
            time.sleep(0.5)

    # Check .codenav directory was created
    codenav_dir = os.path.join(sample_project, ".codenav")
    assert os.path.exists(codenav_dir)

    # Check codemap.json exists
    codemap_file = os.path.join(codenav_dir, "codemap.json")
    assert os.path.exists(codemap_file)


@pytest.mark.asyncio
async def test_prevent_concurrent_indexing(sample_project):
    """Test that concurrent indexing requests are rejected."""
    app_state.project_root = sample_project

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Start first indexing
        response1 = await client.post("/index/start")
        assert response1.status_code == 200

        # Try to start second indexing immediately
        response2 = await client.post("/index/start")
        assert response2.status_code == 400
        assert "already in progress" in response2.json()["detail"].lower()
