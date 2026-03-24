#!/usr/bin/env bash
# =============================================================================
# HackEmpire X — Setup Script (Kali Linux / Debian-based)
# Handles PEP 668 externally-managed-environment by using a venv.
# Made by Chandan Pandey
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Resolve project root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo -e "${RED}"
cat << 'EOF'
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __   ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
  HackEmpire X — Setup Script (venv-based, Kali Linux safe)
EOF
echo -e "${NC}"

# ---------------------------------------------------------------------------
# 1. Python version check
# ---------------------------------------------------------------------------
info "Checking Python version..."
PYTHON=$(command -v python3 || command -v python || true)
[ -z "$PYTHON" ] && error "Python 3 not found. Install with: sudo apt install python3"

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    error "Python $PY_VER detected. HackEmpire X requires Python >= 3.11."
fi
success "Python $PY_VER — OK"

# ---------------------------------------------------------------------------
# 2. Ensure python3-venv is available (Kali may need it)
# ---------------------------------------------------------------------------
info "Checking python3-venv..."
if ! "$PYTHON" -m venv --help &>/dev/null; then
    warn "python3-venv not found. Installing..."
    sudo apt-get install -y python3-venv python3-pip || error "Failed to install python3-venv."
fi
success "python3-venv — OK"

# ---------------------------------------------------------------------------
# 3. Create virtual environment
# ---------------------------------------------------------------------------
if [ -d "$VENV_DIR" ]; then
    info "Virtual environment already exists at .venv — skipping creation."
else
    info "Creating virtual environment at .venv ..."
    "$PYTHON" -m venv "$VENV_DIR"
    success "Virtual environment created."
fi

# Activate venv for the rest of this script
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ---------------------------------------------------------------------------
# 4. Upgrade pip inside venv
# ---------------------------------------------------------------------------
info "Upgrading pip inside venv..."
"$VENV_PIP" install --upgrade pip --quiet
success "pip upgraded."

# ---------------------------------------------------------------------------
# 5. Install Python dependencies inside venv
# ---------------------------------------------------------------------------
info "Installing Python dependencies into venv..."
"$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt" --quiet
success "Python packages installed: rich, requests, flask, weasyprint"

# ---------------------------------------------------------------------------
# 6. System tools (optional — user prompted)
# ---------------------------------------------------------------------------
info "Checking system tools..."

install_tool() {
    local tool=$1
    local pkg=$2
    if command -v "$tool" &>/dev/null; then
        success "$tool — already installed"
    else
        warn "$tool not found."
        read -rp "  Install $tool via apt? (y/n): " ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            sudo apt-get install -y "$pkg" && success "$tool installed." || warn "Failed to install $tool."
        else
            warn "$tool skipped. You can install it later with: sudo apt install $pkg"
        fi
    fi
}

install_tool nmap      nmap
install_tool subfinder subfinder
install_tool nuclei    nuclei
install_tool ffuf      ffuf
install_tool whatweb   whatweb

# dirsearch (git clone to /opt)
if [ -f "/opt/dirsearch/dirsearch.py" ]; then
    success "dirsearch — already installed at /opt/dirsearch"
else
    warn "dirsearch not found at /opt/dirsearch/dirsearch.py"
    read -rp "  Clone dirsearch to /opt/dirsearch? (y/n): " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        sudo git clone https://github.com/maurosoria/dirsearch.git /opt/dirsearch && \
            success "dirsearch cloned to /opt/dirsearch." || warn "Failed to clone dirsearch."
    else
        warn "dirsearch skipped."
    fi
fi

# ---------------------------------------------------------------------------
# 7. Create the 'hackempire' launcher script
# ---------------------------------------------------------------------------
info "Creating launcher script..."

LAUNCHER="$SCRIPT_DIR/hackempire"
cat > "$LAUNCHER" << LAUNCHER_EOF
#!/usr/bin/env bash
# HackEmpire X launcher — activates venv automatically
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
source "\$SCRIPT_DIR/.venv/bin/activate"
exec "\$SCRIPT_DIR/.venv/bin/python" "\$SCRIPT_DIR/main.py" "\$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"
success "Launcher created: ./hackempire"

# ---------------------------------------------------------------------------
# 8. Run status check inside venv
# ---------------------------------------------------------------------------
info "Running system status check..."
"$VENV_PYTHON" "$SCRIPT_DIR/main.py" --status || true

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  HackEmpire X setup complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${CYAN}  HOW TO RUN:${NC}"
echo ""
echo -e "  ${YELLOW}Option 1 — Use the launcher (recommended):${NC}"
echo -e "  ${GREEN}  ./hackempire example.com --mode pro${NC}"
echo -e "  ${GREEN}  ./hackempire example.com --mode pro --web${NC}"
echo -e "  ${GREEN}  ./hackempire --status${NC}"
echo ""
echo -e "  ${YELLOW}Option 2 — Activate venv manually then use python:${NC}"
echo -e "  ${GREEN}  source .venv/bin/activate${NC}"
echo -e "  ${GREEN}  python main.py example.com --mode pro${NC}"
echo ""
echo -e "  ${YELLOW}Option 3 — Direct venv python (no activation needed):${NC}"
echo -e "  ${GREEN}  .venv/bin/python main.py example.com --mode pro${NC}"
echo ""
