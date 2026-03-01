#!/bin/bash
# Setup script for CodeNav VS Code extension

echo "📦 Installing Node.js dependencies..."
cd "$(dirname "$0")"
npm install

echo ""
echo "🔨 Compiling TypeScript..."
npm run compile

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Open VS Code"
echo "2. Press F5 to launch the extension in debug mode"
echo "3. The server should auto-start and index your project"
