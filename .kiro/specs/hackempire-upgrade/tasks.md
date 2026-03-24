# Implementation Plan: HackEmpire Upgrade

## Overview

Upgrade HackEmpire from a 3-phase scanner into a 7-phase automated web penetration testing platform. All tasks extend the existing architecture (BaseTool, ToolManager, Orchestrator, StateManager, Flask web layer) — no rewrites, only additive changes and targeted replacements.

## Tasks

- [x] 1. Extend Phase enum and core data models
  - Extend `core/phases.py` to add 7 phases: RECON, URL_DISCOVERY, ENUMERATION, VULN_SCAN, EXPLOITATION, POST_EXPLOIT, REPORTING
  - Add `Vulnerability` dataclass to `core/models.py` with fields: name, severity, confidence, target, url, cve_ids, cwe_ids, evidence, tool_sources, exploit_available, remediation, cvss_score
  - Add `ChainResult`, `ToolAttempt`, `ScanContext`, `TodoTask`, `TodoList`, `PhaseResult`, `AIDecision`, `WafResult` dataclasses to `core/models.py`
  - _Requirements: 1.1, 16.1, 16.2, 16.3, 16.4_

  - [x] 1.1 Write property tests for Vulnerability data model
    - **Property 16: Vulnerability Severity Invariant** — severity is always one of the 5 allowed values
    - **Property 17: Vulnerability Confidence Bounds** — confidence is always between 0.0 and 1.0
    - **Validates: Requirements 16.2, 16.3**

- [x] 2. Implement FallbackChain
  - Create `core/fallback_chain.py` with `FallbackChain` class
  - Constructor accepts `tools: list[BaseTool]`, `emitter: RealTimeEmitter`, `phase: str`
  - `execute(target)` tries tools in order, stops on first success, returns `ChainResult` in all cases
  - On `ToolNotInstalledError`, `ToolTimeoutError`, `ToolExecutionError`: record attempt and continue to next tool
  - If all tools fail, return `ChainResult(degraded=True, succeeded_tool=None)`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 2.1 Write property test: FallbackChain stops on first success
    - **Property 2: FallbackChain Stops on First Success** — when tool[i] succeeds, tool[i+1] is never called
    - **Validates: Requirements 2.1**

  - [x] 2.2 Write property test: FallbackChain degraded on all failures
    - **Property 3: FallbackChain Degraded on All Failures** — all tools raising exceptions yields degraded=True
    - **Validates: Requirements 2.5**

  - [x] 2.3 Write property test: FallbackChain never raises
    - **Property 4: FallbackChain Never Raises** — no exception for any tool list and target combination
    - **Validates: Requirements 2.6**

  - [x] 2.4 Write property test: degraded iff no succeeded tool
    - **Property 5: Degraded Iff No Succeeded Tool** — degraded == (succeeded_tool is None) always holds
    - **Validates: Requirements 2.7**

- [x] 3. Implement RealTimeEmitter
  - Create `web/realtime_emitter.py` with `RealTimeEmitter` class wrapping flask-socketio
  - Implement `emit_tool_start`, `emit_tool_result`, `emit_tool_error`, `emit_phase_complete`, `emit_todo_update`, `emit_scan_complete`, `emit_vuln_found`, `emit_terminal_output`
  - All emit methods catch SocketIO exceptions, log them, and never propagate
  - All event payloads include ISO 8601 timestamp field
  - Add `flask-socketio>=5.3.0`, `python-socketio>=5.10.0`, `eventlet>=0.35.0` to `requirements.txt`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 3.1 Write property test: RealTimeEmitter never raises
    - **Property 8: RealTimeEmitter Never Raises** — no exception for any emit sequence in any SocketIO state
    - **Validates: Requirements 4.6, 4.7**

