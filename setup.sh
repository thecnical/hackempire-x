#!/usr/bin/env bash
# =============================================================================
# HackEmpire X — Setup Script (Kali Linux / Debian-based)
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

echo -e "${RED}"
cat << 'EOF'
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __   ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
  HackEmpire X — Setup Script
EOF
echo -e "${NC}"

# ---------------------------------------------------------------------------
# 1. Python version check
# ---------------------------------------------------------------------------
info "Checking Python version..."
PYTHON=$(command -v python3 || command -v python || true)
[ -z "$PYTHON" ] && error "Python 3 not found. Install Python 3.11+ first."

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    error "Python $PY_VER detected. HackEmpire X requires Python >= 3.11."
fi
success "Python $PY_VER — OK"

# ---------------------------------------------------------------------------
# 2. pip packages
# ---------------------------------------------------------------------------
info "Installing Python dependencies..."
"$PYTHON" -m pip install --upgrade pip --quiet
"$PYTHON" -m pip install -r requirements.txt --quiet
success "Python packages installed."

# ---------------------------------------------------------------------------
# 3. System tools (optional — user prompted)
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
            warn "$tool skipped."
        fi
    fi
}

install_tool nmap       nmap
install_tool subfinder  subfinder
install_tool nuclei     nuclei
install_tool ffuf       ffuf

# dirsearch (git clone)
if [ ! -f "/opt/dirsearch/dirsearch.py" ]; then
    warn "dirsearch not found at /opt/dirsearch/dirsearch.py"
    read -rp "  Clone dirsearch to /opt/dirsearch? (y/n): " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        sudo git clone https://github.com/maurosoria/dirsearch.git /opt/dirsearch && \
            success "dirsearch cloned." || warn "Failed to clone dirsearch."
    fi
else
    success "dirsearch — already installed"
fi

# ---------------------------------------------------------------------------
# 4. Verify
# ---------------------------------------------------------------------------
info "Running system status check..."
"$PYTHON" main.py --status || true

echo ""
success "HackEmpire X setup complete!"
echo -e "${CYAN}  Run: python main.py <target> --mode pro${NC}"
echo -e "${CYAN}  Run: python main.py <target> --mode pro --web${NC}"
echo ""
