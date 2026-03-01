#!/bin/bash

# Setup script for CodeNav server
echo "Setting up CodeNav server environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete! Server environment is ready."
echo "To activate: source venv/bin/activate"