- [x] 4. Implement PentestKnowledgeBase and AIEngine v2
  - Create `ai/pentest_kb.py` with `PentestKnowledgeBase` containing OWASP Top 10, API Security Top 10, VULN_PATTERNS, BOUNTY_SEVERITY_MAP, TOOL_PARSE_RULES, and `get_default_todo(target)` returning a valid `TodoList`
  - Create `ai/ai_engine.py` with `AIEngine` class extending existing `AIClient`
  - Implement `generate_todo_list(target, context)` — calls AI API, falls back to KB on failure, validates 7-phase x 6-task structure
  - Implement `analyze_phase(phase, result, context)` returning `AIDecision`
  - Implement `suggest_exploits(vulns)` and `generate_report_summary(full_state)`
  - JSON-parse all tool output before including in AI prompts to prevent prompt injection
  - _Requirements: 3.1, 3.2, 3.4, 18.5_

  - [x] 4.1 Write property test: TodoList structure invariant
    - **Property 6: TodoList Structure Invariant** — generate_todo_list always returns exactly 7 phases with 6 tasks each
    - **Validates: Requirements 3.1**

  - [x] 4.2 Write property test: AI fallback on API failure
    - **Property 7: AI Fallback on API Failure** — on any API failure, returns valid TodoList from KB
    - **Validates: Requirements 3.2**

- [x] 5. Implement TodoPlanner
  - Create `core/todo_planner.py` with `TodoPlanner` class
  - Implement `generate(target, ai_engine)` returning `TodoList`
  - Implement `mark_task_done(phase, task_index)` updating task status
  - Implement `get_progress()` returning `dict[str, float]` (phase to 0.0..1.0)
  - Emit updated todo via `RealTimeEmitter` on each status change
  - _Requirements: 3.3, 3.5, 3.6_

  - [x] 5.1 Write property test: TodoPlanner progress bounds
    - **Property 9: TodoPlanner Progress Bounds** — get_progress() always returns floats between 0.0 and 1.0
    - **Validates: Requirements 3.6**

- [x] 6. Implement PhaseManager
  - Create `core/phase_manager.py` with `PhaseManager` class
  - `PHASES` class attribute lists all 7 phases in fixed order
  - `run_phase(phase, target, context)` instantiates `FallbackChain` with the phase's tool list and calls `execute(target)`
  - `get_phase_status()` returns current status dict
  - Emit `phase_complete` via `RealTimeEmitter` after each phase
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 7. Checkpoint — Ensure FallbackChain, PhaseManager, RealTimeEmitter, and AIEngine tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Extend ToolInstaller with go/gem/script install methods
  - Extend `InstallMethod` literal in `installer/tool_installer.py` to include `"go"`, `"gem"`, `"script"`
  - Add `_run_go`, `_run_gem`, `_run_script` methods to `ToolInstaller`
  - Add all new tool `ToolInstallSpec` entries from design Upgrade 1 and Upgrade 8 to `TOOL_INSTALL_SPECS`
  - _Requirements: 8.1, 8.3, 8.4_

- [x] 9. Implement ToolVenvManager
  - Create `installer/tool_venv_manager.py` with `ToolVenvManager` class
  - `ensure_venv(tool_name, pip_packages)` creates venv at `.hackempire/venvs/{tool_name}/` if not present, installs packages, returns Python path
  - If venv already exists, return existing Python path without recreating (idempotent)
  - Create venv with `--system-site-packages=False`
  - Add `TOOL_VENV_PACKAGES` dict mapping tool names to their pip dependencies
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.1 Write property test: ToolVenvManager idempotence
    - **Property 12: ToolVenvManager Idempotence** — calling ensure_venv twice returns same path without recreating
    - **Validates: Requirements 6.2**

