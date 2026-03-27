#!/usr/bin/env bash
# =============================================================================
# HackEmpire X v4 — Full Auto-Install Setup (Kali Linux / Debian)
# Installs ALL v3 + v4 tools automatically — no prompts, no skips.
#
# v4 additions:
#   theHarvester, recon-ng, dnsenum, fierce
#   wpscan, wpprobe, joomscan
#   sstimap, zaproxy, semgrep
#   metasploit (msfconsole), ysoserial, certipy-ad
#   adaptix-c2, atomic-operator, pypykatz, pspy, evil-winrm
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
export PATH="$PATH:$GOPATH/bin:/usr/local/go/bin:$HOME/.local/bin"

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
echo -e "${CYAN}  HackEmpire X v4 — Full Auto-Install (all tools, no prompts)${NC}\n"

# ── 1. Python check ──────────────────────────────────────────────────────────
section "Python"
PYTHON=$(command -v python3 || true)
[ -z "$PYTHON" ] && { err "python3 not found. Run: sudo apt install python3"; exit 1; }
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
[ "$PY_MINOR" -lt 11 ] && { err "Python $PY_VER found. Need >= 3.11"; exit 1; }
ok "Python $PY_VER"

# ── 2. System packages ───────────────────────────────────────────────────────
section "System packages"
DEBIAN_FRONTEND=noninteractive sudo apt-get update -qq
DEBIAN_FRONTEND=noninteractive sudo apt-get install -y --no-install-recommends \
  git curl wget unzip tar build-essential python3-venv python3-pip \
  nmap nikto whatweb ffuf feroxbuster amass wafw00f gobuster wfuzz smbmap \
  sqlmap masscan enum4linux \
  theharvester dnsenum fierce wpscan joomscan zaproxy \
  metasploit-framework \
  ruby ruby-dev \
  libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
  libcairo2 libgdk-pixbuf2.0-0 libffi-dev libxml2-dev libxslt1-dev \
  libpcap-dev \
  tor proxychains4 golang-go \
  default-jre-headless \
  2>/dev/null || warn "Some apt packages may have failed — continuing"
ok "System packages done"

# ── 3. Go tools ──────────────────────────────────────────────────────────────
section "Go tools"
mkdir -p "$HOME/.local/bin"

install_go_tool() {
  local name=$1 pkg=$2
  if command -v "$name" &>/dev/null; then ok "$name already installed"; return; fi
  info "Installing $name..."
  go install "$pkg" 2>/dev/null && ok "$name installed" || warn "$name failed (non-fatal)"
}

install_go_tool subfinder         github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
install_go_tool httpx             github.com/projectdiscovery/httpx/cmd/httpx@latest
install_go_tool dnsx              github.com/projectdiscovery/dnsx/cmd/dnsx@latest
install_go_tool shuffledns        github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest
install_go_tool nuclei            github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
install_go_tool katana            github.com/projectdiscovery/katana/cmd/katana@latest
install_go_tool hakrawler         github.com/hakluke/hakrawler@latest
install_go_tool gospider          github.com/jaeles-project/gospider@latest
install_go_tool dalfox            github.com/hahwul/dalfox/v2@latest
install_go_tool gau               github.com/lc/gau/v2/cmd/gau@latest
install_go_tool waybackurls       github.com/tomnomnom/waybackurls@latest
install_go_tool cariddi           github.com/edoardottt/cariddi/cmd/cariddi@latest
install_go_tool afrog             github.com/zan8in/afrog/cmd/afrog@latest
install_go_tool jsluice           github.com/BishopFox/jsluice/cmd/jsluice@latest
install_go_tool kr                github.com/assetnote/kiterunner/cmd/kr@latest
install_go_tool github-subdomains github.com/gwen001/github-subdomains@latest
install_go_tool naabu             github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
install_go_tool interactsh-client github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest
install_go_tool chisel            github.com/jpillora/chisel@latest
install_go_tool assetfinder       github.com/tomnomnom/assetfinder@latest
install_go_tool anew              github.com/tomnomnom/anew@latest
install_go_tool qsreplace         github.com/tomnomnom/qsreplace@latest

# ligolo-ng proxy
if ! command -v proxy &>/dev/null; then
  info "Installing ligolo-ng..."
  go install github.com/nicocha30/ligolo-ng/cmd/proxy@latest 2>/dev/null && ok "ligolo-ng installed" || warn "ligolo-ng failed"
fi

# trufflehog — use official install script (needs Go >= 1.24)
if ! command -v trufflehog &>/dev/null; then
  info "Installing trufflehog via binary release..."
  curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \
    | sudo sh -s -- -b /usr/local/bin 2>/dev/null && ok "trufflehog installed" || warn "trufflehog failed"
fi

