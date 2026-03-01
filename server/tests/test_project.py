"""Tests for project management endpoints."""
import pytest
import tempfile
import os
from httpx import AsyncClient
from main import app
from state import app_state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset app state before each test."""
    app_state.reset()
    yield
    app_state.reset()


@pytest.mark.asyncio
async def test_open_project_success():
    """Test opening a valid project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/project/open",
                json={"path": tmpdir}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["path"] == os.path.abspath(tmpdir)
        assert data["name"] == os.path.basename(tmpdir)
        assert app_state.project_root == os.path.abspath(tmpdir)


@pytest.mark.asyncio
async def test_open_project_not_found():
    """Test opening a non-existent directory."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/project/open",
            json={"path": "/nonexistent/path"}
        )

    assert response.status_code == 400
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_open_project_file_path():
    """Test that opening a file path fails."""
    with tempfile.NamedTemporaryFile() as tmpfile:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/project/open",
                json={"path": tmpfile.name}
            )

        assert response.status_code == 400
        data = response.json()
        assert "not a directory" in data["detail"].lower()