- [x] 10. Implement DependencyResolver
  - Create `installer/dependency_resolver.py` with `DependencyResolver` class
  - `resolve(tool_names)` installs in order: system packages, Go tools, Ruby tools, Git tools, pip tools, reconftw
  - `install_system_packages()` runs a single `apt-get install -y` batch call for all system packages
  - Abort remaining steps if system package install fails
  - Verify `go` on PATH before Go tools; verify `ruby` on PATH before Ruby tools
  - For git-cloned tools with `requirements.txt`, install into tool's venv via `ToolVenvManager`
  - `install_reconftw()` clones repo and runs `install.sh` as final step
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 11. Implement WafDetector and WafBypassStrategy
  - Create `tools/waf/waf_detector.py` with `WafDetector` class
  - `detect(target)` runs `wafw00f` subprocess, parses output, returns `WafResult`; never raises
  - If wafw00f not installed or fails, return `WafResult(detected=False, vendor=None, confidence=0.0)`
  - Create `tools/waf/waf_bypass_strategy.py` with `WafBypassStrategy` class
  - `get_sqlmap_tampers(waf_vendor)` returns tamper list from `WAF_TAMPER_MAP`; default `["space2comment", "randomcase"]` when no WAF
  - `get_bypass_headers(waf_vendor)` returns `BYPASS_HEADERS` dict
  - `apply_to_nuclei_flags(waf_vendor)` returns `--header` flag list for nuclei
  - Add `wafw00f>=2.2.0` to `requirements.txt`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 11.1 Write property test: WafDetector never raises
    - **Property 10: WafDetector Never Raises** — detect() always returns WafResult, never raises
    - **Validates: Requirements 7.2**

  - [x] 11.2 Write property test: WafBypassStrategy returns tampers for known vendors
    - **Property 11: WafBypassStrategy Returns Tampers for Known Vendors** — all 7 known vendors return non-empty list
    - **Validates: Requirements 7.6**

- [x] 12. Implement TorManager
  - Create `core/tor_manager.py` with `TorManager` class
  - `start()` starts tor service, polls port 9050 for up to 30 seconds, returns bool
  - `verify_connectivity()` GETs Tor check API via SOCKS5 proxy, returns True iff IsTor=true; catches all exceptions
  - `get_new_identity()` sends NEWNYM signal to control port; silently ignores all errors
  - `wrap_command(cmd)` returns new list with `["proxychains4", "-q"]` prepended — never mutates input
  - `stop()` stops tor service
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 12.1 Write property test: TorManager wrap_command does not mutate input
    - **Property 13: TorManager wrap_command Does Not Mutate Input** — original list unchanged after wrap_command
    - **Validates: Requirements 9.5**

- [x] 13. Implement AegisBridge
  - Create `tools/external/aegis_bridge.py` with `AegisBridge` class
  - `is_available()` checks if aegis dir exists and binary is runnable
  - `ensure_installed()` clones aegis repo to `tools/external/aegis/` if not present
  - `run(target, phase)` invokes aegis CLI, parses output via `AEGIS_TYPE_MAP`, returns `ChainResult`; never raises
  - If aegis unavailable or fails, return `ChainResult(degraded=True)` with descriptive error in `tool_attempts`
  - Integrate into `FallbackChain.execute()`: attempt AegisBridge after all primary tools fail
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 13.1 Write property test: AegisBridge never raises
    - **Property 14: AegisBridge Never Raises** — run() always returns ChainResult, never raises
    - **Validates: Requirements 10.3**

- [x] 14. Implement XSSMethodology
  - Create `tools/methodology/xss_methodology.py` with `XSSMethodology` class
  - `reflected_xss(urls, waf)` runs dalfox and xsstrike against each URL with WAF bypass headers applied
  - `stored_xss(forms, waf)` injects payloads into discovered form fields
  - `dom_xss(js_files)` runs jsluice and jsvulns for source/sink analysis
  - `blind_xss(urls)` runs nuclei blind-xss templates
  - `csp_bypass(target)` tests JSONP endpoints, static nonce detection, unsafe-inline/eval directives
  - `run(target, urls, context)` orchestrates all above, deduplicates findings before returning
  - Apply WAF-specific encoding chains from `XSS_WAF_BYPASS_CHAINS` when WAF detected
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [x] 14.1 Write property test: XSSMethodology deduplicates findings
    - **Property 15: XSSMethodology Deduplicates Findings** — no duplicate Vulnerability objects in result
    - **Validates: Requirements 11.6**

