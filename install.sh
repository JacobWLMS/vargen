#!/bin/bash
set -e

INSTALL_DIR="${VARGEN_DIR:-$HOME/vargen}"
VENV_DIR="$INSTALL_DIR/venv"
REPO="https://github.com/JacobWLMS/vargen.git"

echo "==================================="
echo "  vargen installer"
echo "==================================="
echo ""
echo "Install dir: $INSTALL_DIR"
echo ""

# System deps
echo "[1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git curl nodejs npm > /dev/null 2>&1
echo "  done."

# Clone/update
echo "[2/6] Getting vargen..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull --quiet
    echo "  updated."
else
    git clone --quiet "$REPO" "$INSTALL_DIR"
    echo "  cloned."
fi
cd "$INSTALL_DIR"

# Python venv
echo "[3/6] Setting up Python backend..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install --quiet -r requirements.txt
pip install --quiet spandrel
echo "  done."

# Frontend
echo "[4/6] Building Nuxt frontend..."
cd "$INSTALL_DIR/frontend"
npm install --silent 2>/dev/null
API_BASE="http://localhost:8188" npx nuxt generate 2>/dev/null
echo "  done."

# Output dirs
echo "[5/6] Creating directories..."
mkdir -p "$INSTALL_DIR/outputs" "$INSTALL_DIR/uploads"

# Launcher
echo "[6/6] Creating launcher..."
cat > "$INSTALL_DIR/start.sh" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python -m vargen --host 0.0.0.0 --port 8188 "$@"
LAUNCHER
chmod +x "$INSTALL_DIR/start.sh"

# Dev launcher (runs backend + frontend hot-reload)
cat > "$INSTALL_DIR/dev.sh" << 'DEVLAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
# Backend on 8188, frontend dev server on 3000
python -m vargen --host 0.0.0.0 --port 8188 --dev &
BACKEND_PID=$!
cd frontend && API_BASE="http://localhost:8188" npx nuxt dev --port 3000 &
FRONTEND_PID=$!
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
DEVLAUNCHER
chmod +x "$INSTALL_DIR/dev.sh"

echo ""
echo "==================================="
echo "  vargen installed!"
echo "==================================="
echo ""
echo "  Production:  $INSTALL_DIR/start.sh"
echo "               → http://localhost:8188"
echo ""
echo "  Development: $INSTALL_DIR/dev.sh"
echo "               → Backend: http://localhost:8188"
echo "               → Frontend: http://localhost:3000"
echo ""
echo "  Auto-detects ~/ComfyUI/models/ if present."
echo ""
