#!/bin/bash
set -e

INSTALL_DIR="${VARGEN_DIR:-$HOME/vargen}"
VENV_DIR="$INSTALL_DIR/venv"
REPO="https://github.com/JacobWLMS/vargen.git"

echo "==================================="
echo "  vargen installer"
echo "==================================="
echo ""

# System deps
echo "[1/6] System dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git curl nodejs npm > /dev/null 2>&1

# Clone/update
echo "[2/6] Getting vargen..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull --quiet
else
    git clone --quiet "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# Python
echo "[3/6] Python backend..."
[ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install --quiet -r requirements.txt
pip install --quiet spandrel

# Frontend
echo "[4/6] Building frontend..."
cd "$INSTALL_DIR/frontend"
npm install --silent 2>/dev/null
npx nuxt generate 2>/dev/null

# Dirs
echo "[5/6] Creating directories..."
mkdir -p "$INSTALL_DIR/outputs" "$INSTALL_DIR/uploads"

# Launcher
echo "[6/6] Creating launcher..."
cat > "$INSTALL_DIR/start.sh" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
if [ ! -d "frontend/.output" ]; then
    echo "Building frontend..."
    cd frontend && npm install --silent 2>/dev/null && npx nuxt generate 2>/dev/null && cd ..
fi
python -m vargen --host 0.0.0.0 --port 8188 "$@"
LAUNCHER
chmod +x "$INSTALL_DIR/start.sh"

echo ""
echo "==================================="
echo "  vargen installed!"
echo "==================================="
echo "  Start:  $INSTALL_DIR/start.sh"
echo "  Open:   http://<your-ip>:8188"
echo ""