- [x] 15. Implement SQLiMethodology
  - Create `tools/methodology/sqli_methodology.py` with `SQLiMethodology` class
  - `detect(url, param)` fingerprints injection type using sqlmap and ghauri
  - `exploit(url, param, technique, waf)` runs sqlmap with WAF tamper scripts from `WafBypassStrategy`
  - `enumerate_db(url, param)` runs `--dbs`, `--tables`, `--columns`, `--dump` pipeline
  - `escalate_privileges(url, param)` checks `--is-dba`, attempts `--os-shell` if DBA
  - `out_of_band(url, param, dns_domain)` runs `--dns-domain` exfiltration
  - `second_order(inject_url, trigger_url, param)` runs `--second-url` test
  - `run(target, params, context)` orchestrates all above, applies WAF bypass, deduplicates
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [x] 16. Checkpoint — Ensure methodology, WAF, Tor, and AegisBridge tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Extend ToolManager v2 with new tool registry and venv support
  - Update `tools/tool_manager.py` to use `PHASE_TOOLS_2025` registry (7 phases, 6 tools each)
  - Add new tool class files for all new tools: `httpx_tool.py`, `dnsx_tool.py`, `katana_tool.py`, `gauplus_tool.py`, `feroxbuster_tool.py`, `arjun_tool.py`, `nikto_tool.py`, `dalfox_tool.py`, `ghauri_tool.py`, `sqlmap_tool.py`, `commix_tool.py`, `xsstrike_tool.py`, `linpeas_tool.py`, `crackmapexec_tool.py`, `chisel_tool.py`, `jsvulns_tool.py`, `reconftw_tool.py`
  - Each new tool extends `BaseTool` with `check_installed`, `build_command`, `parse_output` using `TOOL_PARSE_RULES`
  - Integrate `ToolVenvManager` into `ToolManager`: tools with `venv_packages` get their venv Python path injected
  - Integrate `WafBypassStrategy` into `SqlmapTool` and `NucleiTool` command building
  - _Requirements: 2.1, 7.4, 7.5, 18.1_

- [x] 18. Upgrade Orchestrator to OrchestratorV2
  - Extend `core/orchestrator.py` to use `PhaseManager` for the 7-phase pipeline
  - After recon phase, run `WafDetector.detect(target)` and store `WafResult` in `ScanContext`
  - If `config.mode == "stealth"`, initialize `TorManager`, start Tor, inject `wrap_command` into tool subprocess calls; log warning and continue if Tor fails to start within 30s
  - Generate todo list via `AIEngine.generate_todo_list` at scan start, emit via `RealTimeEmitter`
  - After each phase, call `AIEngine.analyze_phase` and store `AIDecision` in `ScanContext`
  - Persist `ScanContext` via `StateBridge` after each phase
  - Emit `scan_complete` with `FinalReport` after all 7 phases
  - Gate exploitation-phase tools behind `--mode=exploit` check; gate Sliver behind explicit consent prompt
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 7.1, 9.1, 9.3, 18.3_

  - [x] 18.1 Write property test: Full scan never raises
    - **Property 1: Full Scan Never Raises** — run_full_scan(target) returns FinalReport without raising for any valid target
    - **Validates: Requirements 1.2, 1.4**

- [x] 19. Implement TerminalLauncher
  - Create `web/terminal_launcher.py` with `TerminalLauncher` class
  - `launch(tools)` spawns PTY-backed `/bin/bash` with all tool binaries on PATH, returns `TerminalSession` with unique `session_id`
  - Stream stdout/stderr to SocketIO channel `terminal_output` in a dedicated thread per session
  - `write(session_id, data)` writes to PTY stdin
  - `resize(session_id, rows, cols)` resizes PTY via `fcntl.ioctl`
  - `kill(session_id)` terminates PTY process
  - If `pty.openpty()` fails, return `None` — scan continues normally with terminal feature disabled
  - Bind PTY WebSocket only to `127.0.0.1`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 18.4_

  - [x] 19.1 Write unit tests for TerminalLauncher
    - Test PTY spawn failure returns None and scan continues
    - Test session_id uniqueness across concurrent sessions
    - _Requirements: 5.5, 5.6_

  - [x] 19.2 Write property test: TerminalSession unique IDs
    - **Property 19: TerminalSession Unique IDs** — all concurrent sessions have distinct session_ids
    - **Validates: Requirements 5.6**