# ── 4. Git-cloned tools ──────────────────────────────────────────────────────
section "Git tools"
clone_tool() {
  local name=$1 repo=$2 dest=$3
  if [ -d "$dest" ]; then ok "$name already at $dest"; return; fi
  info "Cloning $name..."
  sudo git clone --depth=1 "$repo" "$dest" 2>/dev/null && ok "$name cloned" || warn "$name clone failed"
}

# v3 git tools
clone_tool dirsearch   https://github.com/maurosoria/dirsearch.git    /opt/dirsearch
clone_tool xsstrike    https://github.com/s0md3v/XSStrike.git         /opt/xsstrike
clone_tool commix      https://github.com/commixproject/commix.git    /opt/commix
clone_tool tplmap      https://github.com/epinna/tplmap.git           /opt/tplmap
clone_tool testssl     https://github.com/drwetter/testssl.sh.git     /opt/testssl
clone_tool peass       https://github.com/carlospolop/PEASS-ng.git    /opt/peass
clone_tool ghauri      https://github.com/r0oth3x49/ghauri.git        /opt/ghauri
clone_tool paramspider https://github.com/devanshbatham/ParamSpider.git /opt/paramspider
clone_tool sqlmap-git  https://github.com/sqlmapproject/sqlmap.git    /opt/sqlmap

# v4 git tools
clone_tool sstimap     https://github.com/vladko312/SSTImap.git       /opt/sstimap
clone_tool adaptix-c2  https://github.com/Adaptix-Framework/AdaptixC2.git /opt/adaptix-c2

# sqlmap symlink
if ! command -v sqlmap &>/dev/null && [ -f /opt/sqlmap/sqlmap.py ]; then
  sudo ln -sf /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap
  sudo chmod +x /usr/local/bin/sqlmap
  ok "sqlmap linked to /usr/local/bin/sqlmap"
fi

# ── 5. Python venv + core deps ───────────────────────────────────────────────
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

# ── 6. Pip tools in isolated venvs ──────────────────────────────────────────
section "Pip tools (isolated venvs)"
VENV_BASE="$HOME/.hackempire/venvs"
mkdir -p "$VENV_BASE"

install_pip_venv() {
  local name=$1; shift; local pkgs=("$@")
  local venv_dir="$VENV_BASE/$name"
  if [ -f "$venv_dir/bin/python" ]; then ok "$name venv already exists"; return; fi
  info "Creating venv for $name..."
  python3 -m venv "$venv_dir" 2>/dev/null || { warn "venv for $name failed"; return; }
  "$venv_dir/bin/pip" install --quiet "${pkgs[@]}" 2>/dev/null \
    && ok "$name installed in venv" || warn "$name pip install failed (non-fatal)"
}

# v3 pip tools
install_pip_venv arjun          arjun
install_pip_venv waymore        waymore
install_pip_venv sslyze         sslyze
install_pip_venv impacket       impacket
install_pip_venv netexec        netexec
install_pip_venv bloodhound     bloodhound
install_pip_venv ldapdomaindump ldapdomaindump
install_pip_venv xsstrike       requests fuzzywuzzy

# v4 pip tools
install_pip_venv semgrep        semgrep
install_pip_venv pypykatz       pypykatz
install_pip_venv certipy-ad     certipy-ad
install_pip_venv atomic-operator atomic-operator
install_pip_venv recon-ng       recon-ng
install_pip_venv wpprobe        wpprobe

# Install requirements for git-cloned tools
for tool_dir in /opt/ghauri /opt/paramspider /opt/commix /opt/tplmap /opt/xsstrike /opt/sstimap; do
  if [ -f "$tool_dir/requirements.txt" ]; then
    name=$(basename "$tool_dir")
    info "Installing requirements for $name..."
    python3 -m venv "$VENV_BASE/$name" 2>/dev/null || true
    "$VENV_BASE/$name/bin/pip" install --quiet -r "$tool_dir/requirements.txt" 2>/dev/null \
      && ok "$name deps installed" || warn "$name deps failed (non-fatal)"
  fi
done

