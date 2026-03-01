#!/bin/bash

# Test script for Phase 3 - Embeddings and Semantic Search

echo "================================================"
echo "Testing CodeNav Phase 3: Embeddings & Search"
echo "================================================"
echo ""

# Navigate to server directory
cd "$(dirname "$0")/server"

echo "1. Checking Python environment..."
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

echo "2. Installing/updating dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies ready"
echo ""

echo "3. Running Phase 3 tests..."
echo ""

echo "Testing embeddings and FAISS indexing..."
pytest tests/test_embeddings.py -v --tb=short
EMBEDDINGS_RESULT=$?

echo ""
echo "Testing graph traversal and context retrieval..."
pytest tests/test_retriever.py -v --tb=short
RETRIEVER_RESULT=$?

echo ""
echo "Testing search and context endpoints..."
pytest tests/test_search_endpoints.py -v --tb=short
ENDPOINTS_RESULT=$?

echo ""
echo "================================================"

if [ $EMBEDDINGS_RESULT -eq 0 ] && [ $RETRIEVER_RESULT -eq 0 ] && [ $ENDPOINTS_RESULT -eq 0 ]; then
    echo "✅ All Phase 3 tests passed!"
    echo "================================================"
    echo ""
    echo "Semantic search is ready! Try it:"
    echo ""
    echo "1. Start the server:"
    echo "   cd server && source venv/bin/activate && python main.py"
    echo ""
    echo "2. Index a project:"
    echo "   curl -X POST http://localhost:8765/project/open \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"path\": \"/path/to/project\"}'"
    echo "   curl -X POST http://localhost:8765/index/start"
    echo ""
    echo "3. Search for functions:"
    echo "   curl 'http://localhost:8765/search?query=user%20authentication'"
    echo ""
    echo "4. Retrieve context for a task:"
    echo "   curl -X POST 'http://localhost:8765/context/retrieve?task=fix%20auth%20bug'"
    echo ""
else
    echo "❌ Some tests failed. Check output above."
    exit 1
fi
