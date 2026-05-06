#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Local Environment Setup Script
# ════════════════════════════════════════════════════════════════

set -e

echo "🚀 Starting PARWA Local Development Setup..."

# 1. Check Python version (requires 3.11+)
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python version $PYTHON_VERSION detected."

# 2. Create Virtual Environment
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv $VENV_DIR
else
    echo "✅ Virtual environment already exists."
fi

# Activate venv for the rest of the script
source $VENV_DIR/bin/activate

# 3. Upgrade pip and install requirements
echo "📥 Installing dependencies from requirements.txt..."
python3 -m pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found! Skipping dependency install."
fi

# 4. Environment Variables
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📝 Copying .env.example to .env..."
        cp .env.example .env
        echo "⚠️ Please review .env and fill in required secrets."
    else
        echo "⚠️ .env.example not found. You must create a .env file manually."
    fi
else
    echo "✅ .env file already exists."
fi

echo ""
echo "🎉 Setup Complete!"
echo "👉 Run 'source venv/bin/activate' to activate your environment."
echo "👉 Run 'docker-compose up -d' to start local infrastructure."
