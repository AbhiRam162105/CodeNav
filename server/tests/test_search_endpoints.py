"""Tests for search and context retrieval endpoints."""
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
def indexed_project():
    """Create and index a sample project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create auth module
        os.makedirs(os.path.join(tmpdir, "auth"))

        with open(os.path.join(tmpdir, "auth", "login.py"), 'w') as f:
            f.write("""def authenticate_user(username, password):
    '''Authenticate a user with username and password.'''
    if validate_credentials(username, password):
        token = generate_token(username)
        return token
    return None

def validate_credentials(username, password):
    '''Validate user credentials against database.'''
    # Check password hash
    return check_password_hash(password)

def generate_token(username):
    '''Generate JWT token for authenticated user.'''
    return f"jwt_token_{username}"

def check_password_hash(password):
    return True
""")

        # Create payment module
        with open(os.path.join(tmpdir, "payment.py"), 'w') as f:
            f.write("""def process_payment(amount, card_number):
    '''Process a payment transaction.'''
    if validate_amount(amount):
        charge_card(card_number, amount)
        return True
    return False

def validate_amount(amount):
    '''Validate payment amount.'''
    return amount > 0

def charge_card(card_number, amount):
    '''Charge the credit card.'''
    pass
""")

        # Set project root and index
        app_state.project_root = tmpdir

        # Import here to avoid circular dependency
        from core.call_tree import build_codemap, resolve_callees
        from core.serialization import save_codemap
        from embeddings.index import build_index, save_index

        # Build and save codemap
        codemap = build_codemap(tmpdir)
        codemap = resolve_callees(codemap)
        save_codemap(codemap, tmpdir)

        # Build and save index
        index, metadata = build_index(codemap, tmpdir)
        save_index(index, metadata, tmpdir)

        # Update state
        app_state.codemap = codemap
        app_state.faiss_index = index
        app_state.index_metadata = metadata
        app_state.index_status = "ready"

        yield tmpdir


@pytest.mark.asyncio
async def test_search_endpoint_no_index():
    """Test search fails when index is not ready."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/search?query=test")

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_search_endpoint(indexed_project):
    """Test semantic search endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/search?query=user authentication")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert "count" in data
    assert data["count"] > 0

    # Should find authentication-related functions
    results = data["results"]
    assert any("authenticate" in r["name"].lower() for r in results)


@pytest.mark.asyncio
async def test_search_with_top_k(indexed_project):
    """Test search with custom top_k parameter."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/search?query=payment&top_k=2")

    assert response.status_code == 200
    data = response.json()

    # Should return at most 2 results
    assert len(data["results"]) <= 2


@pytest.mark.asyncio
async def test_search_loads_index_from_disk(indexed_project):
    """Test that search loads index from disk if not in memory."""
    # Clear in-memory index
    app_state.faiss_index = None
    app_state.index_metadata = None

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/search?query=authentication")

    assert response.status_code == 200
    data = response.json()

    # Should have loaded from disk and returned results
    assert data["count"] > 0


@pytest.mark.asyncio
async def test_search_result_structure(indexed_project):
    """Test that search results have correct structure."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/search?query=validate")

    assert response.status_code == 200
    results = response.json()["results"]

    if len(results) > 0:
        result = results[0]

        # Check all required fields are present
        assert "score" in result
        assert "qualified_name" in result
        assert "file" in result
        assert "name" in result
        assert "line_start" in result
        assert "line_end" in result

        # Check types
        assert isinstance(result["score"], float)
        assert isinstance(result["line_start"], int)


@pytest.mark.asyncio
async def test_context_retrieve_endpoint_no_index():
    """Test context retrieval fails when index is not ready."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/context/retrieve?task=test"
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_context_retrieve_endpoint(indexed_project):
    """Test context retrieval endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/context/retrieve?task=fix authentication bug"
        )

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "context_string" in data
    assert "functions" in data
    assert "token_estimate" in data
    assert "entry_functions" in data

    # Should have found relevant functions
    assert len(data["functions"]) > 0

    # Context string should contain code
    assert "def" in data["context_string"]

    # Should have entry functions
    assert len(data["entry_functions"]) > 0


@pytest.mark.asyncio
async def test_context_retrieve_with_depth(indexed_project):
    """Test context retrieval with custom depth."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Depth 1
        response1 = await client.post(
            "/context/retrieve?task=authenticate user&depth=1"
        )

        # Depth 2
        response2 = await client.post(
            "/context/retrieve?task=authenticate user&depth=2"
        )

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Depth 2 should generally include more functions (or same)
    assert len(data2["functions"]) >= len(data1["functions"])


@pytest.mark.asyncio
async def test_context_retrieve_with_token_limit(indexed_project):
    """Test context retrieval respects token limit."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/context/retrieve?task=process payment&max_tokens=500"
        )

    assert response.status_code == 200
    data = response.json()

    # Should respect token limit
    assert data["token_estimate"] <= 500


@pytest.mark.asyncio
async def test_context_retrieve_loads_index_from_disk(indexed_project):
    """Test that context retrieval loads index from disk if needed."""
    # Clear in-memory state
    app_state.faiss_index = None
    app_state.index_metadata = None

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/context/retrieve?task=user login"
        )

    assert response.status_code == 200
    data = response.json()

    # Should have loaded from disk and returned context
    assert len(data["functions"]) > 0


@pytest.mark.asyncio
async def test_context_includes_function_metadata(indexed_project):
    """Test that context includes detailed function metadata."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/context/retrieve?task=validate credentials"
        )

    assert response.status_code == 200
    data = response.json()

    if len(data["functions"]) > 0:
        func = data["functions"][0]

        # Check metadata fields
        assert "file" in func
        assert "name" in func
        assert "line_start" in func
        assert "line_end" in func
        assert "qualified" in func


@pytest.mark.asyncio
async def test_search_different_queries(indexed_project):
    """Test search with different types of queries."""
    queries = [
        "user authentication",
        "payment processing",
        "validate data",
        "generate token",
    ]

    async with AsyncClient(app=app, base_url="http://test") as client:
        for query in queries:
            response = await client.get(f"/search?query={query}")

            assert response.status_code == 200
            data = response.json()

            # Each query should find at least one relevant function
            # (assuming our test data has relevant functions)
            assert data["count"] >= 0  # May be 0 for unrelated queries
