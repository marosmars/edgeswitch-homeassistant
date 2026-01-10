#!/bin/bash
# Wrapper script to run tests with virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Check if venv exists, if not create it
if [ ! -d "$VENV_DIR" ]; then
    "$SCRIPT_DIR/setup_test_env.sh"
fi

# Run the test script with venv python
"$VENV_DIR/bin/python" "$SCRIPT_DIR/test_api.py" "$@"
