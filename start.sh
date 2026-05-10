#!/usr/bin/env bash
# start.sh — Gas Turbine Engine Simulator startup script
# Run from the project root: ./start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "========================================"
echo "  Gas Turbine Engine Simulator"
echo "========================================"
echo ""

# ── Check Python ───────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.10+."
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PYTHON_VERSION"

# ── Check Cantera ──────────────────────────────────────────────────────────────
if ! python3 -c "import cantera" &>/dev/null; then
  echo ""
  echo "WARNING: Cantera not found in current Python environment."
  echo "  Option A (pip):   pip install cantera==3.0.0"
  echo "  Option B (conda): conda install -c conda-forge cantera=3.0.0"
  echo ""
  echo "  The TURBOFAN model will still work without Cantera."
  echo "  See SETUP_GUIDE.md for full instructions."
  echo ""
fi

# ── Check CF34 deck ────────────────────────────────────────────────────────────
DECK="$PROJECT_DIR/data/CF34_deck_v4.csv"
if [ ! -f "$DECK" ]; then
  echo "WARNING: CF34 deck not found at data/CF34_deck_v4.csv"
  echo "  Turbofan interpolation will not work."
  echo "  Copy CF34_deck_v4.csv from the repository into the data/ folder."
  echo ""
fi

# ── Start backend ──────────────────────────────────────────────────────────────
echo "Starting FastAPI backend on http://localhost:8000 ..."
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Open frontend/index.html in your browser to use the simulator."
echo "  Press CTRL+C to stop."
echo ""

cd "$BACKEND_DIR"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
