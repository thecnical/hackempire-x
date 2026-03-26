<div align="center">

```
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗███╗   ███╗██████╗ ██╗██████╗ ███████╗    ██╗  ██╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝████╗ ████║██╔══██╗██║██╔══██╗██╔════╝    ╚██╗██╔╝
 ███████║███████║██║     █████╔╝ █████╗  ██╔████╔██║██████╔╝██║██████╔╝█████╗       ╚███╔╝
 ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██║██╔══██╗██╔══╝       ██╔██╗
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║ ╚═╝ ██║██║     ██║██║  ██║███████╗    ██╔╝ ██╗
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝
```

**AI-Orchestrated Offensive Security Platform — v2.1**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=linux)](https://kali.org)
[![CI](https://github.com/thecnical/hackempire-x/actions/workflows/ci.yml/badge.svg)](https://github.com/thecnical/hackempire-x/actions)
[![Tests](https://img.shields.io/badge/Tests-84%20passing-brightgreen?style=flat-square)](https://github.com/thecnical/hackempire-x/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tools](https://img.shields.io/badge/Tools-40%2B-red?style=flat-square)](https://github.com/thecnical/hackempire-x)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support%20the%20project-yellow?style=flat-square&logo=buy-me-a-coffee)](https://buymeacoffee.com/chandanpandit)

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
                         │  AIEngine v2                            │
                         │  ├─ Bytez AI (primary)                  │
                         │  ├─ OpenRouter (fallback)               │
                         │  ├─ TodoPlanner (7×6 task matrix)       │
                         │  ├─ PhaseAnalyzer (per-phase decisions) │
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
Every phase runs 6 tools in sequence. If a tool fails, times out, or isn't installed, the next one takes over automatically. If all 6 fail, **AegisBridge** runs as a last-resort fallback.

### AI Engine v2 — Dual Provider
- **Bytez AI** (primary) — fast, modern LLM inference at [bytez.com](https://bytez.com)
- **OpenRouter** (fallback) — automatically used if Bytez is unavailable
- **Offline KB** — OWASP Top 10 + API Security Top 10 fallback when both APIs are down
- Generates a **7-phase × 6-task todo matrix** at scan start
- Analyzes each phase result and decides next steps in real time
- All tool output **JSON-parsed before AI prompts** — prompt injection prevention

### WAF Detection & Bypass
- Detects WAF vendor via `wafw00f`
- Per-vendor tamper chains for sqlmap: Cloudflare, Akamai, AWS WAF, Imperva, F5, Sucuri, ModSecurity
- Automatic fallback to generic bypass

### Stealth Mode
- Routes all tool traffic through **Tor** via proxychains4
- Rate limited to 2 rps with 500–3000ms random jitter
- Automatic identity rotation via NEWNYM signal

### Real-Time Web Dashboard
- Live vulnerability feed, radar chart, phase progress bars
- AI Decision Panel with live reasoning per phase
- Embedded xterm.js terminal (PTY-backed, full interactive shell)
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

The setup script automatically installs everything — apt packages, Go tools, git clones, pip venvs. No prompts. No manual steps.

---

## Configuration

HackEmpire X stores all configuration in:

```
~/.hackempire/config.json
```

This file is **created automatically** — you never need to create it manually.

### Step 1 — Set your AI keys

```bash
# Bytez AI — primary provider (https://bytez.com)
./hackempire config bytez_key YOUR_BYTEZ_KEY

# OpenRouter — fallback provider (https://openrouter.ai)
./hackempire config openrouter_key YOUR_OPENROUTER_KEY
```

### Step 2 — View your current config

```bash
./hackempire config show
```

### Other options

```bash
# Route all tool traffic through Burp Suite
./hackempire config proxy http://127.0.0.1:8080
```

### Config file location

Always at:
```
/home/YOUR_USERNAME/.hackempire/config.json
```

Example on Kali with user `abhay`:
```
/home/abhay/.hackempire/config.json
```

View or edit directly:
```bash
cat ~/.hackempire/config.json
nano ~/.hackempire/config.json
```

Example contents:
```json
{
  "bytez_key": "bz-xxxxxxxxxxxxxxxxxxxx",
  "openrouter_key": "sk-or-xxxxxxxxxxxxxxxxxxxx",
  "proxy": "http://127.0.0.1:8080"
}
```

### Where to get API keys

| Provider | URL | Notes |
|----------|-----|-------|
| Bytez AI | [bytez.com](https://bytez.com) | Primary — sign up and copy key from dashboard |
| OpenRouter | [openrouter.ai](https://openrouter.ai) | Fallback — free tier available |

**AI provider priority:** Bytez → OpenRouter → Offline KB. No API key required — the built-in knowledge base works fully offline.

---

## Usage

```bash
# Full 7-phase scan
./hackempire scan example.com --mode full

# Full scan + live web dashboard
./hackempire scan example.com --mode full --web

# AI-assisted scan (uses saved keys from config automatically)
./hackempire scan example.com --mode full --web

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
| `config <key> <value>` | Set a config value (bytez_key, openrouter_key, proxy) |
| `config show` | Show current config from ~/.hackempire/config.json |
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

## Security Model

- All subprocess calls use **list arguments** — no shell injection possible
- Target input **validated** (domain/IP regex) before any tool runs
- API keys **never logged** or written to disk
- Web dashboard binds to **127.0.0.1 only**
- Exploitation tools **gated behind `--mode exploit`** with explicit confirmation
- TLS on all web traffic (self-signed cert, port 5443)
- All tool output **JSON-parsed** before AI prompts — prompt injection prevention

---

## Tests

```bash
python -m pytest tests/ -q
# 84 passed
```

---

## Author

**Chandan Pandey**

Built for the security community. Use responsibly — always hack with permission.

---

<div align="center">

If HackEmpire X helped you, consider supporting the project:

[![Buy Me A Coffee](https://img.shields.io/badge/☕%20Buy%20Me%20A%20Coffee-Support%20the%20project-yellow?style=for-the-badge)](https://buymeacoffee.com/chandanpandit)

</div>

---

## License

MIT — free to use, modify, and distribute with attribution.