- [x] 20. Implement TLS transport for web interface
  - Create `web/tls_manager.py` with `ensure_tls_cert()` function
  - Generate self-signed cert at `.hackempire/tls/cert.pem` and `.hackempire/tls/key.pem` using `openssl` subprocess if not present
  - If cert and key already exist, reuse without regenerating
  - Update `web/app.py` to call `ensure_tls_cert()` and start Flask with `ssl_context=(cert_file, key_file)` on port 5443
  - Update CLI backend URL to `https://127.0.0.1:5443` with `verify=False`
  - _Requirements: 17.1, 17.2, 17.3, 17.4_

- [x] 21. Upgrade web dashboard routes and templates
  - Add SocketIO event handlers to `web/app.py` for `terminal_input` and `terminal_resize`
  - Add export routes to `web/routes.py`: `GET /api/export/<format>` supporting pdf, json, html, markdown, csv; return HTTP 400 with JSON error body for unknown formats
  - Create `web/exporters/markdown_export.py` and `web/exporters/csv_export.py`
  - Update `web/templates/dashboard.html` with live vulnerability feed panel (SocketIO `vuln_found`), phase progress rings (Chart.js donut), AI Decision Panel, xterm.js terminal tab
  - Create `web/static/hacker-theme.css` with dark hacker theme variables and severity-specific finding card border colors
  - Update `web/templates/base.html` to include xterm.js v5, socket.io-client v4, Chart.js v4 CDN scripts and hacker-theme.css
  - Add WebSocket reconnect logic in dashboard JS: on disconnect, fetch `/api/state` to replay missed events
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [x] 21.1 Write unit tests for export routes
    - Test each valid format returns correct MIME type
    - Test unknown format returns HTTP 400 with JSON error body containing the format name
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [x] 21.2 Write property test: Export MIME type correctness
    - **Property 18: Export MIME Type Correctness** — each valid format string returns the correct MIME type
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**

- [x] 22. Upgrade CLI commands
  - Update `cli/commands.py` to add `scan` command with `--mode` (recon-only, full, exploit, stealth) and `--resume` flag
  - Add `status` command displaying phase progress bars via Rich
  - Add `report` command with `--format` option (pdf, json, html, markdown, csv)
  - Add `install-tools` command invoking `DependencyResolver`
  - Add `terminal` command opening web terminal in default browser
  - Add `config` command accepting key/value to write to `.hackempire/config.json`
  - Require explicit user confirmation before proceeding when `--mode=exploit`
  - Set rate limit to 2 rps with 500-3000ms jitter when `--mode=stealth`
  - Create `cli/progress.py` with `render_phase_progress` and `render_finding` using Rich with `HACKER_THEME`
  - Add `rich>=13.7.0` to `requirements.txt`
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10_

- [x] 23. Extend target validation and security constraints
  - Update `utils/validator.py` to validate target against domain/IP regex before any tool execution
  - Ensure all new tool subprocesses use `shell=False`
  - Disable exploitation-phase tools when mode is not "exploit"
  - Sanitize all user-controlled strings in `web/pdf_report.py` and new HTML/Markdown exporters before rendering
  - _Requirements: 18.1, 18.2, 18.3, 18.6_

- [x] 24. Wire all components together and update main entry point
  - Update `main.py` to instantiate `OrchestratorV2` with all new subsystems
  - Ensure `PhaseManager`, `FallbackChain`, `RealTimeEmitter`, `AIEngine`, `TodoPlanner`, `TorManager`, `WafDetector`, `TerminalLauncher`, and `DependencyResolver` are all wired through `Orchestrator`
  - Update `web/state_bridge.py` to persist full `ScanContext` including todo_list, ai_decisions, waf_result
  - Verify `GET /api/state` returns complete `ScanContext` for dashboard reconnect replay
  - _Requirements: 1.6, 4.7, 14.7_

- [x] 25. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use the `hypothesis` library as specified in the design
- The existing BaseTool, ToolManager, Orchestrator, StateManager, and Flask web layer are extended, not rewritten
