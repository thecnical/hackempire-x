<div align="center">

```
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗███╗   ███╗██████╗ ██╗██████╗ ███████╗    ██╗  ██╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝████╗ ████║██╔══██╗██║██╔══██╗██╔════╝    ╚██╗██╔╝
 ███████║███████║██║     █████╔╝ █████╗  ██╔████╔██║██████╔╝██║██████╔╝█████╗       ╚███╔╝
 ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██║██╔══██╗██╔══╝       ██╔██╗
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║ ╚═╝ ██║██║     ██║██║  ██║███████╗    ██╔╝ ██╗
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝
```

**AI-Orchestrated Offensive Security Platform — v4.0**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=linux)](https://kali.org)
[![CI](https://github.com/thecnical/hackempire-x/actions/workflows/ci.yml/badge.svg)](https://github.com/thecnical/hackempire-x/actions)
[![Tests](https://img.shields.io/badge/Tests-197%20passing-brightgreen?style=flat-square)](https://github.com/thecnical/hackempire-x/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tools](https://img.shields.io/badge/Tools-55%2B-red?style=flat-square)](https://github.com/thecnical/hackempire-x)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support%20the%20project-yellow?style=flat-square&logo=buy-me-a-coffee)](https://buymeacoffee.com/chandanpandit)

</div>

---

> **Legal Notice:** HackEmpire X is for **authorized penetration testing and security research only**. Always obtain explicit written permission before scanning any target. Unauthorized use is illegal and unethical. The authors accept no liability for misuse.

---

## What is HackEmpire X?

HackEmpire X is a **full-stack AI-orchestrated offensive security platform** built for bug bounty hunters, red teamers, and penetration testers. It runs a complete **7-phase attack pipeline** — from passive recon to post-exploitation and reporting — with 55+ integrated tools, automatic fallback chains, real-time AI decision making, and a live web dashboard.

**v4 brings six major upgrades:**
- Multi-model Bytez AI fallback chain (5 free models before OpenRouter)
- Autonomous scan mode — AI drives the entire attack with zero human input
- RAG-style persistent knowledge base — learns from every scan
- 20+ new tool integrations (55+ total)
- Structured AI deep-tool knowledge for every integrated tool
- Dashboard v2 with AttackGraph, MITRE ATT&CK overlay, live PoC preview, autonomous feed, and KB viewer

One command. Full attack surface coverage.

```bash
./hackempire scan example.com --mode ultra --web
```

---

## Architecture

```
                         ┌──────────────────────────────────────────────┐
                         │              OrchestratorV2                  │
                         │                                              │
  Target ──────────────► │  RECON → URL_DISC → ENUM → VULN_SCAN        │
                         │  EXPLOITATION → POST_EXPLOIT → REPORT       │
                         │                                              │
                         │  Each phase: FallbackChain                   │
                         │  [tool1→tool2→...→AegisBridge]              │
                         │                                              │
                         │  AIEngine v4                                 │
                         │  ├─ ModelChain: Qwen3-4B → Mistral-7B →     │
                         │  │             gemma-3-4b → gpt-4o-mini →   │
                         │  │             gpt-4.1-mini (all free)       │
                         │  ├─ OpenRouter (fallback)                    │
                         │  ├─ OfflineKB (OWASP Top 10 + API Top 10)   │
                         │  ├─ AutonomousEngine (AI-driven decisions)   │
                         │  ├─ ToolKnowledge Registry (55+ entries)     │
                         │  └─ RAG_KB (~/.hackempire/kb/)               │
                         │                                              │
                         │  WafDetector → WafBypassStrategy             │
                         │  TorManager (stealth via proxychains4)       │
                         │  ToolVenvManager (isolated pip envs)         │
                         └──────────────┬───────────────────────────────┘
                                        │
                    ┌───────────────────┴────────────────────┐
                    │                                        │
             Rich CLI (TLS)                    Dashboard v2 (HTTPS :5443)
             6 scan modes                      AttackGraph (vis.js)
             5 report formats                  MITRE ATT&CK Overlay
             Doctor + Status                   Live PoC Preview
                                               Autonomous Feed
                                               KB Viewer
                                               xterm.js terminal
```

---

## What's New in v4

### v4.1 — Multi-Model Bytez AI Fallback Chain
The AIEngine now tries 5 free Bytez models in priority order before falling back to OpenRouter:

```
Qwen/Qwen3-4B → Mistral-7B → gemma-3-4b-it → gpt-4o-mini → gpt-4.1-mini → OpenRouter → OfflineKB
```

- Single Bytez API key works across all 5 models
- 90-second total budget enforced across the full chain
- Every successful response records which model produced it
- No API key? Skips straight to OpenRouter → OfflineKB — zero exceptions

### v4.2 — Autonomous Scan Mode
Activate with `--mode ultra` or `--autonomous`. The AI drives the entire attack:

- Selects the next tool based on ToolKnowledge + accumulated scan context
- Analyzes each tool's output and decides: `continue`, `switch_tool`, or `next_phase`
- Logs every decision with reason to the AutonomousFeed dashboard panel
- Applies FallbackChain on tool errors — never stops mid-scan
- Terminates cleanly when all 7 phases complete or no attack surface remains

### v4.3 — RAG Knowledge Base
Persistent on-disk KB at `~/.hackempire/kb/`:

- Stores findings, working payloads, and attack patterns after every scan
- Queries matching entries before generating the todo list — future scans start smarter
- Appends confirmed payloads immediately during EXPLOITATION/POST_EXPLOIT
- Deduplicates entries by `(target, finding_name, url)` hash
- Auto-creates directory on first write — no manual setup

### v4.4 — 20+ New Tool Integrations (55+ total)

| Phase | New Tools Added |
|-------|----------------|
| RECON | theHarvester, recon-ng, dnsenum, fierce |
| ENUMERATION | WPProbe, wpscan, joomscan |
| VULN_SCAN | SSTImap, zaproxy, semgrep |
| EXPLOITATION | MetasploitMCP, ysoserial, certipy |
| POST_EXPLOIT | AdaptixC2, Atomic-Operator, pypykatz, pspy, evil-winrm |

### v4.5 — AI Deep Tool Knowledge
Every one of the 55+ tools has a structured `ToolKnowledge` entry:

```python
ToolKnowledge(
    when_to_use="...",        # when to select this tool
    what_to_look_for="...",   # output patterns that indicate a finding
    success_indicator="...",  # machine-checkable success condition
    failure_action="try_next_tool | skip_phase | escalate_to_ai",
    next_tool="...",          # recommended follow-up tool
    next_phase_trigger="...", # condition that signals phase advance
)
```

The AutonomousEngine consults this registry before every decision.

### v4.6 — Dashboard v2
Five new panels on top of all v3 dashboard features:

| Panel | Description |
|-------|-------------|
| **AttackGraph** | Directed graph of hosts, services, and exploit paths — live via SocketIO |
| **MITREOverlay** | ATT&CK technique grid — cells highlight as findings are confirmed |
| **PoCPreview** | Live curl command + affected URL for the latest generated PoC |
| **AutonomousFeed** | Real-time log of every AI decision during autonomous mode |
| **KBViewer** | Browse and search all RAG_KB entries for the current target |

---

## Features

### 7-Phase Attack Pipeline

| Phase | Tools (v3 + v4 additions) |
|-------|--------------------------|
| **RECON** | subfinder, httpx, dnsx, nmap, whatweb, assetfinder, amass, **theHarvester, recon-ng, dnsenum, fierce** |
| **URL_DISCOVERY** | katana, gau, waybackurls, hakrawler, gospider, cariddi |
| **ENUMERATION** | feroxbuster, ffuf, dirsearch, arjun, gobuster, kiterunner, **WPProbe, wpscan, joomscan** |
| **VULN_SCAN** | nuclei, nikto, naabu, afrog, sslyze, interactsh-client, **SSTImap, zaproxy, semgrep** |
| **EXPLOITATION** | dalfox, sqlmap, commix, tplmap, ghauri, xsstrike, **MetasploitMCP, ysoserial, certipy** |
| **POST_EXPLOIT** | linpeas, netexec, chisel, ligolo-ng, impacket, bloodhound, **AdaptixC2, Atomic-Operator, pypykatz, pspy, evil-winrm** |
| **REPORTING** | PDF, JSON, HTML, Markdown, CSV + HackerOne format |

### FallbackChain — Never Stops
Every phase runs tools in sequence. If a tool fails, times out, or isn't installed, the next one takes over automatically. If all fail, **AegisBridge** runs as last resort.

### WAF Detection & Bypass
- Detects WAF vendor via `wafw00f`
- Per-vendor tamper chains for sqlmap: Cloudflare, Akamai, AWS WAF, Imperva, F5, Sucuri, ModSecurity
- Automatic fallback to generic bypass

### Stealth Mode
- Routes all tool traffic through **Tor** via proxychains4
- Rate limited to 2 rps with 500–3000ms random jitter
- Automatic identity rotation via NEWNYM signal

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

Created automatically on first run. After running any command it will exist at:

```
/home/YOUR_USERNAME/.hackempire/config.json
```

### View your config

```bash
./hackempire config show
```

Or read it directly:
```bash
cat ~/.hackempire/config.json
```

Example config:
```json
{
  "bytez_api_key": "",
  "openrouter_key": "",
  "proxy": ""
}
```

### Set your AI keys

```bash
# Bytez AI — primary provider (https://bytez.com) — covers all 5 ModelChain models
./hackempire config bytez_key YOUR_BYTEZ_KEY

# OpenRouter — fallback provider (https://openrouter.ai)
./hackempire config openrouter_key YOUR_OPENROUTER_KEY
```

### Other options

```bash
# Route all tool traffic through Burp Suite
./hackempire config proxy http://127.0.0.1:8080
```

### Where to get API keys

| Provider | URL | Notes |
|----------|-----|-------|
| Bytez AI | [bytez.com](https://bytez.com) | Primary — one key covers all 5 free models |
| OpenRouter | [openrouter.ai](https://openrouter.ai) | Fallback — free tier available |

**AI provider priority:** Qwen3-4B → Mistral-7B → gemma-3-4b → gpt-4o-mini → gpt-4.1-mini → OpenRouter → OfflineKB

No API key required — the built-in knowledge base works fully offline.

---

## Usage

```bash
# Full autonomous scan — AI drives everything (v4 ultra mode)
./hackempire scan example.com --mode ultra --web

# Autonomous mode without ultra (explicit flag)
./hackempire scan example.com --autonomous --web

# Full 7-phase scan (standard sequential mode)
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
| `scan <target> --mode ultra` | Autonomous scan — AI selects tools and drives all phases |
| `scan <target> --autonomous` | Autonomous mode independent of --mode ultra |
| `scan <target> --mode full` | Standard 7-phase sequential scan |
| `scan <target> --mode recon-only` | Recon phase only |
| `scan <target> --mode stealth` | Scan via Tor + rate limiting |
| `scan <target> --mode exploit` | Full scan + active exploitation |
| `scan <target> --web` | Launch Dashboard v2 at https://127.0.0.1:5443 |
| `scan <target> --resume` | Resume an interrupted scan |
| `scan <target> --proxy http://127.0.0.1:8080` | Route through Burp Suite |
| `report --format pdf\|json\|html\|markdown\|csv` | Export latest report |
| `install-tools` | Install all 55+ pentest tools |
| `config <key> <value>` | Set a config value |
| `config show` | Show current config |
| `--status` | Show tool health status |
| `--doctor` | Diagnose and auto-fix broken tools |
| `--clean` | Clear logs and temp files |
| `--uninstall` | Remove HackEmpire X |

---

## Web Dashboard v2

Open `https://127.0.0.1:5443` when running with `--web`.

### New v4 Panels

| Route / Panel | Description |
|---------------|-------------|
| **AttackGraph** | Live directed graph — hosts, services, exploit paths via vis.js |
| **MITREOverlay** | ATT&CK technique grid — highlights on each confirmed finding |
| **PoCPreview** | Latest generated PoC — curl command + affected URL |
| **AutonomousFeed** | Real-time AI decision log during autonomous mode |
| **KBViewer** | Browse + search RAG_KB entries for current target |

### All Routes

| Route | Description |
|-------|-------------|
| `/dashboard` | Main dashboard — all panels, phase bars, vuln feed, terminal |
| `/report` | Full vulnerability report with severity and remediation |
| `/logs` | Auto-refreshing log viewer |
| `/api/state` | Full scan state JSON (includes v4 panel data for state replay) |
| `/api/attack-graph` | JSON graph data for AttackGraph panel |
| `/api/mitre-overlay` | JSON list of `{finding, technique_id, tactic}` |
| `/api/kb` | JSON list of RAG_KB entries for current target |
| `/api/autonomous-feed` | JSON list of recent autonomous decisions |
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
| `BYTEZ_API_KEY` | — | Bytez API key (fallback if not in config.json) |

---

## Tool Registry (55+ tools)

<details>
<summary>Click to expand full tool list</summary>

**Recon:** subfinder, httpx, dnsx, nmap, whatweb, assetfinder, amass, shuffledns, github-subdomains, **theHarvester, recon-ng, dnsenum, fierce**

**URL Discovery:** katana, gau, waybackurls, hakrawler, gospider, cariddi, waymore, anew, qsreplace

**Enumeration:** feroxbuster, ffuf, dirsearch, arjun, gobuster, wfuzz, kiterunner, enum4linux-ng, smbmap, **WPProbe, wpscan, joomscan**

**Vuln Scan:** nuclei, nikto, naabu, afrog, sslyze, interactsh-client, wafw00f, dalfox, jsluice, **SSTImap, zaproxy, semgrep**

**Exploitation:** sqlmap, commix, tplmap, ghauri, xsstrike, dalfox, **MetasploitMCP, ysoserial, certipy**

**Post-Exploit:** linpeas, netexec, chisel, ligolo-ng, impacket, bloodhound, ldapdomaindump, **AdaptixC2, Atomic-Operator, pypykatz, pspy, evil-winrm**

**Reporting:** WeasyPrint (PDF), JSON, HTML, Markdown, CSV, HackerOne format

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
- RAG_KB stored locally at `~/.hackempire/kb/` — no data leaves your machine

---

## Tests

```bash
python -m pytest tests/ -q
# 197 passed
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
