#!/usr/bin/env bash
# =============================================================================
# HackEmpire X — Full Auto-Install Setup (Kali Linux / Debian)
# Installs ALL tools automatically — no prompts, no skips.
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ERR]${NC}   $*"; }
section() { echo -e "\n${BOLD}${GREEN}━━━ $* ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
GOPATH="${GOPATH:-$HOME/go}"
export PATH="$PATH:$GOPATH/bin:/usr/local/go/bin"

# Banner
echo -e "${RED}"
cat << 'BANNER'
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗███╗   ███╗██████╗ ██╗██████╗ ███████╗    ██╗  ██╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝████╗ ████║██╔══██╗██║██╔══██╗██╔════╝    ╚██╗██╔╝
 ███████║███████║██║     █████╔╝ █████╗  ██╔████╔██║██████╔╝██║██████╔╝█████╗       ╚███╔╝
 ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██║██╔══██╗██╔══╝       ██╔██╗
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║ ╚═╝ ██║██║     ██║██║  ██║███████╗    ██╔╝ ██╗
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝
BANNER
echo -e "${NC}"
echo -e "${CYAN}  Full Auto-Install — All tools, no prompts${NC}\n"

# ── 1. Python check ──────────────────────────────────────────────────────────
section "Python"
PYTHON=$(command -v python3 || true)
[ -z "$PYTHON" ] && { err "python3 not found. Run: sudo apt install python3"; exit 1; }
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
[ "$PY_MINOR" -lt 11 ] && { err "Python $PY_VER found. Need >= 3.11"; exit 1; }
ok "Python $PY_VER"

# ── 2. System dependencies ───────────────────────────────────────────────────
section "System packages"
DEBIAN_FRONTEND=noninteractive sudo apt-get update -qq
DEBIAN_FRONTEND=noninteractive sudo apt-get install -y --no-install-recommends \
  git curl wget unzip tar build-essential python3-venv python3-pip \
  nmap nikto whatweb ffuf feroxbuster amass wafw00f \
  libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
  libcairo2 libgdk-pixbuf2.0-0 libffi-dev libxml2-dev libxslt1-dev \
  tor proxychains4 golang-go 2>/dev/null || warn "Some apt packages may have failed"
ok "System packages done"

# ── 3. Go tools ──────────────────────────────────────────────────────────────
section "Go tools"
install_go_tool() {
  local name=$1 pkg=$2
  if command -v "$name" &>/dev/null; then ok "$name already installed"; return; fi
  info "Installing $name..."
  go install "$pkg" 2>/dev/null && ok "$name installed" || warn "$name failed"
}
install_go_tool subfinder   github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
install_go_tool httpx       github.com/projectdiscovery/httpx/cmd/httpx@latest
install_go_tool dnsx        github.com/projectdiscovery/dnsx/cmd/dnsx@latest
install_go_tool shuffledns  github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest
install_go_tool nuclei      github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
install_go_tool katana      github.com/projectdiscovery/katana/cmd/katana@latest
install_go_tool hakrawler   github.com/hakluke/hakrawler@latest
install_go_tool gospider    github.com/jaeles-project/gospider@latest
install_go_tool dalfox      github.com/hahwul/dalfox/v2@latest
install_go_tool gau         github.com/lc/gau/v2/cmd/gau@latest
install_go_tool waybackurls github.com/tomnomnom/waybackurls@latest
install_go_tool cariddi     github.com/edoardottt/cariddi/cmd/cariddi@latest
install_go_tool trufflehog  github.com/trufflesecurity/trufflehog/v3@latest
install_go_tool jsluice     github.com/BishopFox/jsluice/cmd/jsluice@latest
install_go_tool afrog       github.com/zan8in/afrog/cmd/afrog@latest
install_go_tool kr          github.com/assetnote/kiterunner/cmd/kr@latest
install_go_tool github-subdomains github.com/gwen001/github-subdomains@latest

# ── 4. Git-cloned tools ──────────────────────────────────────────────────────
section "Git tools"
clone_tool() {
  local name=$1 repo=$2 dest=$3
  if [ -d "$dest" ]; then ok "$name already at $dest"; return; fi
  info "Cloning $name..."
  sudo git clone --depth=1 "$repo" "$dest" 2>/dev/null && ok "$name cloned" || warn "$name clone failed"
}
clone_tool dirsearch  https://github.com/maurosoria/dirsearch.git    /opt/dirsearch
clone_tool xsstrike   https://github.com/s0md3v/XSStrike.git         /opt/xsstrike
clone_tool commix     https://github.com/commixproject/commix.git    /opt/commix
clone_tool testssl    https://github.com/drwetter/testssl.sh.git     /opt/testssl
clone_tool peass      https://github.com/carlospolop/PEASS-ng.git    /opt/peass
clone_tool sqlmap     https://github.com/sqlmapproject/sqlmap.git    /opt/sqlmap

# Add /opt/sqlmap to PATH if sqlmap not already available
if ! command -v sqlmap &>/dev/null && [ -f /opt/sqlmap/sqlmap.py ]; then
  sudo ln -sf /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap
  sudo chmod +x /usr/local/bin/sqlmap
  ok "sqlmap linked to /usr/local/bin/sqlmap"
fi

# ── 5. Python venv + deps ────────────────────────────────────────────────────
section "Python venv"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON" -m venv "$VENV_DIR" && ok "venv created at .venv"
else
  ok "venv already exists"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
ok "Python deps installed"

# ── 6. Pip-based tools in isolated venvs ────────────────────────────────────
section "Pip tools (isolated venvs)"
VENV_BASE="$HOME/.hackempire/venvs"
mkdir -p "$VENV_BASE"

install_pip_venv() {
  local name=$1; shift; local pkgs=("$@")
  local venv_dir="$VENV_BASE/$name"
  if [ -f "$venv_dir/bin/python" ]; then ok "$name venv already exists"; return; fi
  info "Creating venv for $name..."
  python3 -m venv "$venv_dir" 2>/dev/null || { warn "venv for $name failed"; return; }
  "$venv_dir/bin/pip" install --quiet "${pkgs[@]}" 2>/dev/null && ok "$name installed in venv" || warn "$name pip install failed"
}

install_pip_venv arjun       arjun
install_pip_venv paramspider paramspider
install_pip_venv ghauri      ghauri
install_pip_venv impacket    impacket
install_pip_venv crackmapexec crackmapexec
install_pip_venv bloodhound  bloodhound
install_pip_venv xsstrike    requests fuzzywuzzy
install_pip_venv sqlmap      sqlmap

# ── 7. Launcher script ───────────────────────────────────────────────────────
section "Launcher"
LAUNCHER="$SCRIPT_DIR/hackempire"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$PATH:$HOME/go/bin:/usr/local/go/bin"
source "$SCRIPT_DIR/.venv/bin/activate"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py" "$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"
ok "Launcher: ./hackempire"

# ── 8. Status check ──────────────────────────────────────────────────────────
section "Status"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" --status 2>/dev/null || true

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        HackEmpire X — Setup Complete!                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}  USAGE:${NC}"
echo -e "  ${YELLOW}./hackempire scan example.com --mode full${NC}"
echo -e "  ${YELLOW}./hackempire scan example.com --mode stealth --web${NC}"
echo -e "  ${YELLOW}./hackempire --doctor${NC}   ← fix missing tools"
echo -e "  ${YELLOW}./hackempire --status${NC}   ← check tool health"
echo ""
