# Requirements Document

## Introduction

HackEmpire is being upgraded from a 3-phase recon/enum/vuln scanner into a master-level automated web penetration testing and bug bounty platform. The upgrade introduces a 7-phase attack pipeline (Recon → URL Discovery → Enumeration → Vulnerability Scanning → Exploitation → Post-Exploitation → Reporting), a 6-tool-per-phase fallback chain, a real-time WebSocket-powered dashboard, an AI engine with deep pentesting knowledge, an auto-launching terminal, WAF detection and bypass, isolated Python tool environments, Tor-based anonymization, and advanced XSS/SQLi methodologies.

---

## Glossary

- **Orchestrator**: The central coordinator that runs the full scan pipeline and manages all subsystems.
- **PhaseManager**: The component that sequences and executes the 7-phase attack pipeline.
- **FallbackChain**: The component that tries up to 6 tools for a phase in priority order, stopping on first success.
- **AIEngine**: The AI-powered component that generates todo lists, analyzes phase results, and suggests exploits.
- **PentestKnowledgeBase**: The static embedded knowledge base used as fallback when the AI API is unavailable.
- **RealTimeEmitter**: The component that bridges the scan engine to the WebSocket layer.
- **TerminalLauncher**: The component that spawns a PTY-backed shell and streams I/O over SocketIO.
- **TodoPlanner**: The component that generates and tracks the 7-phase x 6-task todo list.
- **ToolVenvManager**: The component that creates and manages isolated Python virtual environments per tool.
- **WafDetector**: The component that fingerprints the WAF vendor in front of a target.
- **WafBypassStrategy**: The component that selects sqlmap tamper scripts and HTTP bypass headers based on WAF vendor.
- **TorManager**: The component that manages the Tor service lifecycle and wraps tool commands with proxychains4.
- **DependencyResolver**: The component that installs all tools in the correct dependency order.
- **XSSMethodology**: The component that orchestrates a complete XSS attack methodology.
- **SQLiMethodology**: The component that orchestrates a complete SQL injection attack methodology.
- **AegisBridge**: The component that wraps the aegis CLI as a last-resort fallback scanner.
- **ChainResult**: The data structure returned by FallbackChain containing phase results, tool attempts, and degraded status.
- **TodoList**: The data structure containing 7 phases with 6 tasks each for a given target.
- **Vulnerability**: The data structure representing a discovered security finding with severity, confidence, and evidence.
- **ScanContext**: The data structure holding all state for an active scan session.
- **BaseTool**: The abstract base class that all tool implementations must extend.
- **ToolManager**: The component that instantiates and manages tool instances.
- **StateBridge**: The component that persists scan state to disk and serves it to the web layer.

---

## Requirements

### Requirement 1: 7-Phase Attack Pipeline

**User Story:** As a penetration tester, I want the system to execute a structured 7-phase attack pipeline, so that I can perform comprehensive web application security assessments in a repeatable, methodical way.

#### Acceptance Criteria

1. THE PhaseManager SHALL execute phases in the following fixed order: Recon, URL Discovery, Enumeration, Vulnerability Scan, Exploitation, Post-Exploitation, Reporting.
2. WHEN a scan is started, THE Orchestrator SHALL attempt all 7 phases regardless of individual phase success or failure.
3. WHEN a phase completes, THE Orchestrator SHALL pass the phase result into the AIEngine for analysis before proceeding to the next phase.
4. WHEN all 7 phases complete, THE Orchestrator SHALL emit a scan_complete event containing the FinalReport.
5. IF a phase produces a degraded result, THEN THE Orchestrator SHALL continue to the next phase with the degraded context noted.
6. THE Orchestrator SHALL persist ScanContext to disk via StateBridge after each phase completes.

---

### Requirement 2: FallbackChain Tool Execution

**User Story:** As a penetration tester, I want each phase to try multiple tools in priority order, so that the scan continues producing results even when individual tools are unavailable or fail.

#### Acceptance Criteria

1. WHEN a phase executes, THE FallbackChain SHALL try each tool in priority order, stopping on the first successful result.
2. WHEN a tool raises ToolNotInstalledError, THE FallbackChain SHALL skip that tool and try the next one in the chain.
3. WHEN a tool raises ToolTimeoutError, THE FallbackChain SHALL skip that tool and try the next one in the chain.
4. WHEN a tool raises ToolExecutionError, THE FallbackChain SHALL skip that tool and try the next one in the chain.
5. WHEN all tools in a phase fail, THE FallbackChain SHALL return a ChainResult with degraded set to True.
6. THE FallbackChain SHALL return a ChainResult in all cases and SHALL NOT raise an exception.
7. FOR ALL ChainResult values, degraded SHALL equal True if and only if succeeded_tool is None.
8. FOR ALL ChainResult values, the length of tool_attempts SHALL be less than or equal to the number of tools in the chain.

