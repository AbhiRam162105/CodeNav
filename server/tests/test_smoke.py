"""Smoke test to verify pytest is working correctly."""

def test_true():
    """Baseline test - should always pass."""
    assert True


def test_imports():
    """Verify key dependencies can be imported."""
    try:
        import fastapi
        import google.generativeai
        import sentence_transformers
        import faiss
        assert True
    except ImportError as e:
        assert False, f"Failed to import dependency: {e}"
