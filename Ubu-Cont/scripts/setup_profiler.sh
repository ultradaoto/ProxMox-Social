#!/bin/bash
# Profiler Setup Script
# =====================
# Sets up the behavioral profiler environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================="
echo "  Behavioral Profiler Setup"
echo "=================================="
echo

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.8+ required"
    exit 1
fi

# Create virtual environment if needed
if [[ ! -d "$PROJECT_ROOT/venv" ]]; then
    echo
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_ROOT/venv"
fi

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Install dependencies
echo
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/requirements.txt"

# Create directories
echo
echo "Creating directory structure..."
mkdir -p "$PROJECT_ROOT/recordings/sessions"
mkdir -p "$PROJECT_ROOT/recordings/calibrations"
mkdir -p "$PROJECT_ROOT/profiles"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/exports"

# Check for optional dependencies
echo
echo "Checking optional dependencies..."

if python3 -c "import pynput" 2>/dev/null; then
    echo "  ✓ pynput (input capture)"
else
    echo "  ✗ pynput - install for input capture"
fi

if python3 -c "import pygame" 2>/dev/null; then
    echo "  ✓ pygame (VNC display)"
else
    echo "  ✗ pygame - install for VNC passthrough"
fi

if python3 -c "import scipy" 2>/dev/null; then
    echo "  ✓ scipy (curve fitting)"
else
    echo "  ✗ scipy - install for statistical analysis"
fi

if python3 -c "import matplotlib" 2>/dev/null; then
    echo "  ✓ matplotlib (visualization)"
else
    echo "  ✗ matplotlib - install for visualizations"
fi

# Check environment variables
echo
echo "Checking environment..."

if [[ -n "$OPENROUTER_API_KEY" ]]; then
    echo "  ✓ OPENROUTER_API_KEY is set"
else
    echo "  ✗ OPENROUTER_API_KEY not set"
    echo "    Set with: export OPENROUTER_API_KEY=your_key"
fi

if [[ -n "$VNC_PASSWORD" ]]; then
    echo "  ✓ VNC_PASSWORD is set"
else
    echo "  ✗ VNC_PASSWORD not set (optional)"
fi

# Create sample config if not exists
if [[ ! -f "$PROJECT_ROOT/config/profiler_config.yaml" ]]; then
    echo
    echo "Note: config/profiler_config.yaml exists with defaults"
fi

echo
echo "=================================="
echo "  Setup Complete!"
echo "=================================="
echo
echo "Quick Start:"
echo "  1. Activate environment:"
echo "     source venv/bin/activate"
echo
echo "  2. Run calibration:"
echo "     python -m src.profiler calibrate --user $USER"
echo
echo "  3. Start recording:"
echo "     python -m src.profiler record -d 'My first session'"
echo
echo "  4. Generate profile:"
echo "     python -m src.profiler generate --user $USER"
echo
echo "For more help:"
echo "  python -m src.profiler --help"
echo
