```
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __   ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
  AI-Orchestrated Pentesting Platform  ·  Made by Chandan Pandey
```

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)
![AI](https://img.shields.io/badge/AI-OpenRouter%20LLM-purple?style=flat-square)

</div>

---

## What is HackEmpire X?

HackEmpire X is a **modular, AI-orchestrated pentesting platform** built for security professionals, red teamers, and researchers. It automates the full **Recon → Enumeration → Vulnerability Scanning** pipeline, feeds every result into an AI decision engine, and surfaces everything through a live web dashboard with downloadable reports.

Built for **Kali Linux**. Designed for **speed, accuracy, and security**.

> **Legal Notice:** HackEmpire X is built for ethical security research and authorized penetration testing only. Always obtain written permission before scanning any target. Unauthorized use is illegal.

---

## Core Architecture

```
Target Input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                    Orchestrator                      │
│  Phase 1: RECON  →  Phase 2: ENUM  →  Phase 3: VULN │
│       ↕                  ↕                  ↕        │
│              AI Decision Engine (LLM)                │
│       ↕                  ↕                  ↕        │
│         State Manager  ←→  Context Builder           │
└─────────────────────────────────────────────────────┘
    │                                         │
    ▼                                         ▼
Tool Engine                            Web Dashboard
(nmap, subfinder,                   (Flask · Bootstrap)
 nuclei, ffuf,                      Live stats · Logs
 dirsearch)                         Reports · Attack Tree
```

---

## Features

### Scan Engine
- **3-Phase Pipeline** — Recon → Enum → Vuln with smart skip logic (no wasted cycles)
- **Parallel Execution** — ThreadPoolExecutor with configurable worker count
- **Smart Phase Skipping** — Skips downstream phases if recon yields no open ports or web hints
- **Per-Tool Timeouts** — Every subprocess is hard-capped; no hanging scans
- **Confidence Scoring** — Every finding is scored and corroboration-boosted across tools
- **Deduplication Engine** — Ports, subdomains, URLs, and vulns deduplicated and normalized

### AI Orchestration
- **OpenRouter-Compatible** — Works with any LLM (Llama 3, GPT-4, Mistral, Claude, etc.)
- **Phase-Aware Prompts** — Structured prompts built from live scan context per phase
- **Tool Prioritization** — AI suggests which tools to run next based on findings
- **Fallback Safety** — If AI fails or returns garbage, scan continues uninterrupted
- **Confidence Extraction** — AI decisions include confidence scores and next-phase hints

### Security Hardening
- **No `shell=True`** — All subprocess calls use list args (zero shell injection risk)
- **Input Validation** — Target domain/IP validated before any tool is invoked
- **API Key via Env Var** — Never hardcoded; passed via `--ai-key` or `OPENROUTER_API_KEY`
- **Immutable Config** — Runtime config is a frozen dataclass (no mutation mid-scan)
- **Subprocess Sandboxing** — stdout/stderr captured; no terminal passthrough

### Installer & Health
- **Auto-Install Engine** — Detects missing tools, installs via apt/pip/git with permission prompt
- **Tool Doctor** — Diagnoses broken tools, attempts auto-fix (reinstall, chmod), generates reports
- **Dependency Checker** — Validates Python version, pip packages, and env vars before every run
- **Health Tracker** — Per-tool status tracked across the full scan lifecycle

### Web Dashboard
- **Live Dashboard** — Real-time stats: ports, subdomains, URLs, vulns, tool health
- **Attack Tree View** — Visual nested tree of findings per phase
- **Log Viewer** — Auto-refreshing log stream (polls every 3 seconds)
- **Report Page** — Full vuln table with severity, affected targets, recommendations
- **JSON Export** — One-click download of the complete structured scan report

### CLI Experience
- **Rich-Powered Banner** — Cyberpunk ASCII art with colored output
- **Spinner Progress Bars** — Per-phase spinners with elapsed time
- **Global Commands** — `--status`, `--doctor`, `--clean`, `--uninstall`
- **Zero Crash Policy** — Every phase wrapped in graceful error handling

---

## Roadmap — Planned Features

These are the next high-impact features planned for HackEmpire X:

| # | Feature | Impact |
|---|---------|--------|
| 1 | **CVE Correlation Engine** — map open ports/services to known CVEs via NVD API | Critical |
| 2 | **Shodan / Censys Integration** — passive recon without touching the target | High |
| 3 | **Screenshot Engine** — auto-capture web screenshots via `gowitness` or `aquatone` | High |
| 4 | **Custom Wordlist Manager** — per-target wordlist selection based on tech stack detected | High |
| 5 | **Technology Fingerprinting** — detect CMS, frameworks, WAF via `whatweb` / `wappalyzer` | High |
| 6 | **Exploit Suggester** — map vulns to Metasploit modules and PoC links | High |
| 7 | **PDF Report Generator** — export full scan report as styled PDF via `weasyprint` | Medium |
| 8 | **Slack / Discord Alerts** — push critical findings to webhook in real time | Medium |
| 9 | **Scan Profiles** — save and reuse custom scan configs (wordlists, tools, timeouts) | Medium |
| 10 | **Multi-Target Mode** — scan a list of targets from a file (`--target-file targets.txt`) | Medium |
| 11 | **Rate Limiting Controls** — per-tool request throttling to avoid detection/bans | Medium |
| 12 | **Proxy Support** — route all tool traffic through Burp Suite or SOCKS5 proxy | Medium |
| 13 | **Historical Scan Diff** — compare current scan vs previous to highlight new findings | Medium |
| 14 | **Plugin System** — drop custom tools into `tools/custom/` and they auto-register | Medium |
| 15 | **AI Chat Mode** — interactive post-scan Q&A with the AI about findings | Low |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI | argparse + Rich |
| AI Client | OpenRouter API (any LLM) |
| Scan Tools | nmap, subfinder, nuclei, ffuf, dirsearch |
| Web GUI | Flask 3 + Bootstrap 5 |
| State | Thread-safe JSON file bridge |
| Concurrency | ThreadPoolExecutor |
| Packaging | pip + requirements.txt |

---

## Installation (Kali Linux)

**1. Clone the repository**

```bash
git clone https://github.com/thecnical/hackempire-x.git
cd hackempire-x
```

**2. Run the setup script (recommended)**

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Verify Python 3.11+
- Install pip dependencies (`rich`, `requests`, `flask`)
- Optionally install system tools (nmap, subfinder, nuclei, ffuf, dirsearch)
- Run a full status check

**3. Manual install (alternative)**

```bash
pip install -r requirements.txt
```

---

## Usage

### Basic scan

```bash
python main.py example.com --mode pro
```

### Scan with live web dashboard

```bash
python main.py example.com --mode pro --web
# Open: http://127.0.0.1:5000/dashboard
```

### Full AI-assisted scan

```bash
python main.py example.com --mode lab --ai-key YOUR_OPENROUTER_KEY --web
```

### Beginner mode (guided, verbose)

```bash
python main.py example.com --mode beginner
```

### Using environment variables (recommended for CI/automation)

```bash
export OPENROUTER_API_KEY=your_key
export HACKEMPIRE_MAX_WORKERS=8
export HACKEMPIRE_TOOL_TIMEOUT_S=120
python main.py example.com --mode pro --web
```

---

## CLI Commands

| Command | Description |
|---|---|
| `python main.py <target> --mode pro` | Run a full 3-phase scan |
| `python main.py <target> --mode pro --web` | Scan + launch live web dashboard |
| `python main.py <target> --mode lab --ai-key KEY` | Scan with AI orchestration |
| `python main.py --status` | Show tool and system installation status |
| `python main.py --doctor` | Diagnose and auto-fix broken tools |
| `python main.py --clean` | Clear logs and temp files |
| `python main.py --uninstall` | Fully remove HackEmpire X |

### Scan Modes

| Mode | Execution | Install Prompts | Best For |
|---|---|---|---|
| `beginner` | Sequential | Interactive | Learning, first-time use |
| `pro` | Parallel | Auto-approve | Real engagements |
| `lab` | Parallel | Auto-approve | Controlled lab environments |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HACKEMPIRE_TOOL_TIMEOUT_S` | `60` | Per-tool subprocess timeout (seconds) |
| `HACKEMPIRE_MAX_WORKERS` | `4` | Max parallel tool threads |
| `HACKEMPIRE_WEB_SCHEME` | `http` | URL scheme for web tools (`http`/`https`) |
| `OPENROUTER_BASE_URL` | OpenRouter default | AI API endpoint override |
| `OPENROUTER_MODEL` | `meta-llama/llama-3-8b-instruct` | AI model to use |
| `DIRSEARCH_SCRIPT` | `dirsearch.py` | Path to dirsearch script |
| `FFUF_WORDLIST` | `wordlist.txt` | Path to ffuf wordlist |

---

## Web Dashboard

Launch with `--web` — available at `http://127.0.0.1:5000`

| Route | Description |
|---|---|
| `/dashboard` | Live scan overview — stats, tool health, attack tree, high-confidence vulns |
| `/logs` | Auto-refreshing log viewer (polls every 3 seconds) |
| `/report` | Full vulnerability report with severity, recommendations, AI decisions |
| `/api/report/json` | Download full scan report as JSON |
| `/api/state` | Raw scan state (JSON, for debugging/integration) |
| `/api/logs` | Latest log lines (JSON, consumed by log viewer) |

---

## Security Model

HackEmpire X is built with security-first principles:

- All subprocess calls use **list arguments** — no shell injection possible
- Target input is **validated** (domain/IP regex) before any tool runs
- API keys are **never logged** or written to disk
- Scan state written to `logs/` which is **gitignored**
- Web dashboard binds to **127.0.0.1 only** (localhost, not exposed to network)
- Tool installs require **explicit user confirmation** in beginner mode
- Config is a **frozen dataclass** — immutable after initialization

---

## Performance Tips

- Set `HACKEMPIRE_MAX_WORKERS=8` on machines with 8+ cores
- Use `--mode pro` for parallel execution (4x faster than beginner)
- Increase `HACKEMPIRE_TOOL_TIMEOUT_S=120` for slow networks
- Use `OPENROUTER_MODEL=mistral-7b-instruct` for faster AI responses
- Run `python main.py --clean` between scans to keep logs lean

---

## Project Structure

```
hackempire/
├── main.py                   # Entry point
├── requirements.txt
├── setup.sh                  # Kali Linux setup script
├── cli/
│   ├── cli.py                # Main CLI + argument parser
│   ├── banner.py             # Dynamic Rich banner
│   └── commands.py           # --status, --doctor, --clean, --uninstall
├── core/
│   ├── config.py             # Immutable runtime config (frozen dataclass)
│   ├── orchestrator.py       # Phase orchestration engine
│   ├── phases.py             # Phase enum (RECON, ENUM, VULN)
│   ├── state_manager.py      # Thread-safe in-memory scan state
│   └── context_manager.py    # AI-ready context builder
├── ai/
│   ├── ai_client.py          # OpenRouter HTTP client
│   ├── prompt_builder.py     # Structured prompt construction
│   └── response_parser.py    # JSON extraction + schema validation
├── tools/
│   ├── base_tool.py          # Abstract base class for all tools
│   ├── tool_manager.py       # Phase execution engine
│   ├── health_tracker.py     # Per-tool status tracking
│   ├── confidence_engine.py  # Confidence scoring + corroboration
│   ├── deduplicator.py       # URL/port/subdomain deduplication
│   ├── recon/                # nmap_tool.py, subfinder_tool.py
│   ├── enum/                 # dirsearch_tool.py, ffuf_tool.py
│   └── vuln/                 # nuclei_tool.py
├── installer/
│   ├── tool_installer.py     # apt/pip/git install engine
│   ├── dependency_checker.py # Python + package validation
│   └── tool_doctor.py        # Diagnose + auto-fix tools
├── web/
│   ├── app.py                # Flask app factory
│   ├── routes.py             # Dashboard, logs, report routes
│   ├── state_bridge.py       # Thread-safe JSON state file
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── logs.html
│       └── report.html
├── utils/
│   ├── logger.py             # Rich console + file logger
│   └── validator.py          # Target domain/IP validation
└── logs/
    ├── hackempire.log         # Runtime log (gitignored)
    └── scan_state.json        # Live scan state for web GUI (gitignored)
```

---

## Uninstall

```bash
python main.py --uninstall
```

This will:
1. Remove the `logs/` directory
2. Remove all `__pycache__` directories
3. Optionally uninstall pip packages (`rich`, `requests`, `flask`)
4. Optionally remove the project directory

System tools (nmap, nuclei, etc.) are never removed automatically.

---

## Author

**Chandan Pandey**

> Built with precision for the security community.
> HackEmpire X is for ethical use only — always hack with permission.

---

## License

MIT License — free to use, modify, and distribute with attribution.