---

### Requirement 3: AI-Powered Todo List Generation

**User Story:** As a penetration tester, I want the AI engine to generate a structured todo list for each scan, so that I have a clear, target-specific attack plan before the scan begins.

#### Acceptance Criteria

1. WHEN a scan starts, THE AIEngine SHALL generate a TodoList containing exactly 7 phases with exactly 6 tasks per phase.
2. WHEN the AI API call fails or returns an empty response, THE AIEngine SHALL fall back to PentestKnowledgeBase.get_default_todo() and return a valid TodoList.
3. WHEN a TodoList is generated, THE TodoPlanner SHALL emit the todo list to all connected WebSocket clients via RealTimeEmitter.
4. THE AIEngine SHALL validate that each generated task has a non-empty description and a tool name from the known tool registry.
5. WHEN a task completes, THE TodoPlanner SHALL update the task status and emit the updated progress to connected clients.
6. THE TodoPlanner SHALL track per-phase progress as a float between 0.0 and 1.0 inclusive.

---

### Requirement 4: Real-Time WebSocket Event Streaming

**User Story:** As a penetration tester, I want all scan events streamed to the dashboard in real time, so that I can monitor progress and findings as they happen without refreshing the page.

#### Acceptance Criteria

1. WHEN a tool starts executing, THE RealTimeEmitter SHALL emit a tool_start event containing phase, tool name, and target.
2. WHEN a tool produces a result, THE RealTimeEmitter SHALL emit a tool_result event containing phase, tool name, timestamp, and result data.
3. WHEN a tool fails, THE RealTimeEmitter SHALL emit a tool_error event containing phase, tool name, and error description.
4. WHEN a phase completes, THE RealTimeEmitter SHALL emit a phase_complete event containing the phase name and PhaseResult.
5. WHEN a new vulnerability is discovered, THE RealTimeEmitter SHALL emit a vuln_found event containing the full Vulnerability object.
6. THE RealTimeEmitter SHALL NOT raise an exception for any emit_* call regardless of WebSocket client connection state.
7. IF a SocketIO error occurs during emission, THEN THE RealTimeEmitter SHALL log the error and continue without propagating the exception.
8. FOR ALL emitted events, the payload SHALL include a timestamp in ISO 8601 format.

---

### Requirement 5: Web Terminal (xterm.js + PTY)

**User Story:** As a penetration tester, I want an in-browser terminal pre-loaded with all installed tools, so that I can run manual commands alongside the automated scan without switching windows.

#### Acceptance Criteria

1. WHEN the web interface loads with web_enabled=True, THE TerminalLauncher SHALL spawn a PTY-backed /bin/bash shell with all installed tool binaries on PATH.
2. WHEN the terminal is active, THE TerminalLauncher SHALL stream stdout and stderr to the WebSocket channel terminal_output.
3. WHEN the client sends data on the terminal_input WebSocket channel, THE TerminalLauncher SHALL write that data to the PTY stdin.
4. WHEN the xterm.js client sends a resize event, THE TerminalLauncher SHALL resize the PTY to the specified rows and columns.
5. IF pty.openpty() fails, THEN THE TerminalLauncher SHALL return None and the scan SHALL continue normally with the terminal feature disabled.
6. THE TerminalLauncher SHALL assign a unique session_id to each terminal session.

---

### Requirement 6: Isolated Python Tool Environments (ToolVenvManager)

**User Story:** As a system administrator, I want each Python-based tool to run in its own virtual environment, so that conflicting package dependencies between tools do not cause installation or runtime failures.

#### Acceptance Criteria

1. WHEN a Python-based tool is installed, THE ToolVenvManager SHALL create a dedicated virtual environment at .hackempire/venvs/{tool_name}/.
2. WHEN ensure_venv is called for a tool that already has a venv, THE ToolVenvManager SHALL return the existing Python path without recreating the environment.
3. THE ToolVenvManager SHALL create each venv with --system-site-packages=False to prevent system package inheritance.
4. WHEN running a tool subprocess, THE ToolVenvManager SHALL use the venv's Python interpreter for commands starting with "python" or "python3".
5. FOR ALL tool venvs, the Python interpreter path SHALL exist at .hackempire/venvs/{tool_name}/bin/python after ensure_venv completes.

