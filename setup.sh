#!/usr/bin/env bash
set -e

echo "🎵 Setting up Taghag 🎵"

echo "--> 1/2: Setting up Python backend (taghag_import) via Poetry..."
cd tools
if ! command -v poetry &> /dev/null; then
    echo "❌ Error: poetry is not installed. Please install it first: https://python-poetry.org/docs/"
    exit 1
fi

poetry install
cd ..

echo "--> 2/2: Checking environment variables..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "⚠️  Created .env from .env.example. Please review and fill in missing values."
    else
        echo "⚠️  No .env.example found to copy."
    fi
else
    echo "✅ .env already exists."
fi

echo ""
echo "✅ Setup complete for taghag!"
