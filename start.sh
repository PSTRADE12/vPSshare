#!/usr/bin/env bash
# ==============================================================================
#  vPS Share — One-Click Launcher for Linux & macOS
#  VPS file explorer and file transfer tool by PSTECH
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Locate Python 3 across Linux & macOS environments
if [ -f "$DIR/venv/bin/python3" ]; then
    PYTHON="$DIR/venv/bin/python3"
elif [ -f "$DIR/.venv/bin/python3" ]; then
    PYTHON="$DIR/.venv/bin/python3"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    # macOS Apple Silicon
    PYTHON="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    # macOS Intel / Linux /usr/local
    PYTHON="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    echo "[Error] Python 3 was not found! Please install Python 3.8+ on your system."
    exit 1
fi

# 2. Check minimal dependencies
if ! "$PYTHON" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[vPS Share] Installing required packages from requirements.txt..."
    "$PYTHON" -m pip install -r requirements.txt
fi

# 3. Launch application
exec "$PYTHON" "$DIR/run.py" "$@"