---

### Requirement 7: WAF Detection and Bypass

**User Story:** As a penetration tester, I want the system to detect WAF vendors and automatically apply appropriate bypass techniques, so that scans remain effective against protected targets.

#### Acceptance Criteria

1. WHEN the recon phase completes, THE Orchestrator SHALL run WafDetector.detect(target) and store the WafResult in ScanContext.
2. THE WafDetector SHALL return a WafResult in all cases and SHALL NOT raise an exception.
3. IF wafw00f is not installed or fails, THEN THE WafDetector SHALL return WafResult(detected=False, vendor=None, confidence=0.0).
4. WHEN SqlmapTool executes against a target with a detected WAF, THE SqlmapTool SHALL apply tamper scripts from WafBypassStrategy.get_sqlmap_tampers(waf_vendor).
5. WHEN NucleiTool executes against a target with a detected WAF, THE NucleiTool SHALL append bypass headers from WafBypassStrategy.apply_to_nuclei_flags(waf_vendor).
6. FOR ALL known WAF vendors (cloudflare, akamai, modsecurity, imperva, f5, barracuda, sucuri), THE WafBypassStrategy SHALL return a non-empty list of tamper scripts.
7. WHERE no WAF is detected, THE WafBypassStrategy SHALL return the default tamper scripts ["space2comment", "randomcase"].

---

### Requirement 8: Dependency Installation (DependencyResolver)

**User Story:** As a system administrator, I want all 36+ tools installed in the correct dependency order, so that tools with runtime dependencies on system packages or other tools install successfully.

#### Acceptance Criteria

1. WHEN install_tools is invoked, THE DependencyResolver SHALL install tools in the following order: system packages (apt), Go tools, Ruby tools, Git-cloned tools, pip tools (per-venv), then reconftw last.
2. WHEN system package installation fails, THE DependencyResolver SHALL abort the remaining installation steps and return the failure result.
3. THE DependencyResolver SHALL verify that the Go binary is on PATH before attempting Go tool installation.
4. THE DependencyResolver SHALL verify that the Ruby binary is on PATH before attempting Ruby tool installation.
5. WHEN reconftw is in the tool list, THE DependencyResolver SHALL run reconftw's install.sh as the final installation step.
6. THE DependencyResolver SHALL be idempotent — running resolve twice with the same tool list SHALL NOT fail or produce duplicate installations.
7. WHEN a git-cloned tool has a requirements.txt, THE DependencyResolver SHALL install those requirements into the tool's dedicated venv.

---

### Requirement 9: Tor Anonymization (TorManager)

**User Story:** As a penetration tester, I want the option to route all tool traffic through Tor, so that I can perform stealth scans without exposing my real IP address.

#### Acceptance Criteria

1. WHERE scan mode is "stealth", THE Orchestrator SHALL initialize TorManager and attempt to start the Tor service before any tool executes.
2. WHEN TorManager.start() is called, THE TorManager SHALL wait up to 30 seconds for the Tor SOCKS5 proxy to become available on port 9050.
3. IF Tor fails to start within 30 seconds, THEN THE Orchestrator SHALL log a warning and continue the scan without anonymization.
4. WHEN stealth mode is active and Tor is running, THE TorManager SHALL prepend ["proxychains4", "-q"] to all tool subprocess commands.
5. THE TorManager.wrap_command SHALL return a new list and SHALL NOT mutate the input command list.
6. WHEN rate-limiting is detected during a stealth scan, THE TorManager SHALL request a new Tor circuit via the NEWNYM signal.
7. IF the Tor control port is unavailable, THEN THE TorManager.get_new_identity SHALL fail silently without raising an exception.
8. THE TorManager.verify_connectivity SHALL return True if and only if the exit IP is confirmed as a Tor exit node via the Tor Project check API.

---

### Requirement 10: AegisBridge Last-Resort Fallback

**User Story:** As a penetration tester, I want a last-resort fallback scanner available when all primary tools fail, so that the scan always produces some results even in degraded environments.

#### Acceptance Criteria

