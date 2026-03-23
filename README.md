```
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __   ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
  AI-Orchestrated Pentesting Platform — Made by Chandan Pandey
```

---

## What is HackEmpire X?

HackEmpire X is a modular, AI-orchestrated pentesting platform built for security professionals and researchers. It automates the full recon → enumeration → vulnerability scanning pipeline, feeds results into an AI decision engine, and surfaces everything through a clean web dashboard and downloadable reports.

It is designed to run on Kali Linux and any Debian-based system with Python 3.11+.

---

## Features

- **AI Orchestration** — OpenRouter-compatible AI client drives phase decisions, tool prioritization, and next-step recommendations
- **3-Phase Scan Engine** — Recon (nmap, subfinder) → Enum (dirsearch, ffuf) → Vuln (nuclei), with smart skip logic
- **Auto-Install System** — Detects missing tools, prompts for permission, installs via apt/pip/git
- **Tool Doctor** — Diagnoses broken tools, attempts auto-fix (reinstall, chmod), generates repair reports
- **Dependency Checker** — Validates Python version, pip packages, and environment variables before every run
- **Confidence Scoring** — Every finding is scored and corroboration-boosted across tools
- **Deduplication Engine** — Ports, subdomains, URLs, and vulnerabilities are deduplicated and normalized
- **Web Dashboard** — Flask-based live dashboard with attack tree, tool health, vuln table, and log viewer
- **JSON Report Export** — One-click download of the full structured scan report
- **Dynamic CLI** — Rich-powered cyberpunk banner, spinner progress bars, and colored output
- **Global Commands** — `--status`, `--doctor`, `--clean`, `--uninstall`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI | argparse + Rich |
| AI Client | OpenRouter API (any LLM) |
| Scan Tools | nmap, subfinder, nuclei, ffuf, dirsearch |
| Web GUI | Flask 3 + Bootstrap 5 |
| State | JSON file bridge (thread-safe) |
| Concurrency | ThreadPoolExecutor |
| Packaging | pip + requirements.txt |

---

## Installation (Kali Linux)

**1. Clone the repository**

```bash
git clone https://github.com/chandanpandey/hackempire-x.git
cd hackempire-x
```

**2. Run the setup script (recommended)**

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Verify Python 3.11+
- Install pip dependencies
- Optionally install system tools (nmap, subfinder, nuclei, ffuf, dirsearch)
- Run a status check

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

### Scan with web dashboard

```bash
python main.py example.com --mode pro --web
# Open: http://127.0.0.1:5000/dashboard
```

### Scan with AI decisions

```bash
python main.py example.com --mode lab --ai-key YOUR_OPENROUTER_KEY --web
```

### Beginner mode (guided output)

```bash
python main.py example.com --mode beginner
```

---

## CLI Commands

| Command | Description |
|---|---|
| `python main.py <target> --mode pro` | Run a full scan |
| `python main.py <target> --mode pro --web` | Scan + launch web dashboard |
| `python main.py <target> --mode lab --ai-key KEY` | Scan with AI orchestration |
| `python main.py --status` | Show tool and system status |
| `python main.py --doctor` | Diagnose and auto-fix broken tools |
| `python main.py --clean` | Clear logs and temp files |
| `python main.py --uninstall` | Fully remove HackEmpire X |

### Modes

| Mode | Description |
|---|---|
| `beginner` | Sequential execution, verbose guidance, install prompts |
| `pro` | Parallel execution, minimal output, auto-approve installs |
| `lab` | Same as pro, intended for controlled lab environments |

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `HACKEMPIRE_TOOL_TIMEOUT_S` | `60` | Per-tool subprocess timeout in seconds |
| `HACKEMPIRE_MAX_WORKERS` | `4` | Max parallel tool threads |
| `HACKEMPIRE_WEB_SCHEME` | `http` | URL scheme for web tools (http/https) |
| `OPENROUTER_BASE_URL` | OpenRouter default | AI API endpoint |
| `OPENROUTER_MODEL` | `meta-llama/llama-3-8b-instruct` | AI model to use |
| `DIRSEARCH_SCRIPT` | `dirsearch.py` | Path to dirsearch script |
| `FFUF_WORDLIST` | `wordlist.txt` | Path to ffuf wordlist |

