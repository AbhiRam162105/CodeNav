#!/bin/bash

# Fix NumPy compatibility issue for CodeNav
# This script downgrades NumPy to 1.x and rebuilds all dependent packages

set -e

echo "================================================"
echo "CodeNav NumPy Fix Script"
echo "================================================"
echo ""

# Step 1: Uninstall NumPy 2.x
echo "Step 1: Uninstalling NumPy 2.x..."
pip uninstall -y numpy

# Step 2: Install NumPy 1.x
echo ""
echo "Step 2: Installing NumPy 1.x..."
pip install "numpy<2.0"

# Step 3: Rebuild all packages that depend on NumPy
echo ""
echo "Step 3: Rebuilding dependent packages..."
echo "This may take a few minutes..."

# Force reinstall packages that were compiled against NumPy 1.x
pip install --force-reinstall --no-cache-dir \
    pyarrow \
    bottleneck \
    numexpr \
    pandas \
    scikit-learn \
    sentence-transformers

# Step 4: Reinstall other requirements
echo ""
echo "Step 4: Reinstalling all requirements..."
pip install -r requirements.txt

# Step 5: Verify installation
echo ""
echo "Step 5: Verifying installation..."
python -c "import numpy; print(f'✅ NumPy version: {numpy.__version__}')"
python -c "import pandas; print('✅ pandas OK')"
python -c "import sklearn; print('✅ scikit-learn OK')"
python -c "import sentence_transformers; print('✅ sentence-transformers OK')"
python -c "import faiss; print('✅ faiss OK')"

echo ""
echo "================================================"
echo "✅ Fix complete! Restart the CodeNav server."
echo "================================================"