1. WHEN all primary tools in a FallbackChain fail, THE FallbackChain SHALL attempt AegisBridge.run() if aegis is available.
2. WHEN AegisBridge is invoked for the first time, THE AegisBridge SHALL clone the aegis repository to tools/external/aegis/.
3. THE AegisBridge SHALL return a ChainResult in all cases and SHALL NOT raise an exception.
4. IF aegis is unavailable or fails, THEN THE AegisBridge SHALL return ChainResult(degraded=True) with a descriptive error in tool_attempts.
5. WHEN aegis produces output, THE AegisBridge SHALL parse it into the standard result schema containing ports, subdomains, urls, and vulnerabilities fields.

---

### Requirement 11: XSS Attack Methodology

**User Story:** As a penetration tester, I want a comprehensive automated XSS testing methodology, so that I can discover reflected, stored, DOM-based, and blind XSS vulnerabilities across all collected URLs.

#### Acceptance Criteria

1. WHEN the exploitation phase runs XSSMethodology, THE XSSMethodology SHALL test for reflected XSS using dalfox and xsstrike against all collected URLs.
2. WHEN the exploitation phase runs XSSMethodology, THE XSSMethodology SHALL test for stored XSS by injecting payloads into discovered form fields.
3. WHEN the exploitation phase runs XSSMethodology, THE XSSMethodology SHALL perform DOM XSS analysis on collected JavaScript files using jsluice and jsvulns.
4. WHEN the exploitation phase runs XSSMethodology, THE XSSMethodology SHALL test for blind XSS using nuclei blind-xss templates.
5. WHEN a WAF is detected, THE XSSMethodology SHALL apply WAF-specific encoding chains and bypass headers to all XSS payloads.
6. THE XSSMethodology SHALL deduplicate findings before returning results.
7. WHEN CSP headers are present, THE XSSMethodology SHALL test for CSP bypass via JSONP endpoints, static nonce detection, and unsafe-inline/unsafe-eval directives.

---

### Requirement 12: SQLi Attack Methodology

**User Story:** As a penetration tester, I want a comprehensive automated SQL injection testing methodology, so that I can discover and exploit SQL injection vulnerabilities across all 7 injection techniques.

#### Acceptance Criteria

1. WHEN the exploitation phase runs SQLiMethodology, THE SQLiMethodology SHALL test each discovered parameter for SQL injection using sqlmap and ghauri.
2. WHEN a WAF is detected, THE SQLiMethodology SHALL apply tamper scripts from WafBypassStrategy to all sqlmap invocations.
3. WHEN SQL injection is confirmed, THE SQLiMethodology SHALL enumerate databases, tables, and columns via the sqlmap --dbs → --tables → --columns pipeline.
4. WHEN the target database user has DBA privileges, THE SQLiMethodology SHALL attempt OS shell access via sqlmap --os-shell.
5. WHERE a DNS domain is configured, THE SQLiMethodology SHALL attempt out-of-band data exfiltration via sqlmap --dns-domain.
6. WHEN second-order injection is suspected, THE SQLiMethodology SHALL test via sqlmap --second-url with the injection URL and trigger URL.

---

### Requirement 13: CLI Commands and Scan Modes

**User Story:** As a penetration tester, I want a rich CLI with multiple scan modes and progress visualization, so that I can control the scan precisely and monitor results in real time from the terminal.

#### Acceptance Criteria

1. THE CLI SHALL provide a scan command accepting a target argument and --mode option with values: recon-only, full, exploit, stealth.
2. THE CLI SHALL provide a status command that displays current scan phase progress bars.
3. THE CLI SHALL provide a report command accepting a --format option with values: pdf, json, html, markdown, csv.
4. THE CLI SHALL provide an install-tools command that invokes DependencyResolver to install all tools.
5. THE CLI SHALL provide a terminal command that opens the web terminal in the default browser.
6. THE CLI SHALL provide a config command accepting key and value arguments to set configuration values in .hackempire/config.json.
7. WHERE scan mode is "exploit", THE CLI SHALL require explicit user confirmation before proceeding, as exploitation tools are enabled.
8. WHEN scan mode is "stealth", THE CLI SHALL set the request rate to 2 requests per second with a random jitter between 500ms and 3000ms.
9. THE CLI SHALL render per-phase progress bars using the Rich library with a dark hacker color theme.
10. THE CLI SHALL support a --resume flag on the scan command to resume from the last saved ScanContext state.

---

### Requirement 14: Web Dashboard

**User Story:** As a penetration tester, I want a real-time web dashboard with live vulnerability feeds, phase progress rings, and AI decision panels, so that I can monitor the full scan visually without using the CLI.

#### Acceptance Criteria

