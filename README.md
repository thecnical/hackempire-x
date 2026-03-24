```
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __   ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
  AI-Orchestrated Web Penetration Testing Platform  v2.0
```

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-84%20passing-brightgreen?style=flat-square)
![AI](https://img.shields.io/badge/AI-OpenRouter%20LLM-purple?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

</div>

---

> **Legal Notice:** HackEmpire X is for ethical security research and authorized penetration testing only. Always obtain explicit written permission before scanning any target. Unauthorized use is illegal.

---

## What is HackEmpire X?

HackEmpire X is a **master-level automated web penetration testing and bug bounty platform**. It runs a full 7-phase pipeline from recon to reporting, with 6 tools per phase and automatic fallback if any tool fails. Every result feeds into an AI decision engine that guides the next phase. Everything streams live to a real-time web dashboard with an embedded terminal.

Built for **Kali Linux**. Designed for **bug bounty hunters, red teamers, and security researchers**.

---

## Architecture

```
Target
  |
  v
+------------------------------------------------------------------+
|                        OrchestratorV2                            |
|                                                                  |
|  Phase 1: RECON -> Phase 2: URL_DISCOVERY -> Phase 3: ENUM      |
|  Phase 4: VULN_SCAN -> Phase 5: EXPLOITATION -> Phase 6: POST   |
|  Phase 7: REPORTING                                              |
|                                                                  |
|  Each phase: FallbackChain(tool1->tool2->...->tool6->AegisBridge)|
|                        |                                         |
|            AIEngine (OpenRouter LLM)                             |
|                        |                                         |
|         WafDetector -> WafBypassStrategy                         |
|                        |                                         |
|         TorManager (stealth mode via proxychains4)               |
|                        |                                         |
|         TodoPlanner -> RealTimeEmitter (SocketIO)                |
+------------------------------------------------------------------+
         |                                    |
         v                                    v
   Rich CLI (TLS)                   Web Dashboard (HTTPS :5443)
   4 scan modes                     xterm.js terminal
   5 report formats                 Chart.js phase rings
                                    Live vuln feed
```

---

## Features

### 7-Phase Pipeline
- **RECON** - subfinder, httpx, dnsx, nmap, whatweb, reconftw
- **URL_DISCOVERY** - katana, gauplus, waybackurls, hakrawler, gau, gospider
- **ENUMERATION** - feroxbuster, ffuf, dirsearch, arjun, gobuster, wfuzz
- **VULN_SCAN** - nuclei, nikto, dalfox, sqlmap, ghauri, commix
- **EXPLOITATION** - sqlmap full chain, commix, dalfox, xsstrike, ghauri, metasploit (gated)
- **POST_EXPLOIT** - linpeas, crackmapexec, chisel, sliver (gated + consent), mimikatz, bloodhound
- **REPORTING** - PDF, JSON, HTML, Markdown, CSV

### FallbackChain
Every phase runs 6 tools in order. If a tool fails, times out, or is not installed, the next one takes over automatically. If all 6 fail, AegisBridge runs as a last-resort fallback. The scan never stops due to a single tool failure.

### AI Engine
- Generates a 7-phase x 6-task todo list at scan start
- Analyzes each phase result and decides next steps
- Suggests exploits based on discovered vulnerabilities
- Falls back to built-in PentestKnowledgeBase (OWASP Top 10, API Security Top 10) if the API is unavailable
- Prompt injection prevention: all tool output is JSON-parsed before being sent to the AI

### WAF Detection and Bypass
- Detects WAF vendor via wafw00f
- Per-vendor tamper script chains for sqlmap (Cloudflare, Akamai, AWS WAF, Imperva, F5, Sucuri, ModSecurity)
- Per-vendor bypass headers for nuclei and other tools
- Automatic fallback to generic bypass when no WAF is detected

### XSS Methodology
- Reflected XSS - dalfox + xsstrike with WAF bypass headers
- Stored XSS - form field injection
- DOM XSS - jsluice + jsvulns source/sink analysis
- Blind XSS - nuclei blind-xss templates
- CSP Bypass - JSONP endpoints, nonce detection, unsafe-inline/eval

### SQLi Methodology
All 7 sqlmap techniques: Boolean-based, Error-based, Union-based, Stacked queries, Time-based, Inline queries, Out-of-band. Plus second-order injection and privilege escalation.

### Stealth Mode
- Routes all tool traffic through Tor via proxychains4
- Rate limited to 2 rps with 500-3000ms random jitter
- Automatic identity rotation via NEWNYM signal

### Isolated Environments
- Each Python-based tool runs in its own venv (no dependency conflicts)
- Go tools installed via go install
- Ruby tools installed via gem
- Git-cloned tools get their own venv from their requirements.txt

### Real-Time Dashboard
- Live vulnerability feed via SocketIO
- Phase progress rings (Chart.js)
- AI Decision Panel
- Embedded xterm.js terminal (PTY-backed)
- Auto-reconnect with state replay on disconnect
- TLS on port 5443 (self-signed cert auto-generated)

---

## Installation

**Requirements:** Kali Linux (or any Debian-based distro), Python 3.11+, Go 1.21+, Ruby 3+

```bash
git clone https://github.com/thecnical/hackempire-x.git
cd hackempire-x
chmod +x setup.sh
./setup.sh
```

The setup script creates an isolated venv, installs pip dependencies, and optionally installs system tools via apt.

**Install all pentest tools:**

```bash
python main.py install-tools
```

This runs the full dependency resolver: apt packages -> Go tools -> Ruby gems -> Git clones -> pip packages -> ReconFTW.

---

## Usage

### Basic full scan

```bash
python main.py scan example.com --mode full
```

### Scan with live dashboard

```bash
python main.py scan example.com --mode full --web
# Open: https://127.0.0.1:5443/dashboard
```

### AI-assisted scan

```bash
python main.py scan example.com --mode full --ai-key YOUR_OPENROUTER_KEY --web
```

### Stealth scan (Tor + rate limiting)

```bash
python main.py scan example.com --mode stealth --web
```

### Exploit mode (requires explicit confirmation)

```bash
python main.py scan example.com --mode exploit --web
```

### Resume an interrupted scan

```bash
python main.py scan example.com --mode full --resume
```

---

## CLI Commands

| Command | Description |
|---|---|
| `python main.py scan <target> --mode full` | Run 7-phase scan |
| `python main.py scan <target> --mode recon-only` | Recon phase only |
| `python main.py scan <target> --mode stealth` | Scan via Tor + rate limiting |
| `python main.py scan <target> --mode exploit` | Full scan + active exploitation |
| `python main.py scan <target> --mode full --web` | Scan + live dashboard |
| `python main.py scan <target> --mode full --resume` | Resume interrupted scan |
| `python main.py report --format pdf` | Export latest scan as PDF |
| `python main.py report --format json` | Export as JSON |
| `python main.py report --format html` | Export as HTML |
| `python main.py report --format markdown` | Export as Markdown |
| `python main.py report --format csv` | Export as CSV |
| `python main.py install-tools` | Install all pentest tools |
| `python main.py terminal` | Open web terminal in browser |
| `python main.py config <key> <value>` | Set a config value |
| `python main.py --status` | Show tool installation status |
| `python main.py --doctor` | Diagnose and auto-fix broken tools |
| `python main.py --clean` | Clear logs and temp files |
| `python main.py --uninstall` | Remove HackEmpire X |

---

## Web Dashboard

Available at `https://127.0.0.1:5443` when running with `--web`.

| Route | Description |
|---|---|
| `/dashboard` | Live scan overview - phase rings, vuln feed, AI decisions, terminal |
| `/report` | Full vulnerability report with severity and recommendations |
| `/logs` | Auto-refreshing log viewer |
| `/api/state` | Raw scan state JSON (for integrations) |
| `/api/export/json` | Download report as JSON |
| `/api/export/pdf` | Download report as PDF |
| `/api/export/html` | Download report as HTML |
| `/api/export/markdown` | Download report as Markdown |
| `/api/export/csv` | Download report as CSV |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | - | AI API key (or pass via --ai-key) |
| `OPENROUTER_MODEL` | `meta-llama/llama-3-8b-instruct` | LLM model to use |
| `HACKEMPIRE_TOOL_TIMEOUT_S` | `60` | Per-tool subprocess timeout (seconds) |
| `HACKEMPIRE_MAX_WORKERS` | `4` | Max parallel tool threads |
| `HACKEMPIRE_RATE_LIMIT_RPS` | `10` | Requests per second (overridden to 2 in stealth) |

---

## Project Structure

```
hackempire/
+-- main.py                        # Entry point
+-- requirements.txt
+-- setup.sh
+-- cli/
|   +-- cli.py                     # Argument parser
|   +-- commands.py                # All CLI commands
|   +-- banner.py                  # Rich ASCII banner
|   +-- progress.py                # Phase progress bars + finding renderer
+-- core/
|   +-- orchestrator.py            # OrchestratorV2 - 7-phase pipeline
|   +-- phase_manager.py           # PhaseManager - runs FallbackChain per phase
|   +-- fallback_chain.py          # FallbackChain - 6 tools + AegisBridge fallback
|   +-- models.py                  # Vulnerability, ScanContext, ChainResult, etc.
|   +-- phases.py                  # Phase enum (7 phases)
|   +-- todo_planner.py            # AI-generated todo list per scan
|   +-- tor_manager.py             # Tor + proxychains4 stealth routing
|   +-- config.py                  # Immutable runtime config
|   +-- state_manager.py           # Thread-safe scan state
+-- ai/
|   +-- ai_engine.py               # AIEngine v2 - todo, phase analysis, exploits
|   +-- pentest_kb.py              # PentestKnowledgeBase - OWASP, API Top 10
|   +-- ai_client.py               # OpenRouter HTTP client
|   +-- prompt_builder.py          # Structured prompt construction
|   +-- response_parser.py         # JSON extraction + schema validation
+-- tools/
|   +-- base_tool.py               # Abstract BaseTool
|   +-- tool_manager.py            # PHASE_TOOLS_2025 registry (7 phases x 6 tools)
|   +-- recon/                     # httpx, dnsx, subfinder, nmap, whatweb
|   +-- url_discovery/             # katana, gauplus
|   +-- enum/                      # feroxbuster, ffuf, dirsearch, arjun
|   +-- vuln/                      # nuclei, nikto, dalfox, sqlmap, ghauri
|   +-- post_exploit/              # linpeas, crackmapexec
|   +-- methodology/               # XSSMethodology, SQLiMethodology
|   +-- waf/                       # WafDetector, WafBypassStrategy
|   +-- external/                  # AegisBridge (last-resort fallback)
+-- installer/
|   +-- tool_installer.py          # apt/go/gem/git/pip install engine
|   +-- dependency_resolver.py     # Ordered install pipeline
|   +-- tool_venv_manager.py       # Per-tool isolated Python venvs
|   +-- dependency_checker.py      # Pre-flight validation
|   +-- tool_doctor.py             # Diagnose + auto-fix tools
+-- web/
|   +-- app.py                     # Flask + SocketIO app factory (TLS :5443)
|   +-- routes.py                  # Dashboard, report, export routes
|   +-- realtime_emitter.py        # SocketIO event emitter
|   +-- terminal_launcher.py       # PTY-backed xterm.js terminal
|   +-- tls_manager.py             # Self-signed cert generation
|   +-- state_bridge.py            # Thread-safe JSON state file
|   +-- pdf_report.py              # WeasyPrint PDF generator
|   +-- exporters/
|   |   +-- markdown_export.py
|   |   +-- csv_export.py
|   +-- static/
|   |   +-- hacker-theme.css       # Dark hacker theme
|   +-- templates/
|       +-- base.html              # xterm.js v5, socket.io v4, Chart.js v4
|       +-- dashboard.html         # Live dashboard
|       +-- report.html            # Vulnerability report
|       +-- logs.html              # Log viewer
+-- utils/
|   +-- logger.py                  # Rich console + file logger
|   +-- validator.py               # Target domain/IP validation
+-- tests/                         # 84 property-based + unit tests
```

---

## Security Model

- All subprocess calls use **list arguments** - no shell injection possible
- Target input **validated** (domain/IP regex) before any tool runs
- API keys **never logged** or written to disk
- Web dashboard binds to **127.0.0.1 only**
- Exploitation-phase tools **gated behind --mode=exploit**
- Sliver C2 **gated behind explicit consent prompt** at runtime
- TLS on all web traffic (self-signed cert, port 5443)
- All tool output **JSON-parsed** before inclusion in AI prompts (prompt injection prevention)
- Config is a **frozen dataclass** - immutable after initialization

---

## Tests

```bash
python -m pytest tests/ -q
# 84 passed
```

Includes property-based tests (Hypothesis) covering: FallbackChain invariants, Vulnerability model bounds, WAF bypass correctness, TorManager immutability, AegisBridge resilience, export MIME types, terminal session uniqueness, and full scan never-raises guarantees.

---

## Author

**Chandan Pandey**

Built for the security community. Use responsibly - always hack with permission.

---

## License

MIT License - free to use, modify, and distribute with attribution.
