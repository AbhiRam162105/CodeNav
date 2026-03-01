#!/bin/bash

# Test script for Phase 2 - Call Tree Engine

echo "=========================================="
echo "Testing CodeNav Phase 2: Call Tree Engine"
echo "=========================================="
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

echo "2. Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

echo "3. Running unit tests..."
echo ""
echo "Testing call tree extraction..."
pytest tests/test_call_tree.py -v --tb=short

echo ""
echo "Testing serialization..."
pytest tests/test_serialization.py -v --tb=short

echo ""
echo "Testing indexing endpoints..."
pytest tests/test_indexing.py -v --tb=short

echo ""
echo "=========================================="
echo "Phase 2 Tests Complete!"
echo "=========================================="
echo ""
echo "To run the server:"
echo "  cd server"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Then test the indexing API:"
echo "  curl -X POST http://localhost:8765/project/open -H 'Content-Type: application/json' -d '{\"path\": \"/path/to/project\"}'"
echo "  curl -X POST http://localhost:8765/index/start"
echo "  curl http://localhost:8765/index/status"