# Symlink venv binaries to ~/.local/bin
for tool_bin in arjun waymore sslyze nxc bloodhound-python impacket-secretsdump ldapdomaindump \
                semgrep pypykatz certipy atomic-operator recon-ng wpprobe; do
  for venv_dir in "$VENV_BASE"/*/; do
    bin_path="$venv_dir/bin/$tool_bin"
    if [ -f "$bin_path" ]; then
      ln -sf "$bin_path" "$HOME/.local/bin/$tool_bin" 2>/dev/null && ok "Linked $tool_bin" || true
      break
    fi
  done
done

# ── 7. Gem tools ─────────────────────────────────────────────────────────────
section "Gem tools"
if command -v gem &>/dev/null; then
  if ! command -v evil-winrm &>/dev/null; then
    info "Installing evil-winrm..."
    sudo gem install evil-winrm 2>/dev/null && ok "evil-winrm installed" || warn "evil-winrm failed (non-fatal)"
  else
    ok "evil-winrm already installed"
  fi
else
  warn "ruby/gem not found — skipping evil-winrm"
fi

# ── 8. Curl binary downloads ─────────────────────────────────────────────────
section "Binary downloads"

# ysoserial JAR
if [ ! -f /opt/ysoserial/ysoserial.jar ]; then
  info "Downloading ysoserial JAR..."
  sudo mkdir -p /opt/ysoserial
  sudo curl -sSL \
    "https://github.com/frohoff/ysoserial/releases/latest/download/ysoserial-all.jar" \
    -o /opt/ysoserial/ysoserial.jar 2>/dev/null && ok "ysoserial downloaded" || warn "ysoserial download failed"
  if [ -f /opt/ysoserial/ysoserial.jar ]; then
    sudo tee /usr/local/bin/ysoserial > /dev/null << 'WRAPPER'
#!/usr/bin/env bash
exec java -jar /opt/ysoserial/ysoserial.jar "$@"
WRAPPER
    sudo chmod +x /usr/local/bin/ysoserial
    ok "ysoserial wrapper created"
  fi
else
  ok "ysoserial already at /opt/ysoserial/ysoserial.jar"
fi

# pspy64 binary
if ! command -v pspy64 &>/dev/null && ! command -v pspy &>/dev/null; then
  info "Downloading pspy64..."
  sudo curl -sSL \
    "https://github.com/DominicBreuker/pspy/releases/latest/download/pspy64" \
    -o /usr/local/bin/pspy64 2>/dev/null && ok "pspy64 downloaded" || warn "pspy64 download failed"
  [ -f /usr/local/bin/pspy64 ] && sudo chmod +x /usr/local/bin/pspy64
else
  ok "pspy already installed"
fi

# ── 9. Wrapper scripts for git tools ─────────────────────────────────────────
section "Tool wrappers"
create_wrapper() {
  local name=$1 script=$2
  local wrapper="/usr/local/bin/$name"
  if command -v "$name" &>/dev/null; then ok "$name already on PATH"; return; fi
  if [ ! -f "$script" ]; then warn "$script not found — skipping wrapper"; return; fi
  sudo tee "$wrapper" > /dev/null << WRAPPER
#!/usr/bin/env bash
exec python3 "$script" "\$@"
WRAPPER
  sudo chmod +x "$wrapper"
  ok "Wrapper created: $name → $script"
}

create_wrapper dirsearch   /opt/dirsearch/dirsearch.py
create_wrapper xsstrike    /opt/xsstrike/xsstrike.py
create_wrapper tplmap      /opt/tplmap/tplmap.py
create_wrapper ghauri      /opt/ghauri/ghauri.py
create_wrapper paramspider /opt/paramspider/paramspider.py
create_wrapper sstimap     /opt/sstimap/sstimap.py

# testssl.sh wrapper
if [ -f /opt/testssl/testssl.sh ] && ! command -v testssl &>/dev/null; then
  sudo ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl
  sudo chmod +x /usr/local/bin/testssl
  ok "testssl linked"
fi

# ── 10. Launcher script ──────────────────────────────────────────────────────
section "Launcher"
LAUNCHER="$SCRIPT_DIR/hackempire"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$PATH:$HOME/go/bin:/usr/local/go/bin:$HOME/.local/bin"
source "$SCRIPT_DIR/.venv/bin/activate"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py" "$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"
ok "Launcher: ./hackempire"

# ── 11. Status check ─────────────────────────────────────────────────────────
section "Status"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" --status 2>/dev/null || true

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          HackEmpire X v4 — Setup Complete!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}  USAGE:${NC}"
echo -e "  ${YELLOW}./hackempire scan example.com --mode full${NC}"
echo -e "  ${YELLOW}./hackempire scan example.com --mode ultra --web${NC}          ← v4 full power"
echo -e "  ${YELLOW}./hackempire scan example.com --mode ultra --autonomous${NC}   ← v4.2 autonomous"
echo -e "  ${YELLOW}./hackempire scan example.com --mode stealth --web${NC}"
echo -e "  ${YELLOW}./hackempire --doctor${NC}                                     ← fix missing tools"
echo -e "  ${YELLOW}./hackempire --status${NC}                                     ← check tool health"
echo -e "  ${YELLOW}./hackempire config bytez_key YOUR_KEY${NC}                    ← set Bytez AI key"
echo -e "  ${YELLOW}./hackempire config openrouter_key YOUR_KEY${NC}               ← set OpenRouter key"
echo ""
echo -e "${CYAN}  v4 NEW FEATURES:${NC}"
echo -e "  • ModelChain: 5 Bytez free models with 90s budget"
echo -e "  • AutonomousEngine: AI-driven phase decisions"
echo -e "  • RAG Knowledge Base: learns from every scan"
echo -e "  • 20 new tools: sstimap, zaproxy, semgrep, certipy, pypykatz, pspy, ..."
echo -e "  • Dashboard v2: AttackGraph, MITREOverlay, PoCPreview, AutonomousFeed, KBViewer"
echo ""
