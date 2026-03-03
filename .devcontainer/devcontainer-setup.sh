#!/bin/bash
# Development container initialization script for pyPhoTimeline
# Installs UV, uv-deps-switcher tool, and sets up Python environment with fallback strategy

set -e

echo "======================================================================"
echo "pyPhoTimeline Dev Container Setup"
echo "======================================================================"

# Colors for output (safe for agents)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

# 1. Ensure UV is installed
log_info "Checking UV package manager..."
if ! command -v uv &> /dev/null; then
    log_info "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    log_success "UV installed"
else
    log_success "UV is already installed at $(which uv)"
fi

# 2. Install uv-deps-switcher tool if not present
log_info "Checking uv-deps-switcher..."
if ! command -v uv-deps-switcher &> /dev/null; then
    log_info "Installing uv-deps-switcher from GitHub..."
    uv tool install git+https://github.com/PhoPersonalOrg/uv-deps-switcher.git
    log_success "uv-deps-switcher installed"
else
    log_success "uv-deps-switcher is already installed"
fi

# 3. Attempt dependency configuration with fallback strategy
log_info "Configuring dependencies (dev mode preferred, falls back to release)..."

# Try dev mode first (assumes sibling repos exist: ../pyPhoCoreHelpers, ../PhoPyLSLhelper, ../PhoPyMNEHelper)
if uv-deps-switcher dev 2>/dev/null; then
    log_success "Dev mode activated (using local sibling repos)"
else
    log_warning "Dev mode failed - sibling repos not found, switching to release mode"
    if uv-deps-switcher release 2>/dev/null; then
        log_success "Release mode activated (using GitHub dependencies)"
    else
        log_error "Both dev and release modes failed. Check configuration."
        exit 1
    fi
fi

# 4. Sync and install all dependencies
log_info "Syncing dependencies with uv..."
uv sync --all-extras
log_success "Dependencies synced"

# 5. Verify Python environment
VENV_PYTHON=".venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_VERSION=$($VENV_PYTHON --version)
    log_success "Python environment ready: $PYTHON_VERSION"
else
    log_error "Expected Python not found at $VENV_PYTHON"
    exit 1
fi

# 6. Initialize shell activation script (helpful for subshells)
if [ -f ".venv/bin/activate" ]; then
    log_success "Virtual environment activation script ready at .venv/bin/activate"
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}Dev environment setup complete!${NC}"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. To activate the environment in your shell:"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Run the main application:"
echo "     python -m pypho_timeline"
echo ""
echo "  3. Run tests:"
echo "     python -m unittest discover -s tests -p 'test_*.py'"
echo ""
echo "  4. Switch dependency modes:"
echo "     uv-deps-switcher dev    # Local development"
echo "     uv-deps-switcher release # Published packages"
echo ""
