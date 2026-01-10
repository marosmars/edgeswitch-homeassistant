#!/bin/bash
# Setup script for EdgeSwitch API testing environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Setting up EdgeSwitch test environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate and install dependencies
echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet aiohttp

echo ""
echo "Setup complete!"
echo ""
echo "Usage:"
echo "  source .venv/bin/activate"
echo "  python test_api.py <host> <username> <password>"
echo ""
echo "Examples:"
echo "  python test_api.py 192.168.18.2 ubnt mypassword"
echo "  python test_api.py 192.168.18.2 ubnt mypassword --action poe-off --port 5"
echo "  python test_api.py 192.168.18.2 ubnt mypassword --action poe-on --port 5"
echo ""