1. WHEN a new vulnerability is discovered, THE Dashboard SHALL prepend a collapsible finding card to the live vulnerability feed without a full page refresh.
2. WHEN a phase_progress event is received, THE Dashboard SHALL update the corresponding Chart.js donut ring to reflect the current completion percentage.
3. WHEN an ai_decision event is received, THE Dashboard SHALL update the AI Decision Panel with the phase name, summary, suggested tools, and detected exploit chains.
4. THE Dashboard SHALL display the xterm.js terminal in a dedicated tab connected to the TerminalLauncher PTY session.
5. THE Dashboard SHALL apply the dark hacker color theme with --bg-primary: #0d0d0d and --accent-green: #00ff41 as defined in hacker-theme.css.
6. THE Dashboard SHALL display finding cards with severity-specific border colors: red for critical, orange for high, yellow for medium, cyan for low.
7. WHEN the WebSocket connection drops mid-scan, THE Dashboard SHALL reconnect and fetch current state via GET /api/state to replay missed events.

---

### Requirement 15: Report Export

**User Story:** As a penetration tester, I want to export scan reports in multiple formats, so that I can share findings with clients and stakeholders in their preferred format.

#### Acceptance Criteria

1. WHEN GET /api/export/pdf is called, THE System SHALL return a PDF file download with MIME type application/pdf.
2. WHEN GET /api/export/json is called, THE System SHALL return a JSON file download with MIME type application/json.
3. WHEN GET /api/export/html is called, THE System SHALL return an HTML file download with MIME type text/html.
4. WHEN GET /api/export/markdown is called, THE System SHALL return a Markdown file download with MIME type text/markdown.
5. WHEN GET /api/export/csv is called, THE System SHALL return a CSV file download with MIME type text/csv.
6. IF an unknown format is requested, THEN THE System SHALL return HTTP 400 with a JSON error body containing the format name.

---

### Requirement 16: Vulnerability Data Model

**User Story:** As a penetration tester, I want all discovered vulnerabilities to follow a consistent data model, so that findings from different tools can be aggregated, deduplicated, and reported uniformly.

#### Acceptance Criteria

1. THE System SHALL represent every finding as a Vulnerability with the fields: name, severity, confidence, target, url, cve_ids, cwe_ids, evidence, tool_sources, exploit_available, remediation, cvss_score.
2. FOR ALL Vulnerability objects, severity SHALL be one of: "info", "low", "medium", "high", "critical".
3. FOR ALL Vulnerability objects, confidence SHALL be a float between 0.0 and 1.0 inclusive.
4. FOR ALL Vulnerability objects, tool_sources SHALL be a non-empty list containing at least one tool name.
5. WHEN multiple tools discover the same vulnerability, THE System SHALL merge tool_sources into a single Vulnerability rather than creating duplicates.

---

### Requirement 17: TLS Transport for Web Interface

**User Story:** As a security-conscious user, I want all CLI-to-backend communication to use HTTPS, so that scan data and credentials are not transmitted in plaintext on the local network.

#### Acceptance Criteria

1. WHEN the web server starts for the first time, THE System SHALL generate a self-signed TLS certificate and private key at .hackempire/tls/cert.pem and .hackempire/tls/key.pem.
2. WHEN the TLS certificate and key already exist, THE System SHALL reuse them without regenerating.
3. THE Flask server SHALL start with ssl_context=(cert_file, key_file) and listen on port 5443.
4. THE CLI SHALL connect to the backend via https://127.0.0.1:5443 with certificate verification disabled for the self-signed certificate.

---

### Requirement 18: Security Constraints

**User Story:** As a security engineer, I want the platform to follow secure coding practices, so that the tool itself does not introduce vulnerabilities or expose the operator's system.

#### Acceptance Criteria

1. THE System SHALL execute all tool subprocesses with shell=False to prevent shell injection.
2. WHEN a scan target is provided, THE System SHALL validate it against a domain/IP regex before any tool execution begins.
3. WHERE scan mode is not "exploit", THE System SHALL disable exploitation-phase tools (sqlmap exploit mode, metasploit, sliver) by default.
4. THE TerminalLauncher SHALL bind the PTY WebSocket only to 127.0.0.1 and SHALL NOT expose it on public network interfaces.
5. THE AIEngine SHALL JSON-parse all tool output before including it in AI prompts to prevent prompt injection via raw tool output.
6. THE System SHALL sanitize all user-controlled strings before rendering them in PDF and HTML reports.
