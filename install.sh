#!/bin/bash
set -e

# vargen installer for Debian/Ubuntu
# Usage: curl -sSL https://raw.githubusercontent.com/JacobWLMS/vargen/main/install.sh | bash

INSTALL_DIR="${VARGEN_DIR:-$HOME/vargen}"
VENV_DIR="$INSTALL_DIR/venv"
REPO="https://github.com/JacobWLMS/vargen.git"

echo "==================================="
echo "  vargen installer"
echo "==================================="
echo ""
echo "Install dir: $INSTALL_DIR"
echo ""

# System dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git curl > /dev/null 2>&1
echo "  done."

# Clone or update repo
echo "[2/5] Getting vargen..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --quiet
    echo "  updated existing install."
else
    git clone --quiet "$REPO" "$INSTALL_DIR"
    echo "  cloned fresh."
fi

cd "$INSTALL_DIR"

# Create venv
echo "[3/5] Setting up Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  created venv."
else
    echo "  venv exists."
fi

source "$VENV_DIR/bin/activate"

# Install PyTorch with CUDA
echo "[4/5] Installing PyTorch + dependencies (this takes a minute)..."
pip install --quiet --upgrade pip
pip install --quiet torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install --quiet -r requirements.txt
pip install --quiet spandrel

echo "  done."

# Create launcher
echo "[5/5] Creating launcher..."
cat > "$INSTALL_DIR/start.sh" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python -m vargen --host 0.0.0.0 --port 8188 "$@"
LAUNCHER
chmod +x "$INSTALL_DIR/start.sh"

echo ""
echo "==================================="
echo "  vargen installed!"
echo "==================================="
echo ""
echo "  Start:   $INSTALL_DIR/start.sh"
echo "  Open:    http://localhost:8188"
echo ""
echo "  It auto-detects ~/ComfyUI/models/"
echo "  if present — no need to re-download"
echo "  models you already have."
echo ""
echo "  To update later:  cd $INSTALL_DIR && git pull"
echo ""
