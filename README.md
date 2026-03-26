<div align="center">

```
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗███╗   ███╗██████╗ ██╗██████╗ ███████╗    ██╗  ██╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝████╗ ████║██╔══██╗██║██╔══██╗██╔════╝    ╚██╗██╔╝
 ███████║███████║██║     █████╔╝ █████╗  ██╔████╔██║██████╔╝██║██████╔╝█████╗       ╚███╔╝
 ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██║██╔══██╗██╔══╝       ██╔██╗
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║ ╚═╝ ██║██║     ██║██║  ██║███████╗    ██╔╝ ██╗
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝
```

**AI-Orchestrated Offensive Security Platform — v2.0**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=linux)](https://kali.org)
[![CI](https://github.com/thecnical/hackempire-x/actions/workflows/ci.yml/badge.svg)](https://github.com/thecnical/hackempire-x/actions)
[![Tests](https://img.shields.io/badge/Tests-84%20passing-brightgreen?style=flat-square)](https://github.com/thecnical/hackempire-x/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tools](https://img.shields.io/badge/Tools-40%2B-red?style=flat-square)](https://github.com/thecnical/hackempire-x)

</div>

---

> **Legal Notice:** HackEmpire X is for **authorized penetration testing and security research only**. Always obtain explicit written permission before scanning any target. Unauthorized use is illegal and unethical. The authors accept no liability for misuse.

---

## What is HackEmpire X?

HackEmpire X is a **full-stack AI-orchestrated offensive security platform** built for bug bounty hunters, red teamers, and penetration testers. It runs a complete **7-phase attack pipeline** — from passive recon to post-exploitation and reporting — with 40+ integrated tools, automatic fallback chains, real-time AI decision making, and a live web dashboard.

One command. Full attack surface coverage.

```bash
./hackempire scan example.com --mode full --web
```

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │           OrchestratorV2                │
                         │                                         │
  Target ──────────────► │  RECON → URL_DISC → ENUM → VULN_SCAN   │
                         │  EXPLOITATION → POST_EXPLOIT → REPORT  │
                         │                                         │
                         │  Each phase: FallbackChain              │
                         │  [tool1→tool2→...→tool6→AegisBridge]   │
                         │                                         │
                         │  AIEngine v2 (OpenRouter LLM)           │
                         │  ├─ TodoPlanner (7×6 task matrix)       │
                         │  ├─ PhaseAnalyzer (per-phase decisions) │
                         │  ├─ ExploitSuggester                    │
                         │  └─ PentestKnowledgeBase (offline KB)   │
                         │                                         │
                         │  WafDetector → WafBypassStrategy        │
                         │  TorManager (stealth via proxychains4)  │
                         │  ToolVenvManager (isolated pip envs)    │
                         └──────────────┬──────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
             Rich CLI (TLS)                    Web Dashboard (HTTPS :5443)
             4 scan modes                      Real-time SocketIO
             5 report formats                  xterm.js terminal
             Doctor + Status                   Chart.js radar map
                                               Live vuln feed
```

---

## Features

### 7-Phase Attack Pipeline

| Phase | Tools |
|-------|-------|
| **RECON** | subfinder, httpx, dnsx, nmap, whatweb, assetfinder |
| **URL_DISCOVERY** | katana, gau, waybackurls, hakrawler, gospider, cariddi |
| **ENUMERATION** | feroxbuster, ffuf, dirsearch, arjun, gobuster, kiterunner |
| **VULN_SCAN** | nuclei, nikto, naabu, afrog, sslyze, interactsh-client |
| **EXPLOITATION** | dalfox, sqlmap, commix, tplmap, ghauri, xsstrike |
| **POST_EXPLOIT** | linpeas, netexec, chisel, ligolo-ng, impacket, bloodhound |
| **REPORTING** | PDF, JSON, HTML, Markdown, CSV |

### FallbackChain — Never Stops
Every phase runs 6 tools in sequence. If a tool fails, times out, or isn't installed, the next one takes over automatically. If all 6 fail, **AegisBridge** runs as a last-resort fallback. The scan never stops due to a single tool failure.

### AI Engine v2
- Generates a **7-phase × 6-task todo matrix** at scan start via OpenRouter LLM
- Analyzes each phase result and decides next steps in real time
- Suggests exploit chains based on discovered vulnerabilities
- Falls back to built-in **PentestKnowledgeBase** (OWASP Top 10, API Security Top 10) when offline
- All tool output is **JSON-parsed before AI prompts** — prompt injection prevention

### WAF Detection & Bypass
- Detects WAF vendor via `wafw00f`
- Per-vendor tamper chains for sqlmap: Cloudflare, Akamai, AWS WAF, Imperva, F5, Sucuri, ModSecurity
- Per-vendor bypass headers for nuclei and HTTP tools
- Automatic fallback to generic bypass

### XSS Methodology
- **Reflected XSS** — dalfox + xsstrike with WAF bypass headers
- **Stored XSS** — form field injection
- **DOM XSS** — jsluice source/sink analysis
- **Blind XSS** — nuclei blind-xss templates
- **CSP Bypass** — JSONP, nonce detection, unsafe-inline/eval
- Full deduplication with tool source merging

### SQLi Methodology
All 7 sqlmap techniques: Boolean, Error, Union, Stacked, Time-based, Inline, Out-of-band. Plus second-order injection, privilege escalation, and OS shell via DBA.

### New Tools (v2.1)
| Tool | Phase | Purpose |
|------|-------|---------|
| **naabu** | VULN_SCAN | Ultra-fast port scanner (ProjectDiscovery) |
| **interactsh-client** | VULN_SCAN | OOB interaction server — blind SSRF/XXE/RCE detection |
| **metasploit** | EXPLOITATION | 2000+ exploits, Meterpreter, post-exploit modules |
| **waymore** | URL_DISCOVERY | Wayback + CommonCrawl + OTX URL harvester |
| **tplmap** | EXPLOITATION | Server-Side Template Injection (SSTI) exploitation |
| **commix** | EXPLOITATION | Automated OS command injection |
| **chisel** | POST_EXPLOIT | Fast TCP tunnel over HTTP for pivoting |
| **ligolo-ng** | POST_EXPLOIT | Reverse tunnel for network pivoting |
| **sslyze** | VULN_SCAN | Deep TLS/SSL configuration analysis |
| **enum4linux-ng** | ENUMERATION | SMB/NetBIOS/Active Directory enumeration |

### Stealth Mode
- Routes all tool traffic through **Tor** via proxychains4
- Rate limited to 2 rps with 500–3000ms random jitter
- Automatic identity rotation via NEWNYM signal

### Isolated Tool Environments
- Each Python-based tool runs in its own **isolated venv** — no dependency conflicts
- Go tools installed via `go install` to `~/go/bin`
- Git-cloned tools get their own venv from their `requirements.txt`
- Pip tools symlinked to `~/.local/bin` for PATH availability

### Real-Time Web Dashboard
- **Live vulnerability feed** via SocketIO with severity color coding
- **Radar chart** showing phase coverage (Chart.js)
- **Phase progress bars** with real-time updates
- **AI Decision Panel** — live AI reasoning per phase
- **Embedded xterm.js terminal** (PTY-backed, full interactive shell)
- Auto-reconnect with state replay on disconnect
- TLS on port 5443 (self-signed cert auto-generated)
- Dynamic hacker UI — Orbitron font, animated grid, scanline overlay

---

## Installation

**Requirements:** Kali Linux (or Debian-based), Python 3.11+, Go 1.21+

```bash
git clone https://github.com/thecnical/hackempire-x.git
cd hackempire-x
chmod +x setup.sh
./setup.sh
```

The setup script automatically:
- Installs all apt packages (nmap, nikto, ffuf, feroxbuster, amass, metasploit, enum4linux-ng, etc.)
- Installs all Go tools (subfinder, httpx, nuclei, naabu, katana, dalfox, chisel, ligolo-ng, etc.)
- Clones all git tools (dirsearch, xsstrike, commix, tplmap, ghauri, paramspider, testssl, linpeas)
- Creates isolated pip venvs (arjun, waymore, sslyze, impacket, netexec, bloodhound)
- Creates the `./hackempire` launcher script

**No prompts. No manual steps. Everything installs automatically.**

---

## Usage

```bash
# Full 7-phase scan
./hackempire scan example.com --mode full

# Full scan + live web dashboard
./hackempire scan example.com --mode full --web

# AI-assisted scan (OpenRouter API key)
./hackempire scan example.com --mode full --ai-key YOUR_KEY --web

# Stealth mode (Tor + rate limiting)
./hackempire scan example.com --mode stealth

# Exploitation mode (requires explicit confirmation)
./hackempire scan example.com --mode exploit

# Resume interrupted scan
./hackempire scan example.com --mode full --resume

# Check tool installation status
./hackempire --status

# Auto-fix all missing tools
./hackempire --doctor

# Export latest scan report
./hackempire report --format pdf
./hackempire report --format json
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `scan <target> --mode full` | Run complete 7-phase pipeline |
| `scan <target> --mode recon-only` | Recon phase only |
| `scan <target> --mode stealth` | Scan via Tor + rate limiting |
| `scan <target> --mode exploit` | Full scan + active exploitation |
| `scan <target> --web` | Launch live dashboard at https://127.0.0.1:5443 |
| `scan <target> --resume` | Resume an interrupted scan |
| `scan <target> --proxy http://127.0.0.1:8080` | Route through Burp Suite |
| `report --format pdf\|json\|html\|markdown\|csv` | Export latest report |
| `install-tools` | Install all 40+ pentest tools |
| `terminal` | Open web terminal in browser |
| `config <key> <value>` | Set config value |
| `--status` | Show tool health status |
| `--doctor` | Diagnose and auto-fix broken tools |
| `--clean` | Clear logs and temp files |
| `--uninstall` | Remove HackEmpire X |

---

## Web Dashboard

Open `https://127.0.0.1:5443` when running with `--web`.

| Route | Description |
|-------|-------------|
| `/dashboard` | Live scan — phase bars, radar chart, vuln feed, AI panel, terminal |
| `/report` | Full vulnerability report with severity and remediation |
| `/logs` | Auto-refreshing log viewer |
| `/api/state` | Raw scan state JSON |
| `/api/report/json` | Download JSON report |
| `/api/report/pdf` | Download PDF report |
| `/api/report/html` | Download HTML report |
| `/api/report/markdown` | Download Markdown report |
| `/api/report/csv` | Download CSV report |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | AI API key (or `--ai-key` flag) |
| `OPENROUTER_MODEL` | `meta-llama/llama-3-8b-instruct` | LLM model |
| `HACKEMPIRE_TOOL_TIMEOUT_S` | `60` | Per-tool timeout (seconds) |
| `HACKEMPIRE_MAX_WORKERS` | `4` | Parallel tool threads |
| `HACKEMPIRE_RATE_LIMIT_RPS` | `10` | Requests/sec (2 in stealth mode) |

---

## Tool Registry (40+ tools)

<details>
<summary>Click to expand full tool list</summary>

**Recon:** subfinder, httpx, dnsx, nmap, whatweb, assetfinder, amass, shuffledns, github-subdomains

**URL Discovery:** katana, gau, waybackurls, hakrawler, gospider, cariddi, waymore, anew, qsreplace

**Enumeration:** feroxbuster, ffuf, dirsearch, arjun, gobuster, wfuzz, kiterunner, enum4linux-ng, smbmap

**Vuln Scan:** nuclei, nikto, naabu, afrog, sslyze, interactsh-client, wafw00f, dalfox, jsluice

**Exploitation:** sqlmap, commix, tplmap, ghauri, xsstrike, dalfox, metasploit (gated)

**Post-Exploit:** linpeas, netexec, chisel, ligolo-ng, impacket, bloodhound, ldapdomaindump

**Reporting:** WeasyPrint (PDF), JSON, HTML, Markdown, CSV

</details>

---

## Project Structure

```
hackempire-x/
├── main.py                    # Entry point + bootstrap
├── _bootstrap.py              # sys.path + module alias setup
├── setup.sh                   # Full auto-install script
├── requirements.txt
├── cli/                       # Argument parser, commands, banner, progress
├── core/
│   ├── orchestrator.py        # OrchestratorV2 — 7-phase pipeline
│   ├── phase_manager.py       # PhaseManager — FallbackChain per phase
│   ├── fallback_chain.py      # FallbackChain — 6 tools + AegisBridge
│   ├── models.py              # Vulnerability, ScanContext, ChainResult
│   ├── tor_manager.py         # Tor + proxychains4 stealth routing
│   └── todo_planner.py        # AI-generated todo list
├── ai/
│   ├── ai_engine.py           # AIEngine v2 — todo, analysis, exploits
│   ├── pentest_kb.py          # Offline PentestKnowledgeBase
│   ├── ai_client.py           # OpenRouter HTTP client
│   └── prompt_builder.py      # Structured prompt construction
├── tools/
│   ├── base_tool.py           # Abstract BaseTool + venv enforcement
│   ├── tool_manager.py        # Phase→tools registry
│   ├── recon/                 # httpx, dnsx, subfinder, nmap, whatweb
│   ├── url_discovery/         # katana, gau
│   ├── enum/                  # feroxbuster, ffuf, dirsearch, arjun
│   ├── vuln/                  # nuclei, nikto, dalfox, sqlmap, naabu
│   ├── post_exploit/          # linpeas, netexec
│   ├── methodology/           # XSSMethodology, SQLiMethodology
│   ├── waf/                   # WafDetector, WafBypassStrategy
│   └── external/              # AegisBridge (last-resort fallback)
├── installer/
│   ├── tool_installer.py      # apt/go/gem/git/pip/curl install engine
│   ├── dependency_resolver.py # Ordered install pipeline + venv linking
│   ├── tool_venv_manager.py   # Per-tool isolated Python venvs
│   └── tool_doctor.py         # Diagnose + auto-fix all tools
├── web/
│   ├── app.py                 # Flask + SocketIO (TLS :5443)
│   ├── routes.py              # Dashboard, report, export routes
│   ├── realtime_emitter.py    # SocketIO event emitter
│   ├── terminal_launcher.py   # PTY-backed xterm.js terminal
│   ├── tls_manager.py         # Self-signed cert generation
│   ├── static/hacker-theme.css # Dynamic hacker UI
│   └── templates/             # dashboard, report, logs
├── utils/                     # Logger, validator
└── tests/                     # 84 property-based + unit tests
```

---

## Security Model

- All subprocess calls use **list arguments** — no shell injection possible
- Target input **validated** (domain/IP regex) before any tool runs
- API keys **never logged** or written to disk
- Web dashboard binds to **127.0.0.1 only**
- Exploitation tools **gated behind `--mode exploit`** with explicit confirmation
- TLS on all web traffic (self-signed cert, port 5443)
- All tool output **JSON-parsed** before AI prompts — prompt injection prevention
- Config is a **frozen dataclass** — immutable after initialization

---

## Tests

```bash
python -m pytest tests/ -q
# 84 passed
```

Property-based tests (Hypothesis) cover: FallbackChain invariants, Vulnerability model bounds, WAF bypass correctness, TorManager immutability, AegisBridge resilience, export MIME types, terminal session uniqueness, full scan never-raises guarantees.

---

## Author

**Chandan Pandey**

Built for the security community. Use responsibly — always hack with permission.

---

## License

MIT — free to use, modify, and distribute with attribution.