---

## Web Dashboard

When launched with `--web`, the dashboard is available at `http://127.0.0.1:5000`.

| Route | Description |
|---|---|
| `/dashboard` | Live scan overview — stats, tool health, attack tree, high-confidence vulns |
| `/logs` | Auto-refreshing log viewer (polls every 3 seconds) |
| `/report` | Full vulnerability report with severity, recommendations, AI decisions |
| `/api/report/json` | Download full scan report as JSON |
| `/api/state` | Raw scan state (JSON, for debugging) |
| `/api/logs` | Latest log lines (JSON, used by log viewer) |

---

## Project Structure

```
hackempire/
├── main.py                  # Entry point
├── requirements.txt
├── setup.sh                 # Kali Linux setup script
├── cli/
│   ├── cli.py               # Main CLI + argument parser
│   ├── banner.py            # Dynamic Rich banner
│   └── commands.py          # --status, --doctor, --clean, --uninstall
├── core/
│   ├── config.py            # Immutable runtime config
│   ├── orchestrator.py      # Phase orchestration engine
│   ├── phases.py            # Phase enum (RECON, ENUM, VULN)
│   ├── state_manager.py     # In-memory scan state
│   └── context_manager.py   # AI-ready context builder
├── ai/
│   ├── ai_client.py         # OpenRouter HTTP client
│   ├── prompt_builder.py    # Structured prompt construction
│   └── response_parser.py   # JSON extraction + schema validation
├── tools/
│   ├── base_tool.py         # Abstract base class for all tools
│   ├── tool_manager.py      # Phase execution engine
│   ├── health_tracker.py    # Per-tool status tracking
│   ├── confidence_engine.py # Confidence scoring + corroboration
│   ├── deduplicator.py      # URL/port/subdomain deduplication
│   ├── recon/               # nmap_tool.py, subfinder_tool.py
│   ├── enum/                # dirsearch_tool.py, ffuf_tool.py
│   └── vuln/                # nuclei_tool.py
├── installer/
│   ├── tool_installer.py    # apt/pip/git install engine
│   ├── dependency_checker.py# Python + package validation
│   └── tool_doctor.py       # Diagnose + auto-fix tools
├── web/
│   ├── app.py               # Flask app factory
│   ├── routes.py            # Dashboard, logs, report routes
│   ├── state_bridge.py      # Thread-safe JSON state file
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── logs.html
│       └── report.html
├── utils/
│   ├── logger.py            # Rich console + file logger
│   └── validator.py         # Target domain/IP validation
└── logs/
    ├── hackempire.log        # Runtime log (gitignored)
    └── scan_state.json       # Live scan state for web GUI (gitignored)
```

---

## Uninstall

```bash
python main.py --uninstall
```

This will:
1. Remove the `logs/` directory
2. Remove all `__pycache__` directories
3. Optionally uninstall pip packages (rich, requests, flask)
4. Optionally remove the project directory

System tools (nmap, nuclei, etc.) are never removed automatically.

---

## GitHub Setup

```bash
git init
git add .
git commit -m "Initial release — HackEmpire X v1.0.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hackempire-x.git
git push -u origin main
```

---

## Screenshots

> Dashboard, log viewer, and report pages render in any modern browser.
> Run `python main.py example.com --mode pro --web` and open `http://127.0.0.1:5000`.

---

## Author

**Chandan Pandey**

HackEmpire X is built for ethical security research and authorized penetration testing only.
Always obtain written permission before scanning any target.

---

## License

MIT License — see `LICENSE` for details.
