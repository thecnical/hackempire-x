from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import Callable
import json
import os
from typing import Any, Optional

from core.config import Config
from core.context_manager import ContextManager
from core.phases import Phase
from core.state_manager import StateManager
from ai.ai_client import AIClient
from ai.prompt_builder import PromptBuilder
from ai.response_parser import ResponseParser
from utils.logger import Logger
from tools.tool_manager import ToolManager
from tools.health_tracker import ToolHealthTracker
from installer.dependency_checker import DependencyChecker
from installer.tool_installer import ToolInstaller
from installer.tool_doctor import ToolDoctor

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True, slots=True)
class PhaseResult:
    name: str
    status: str


PhaseHook = Callable[[str, str], None]


class Orchestrator:
    def __init__(
        self,
        *,
        config: Config,
        logger: Logger,
        phase_hook: Optional[PhaseHook] = None,
    ) -> None:
        self._config = config
        self._logger = logger
        self._phase_hook = phase_hook
        self.state = StateManager()
        self.context = ContextManager(config, self.state)
        self._prompt_builder = PromptBuilder()
        self._response_parser = ResponseParser()
        self._ai_client: Optional[AIClient] = None
        self._health_tracker = ToolHealthTracker()

        timeout_s_str = os.environ.get("HACKEMPIRE_TOOL_TIMEOUT_S", "60")
        try:
            timeout_s = float(timeout_s_str)
        except ValueError:
            timeout_s = 60.0

        max_workers_str = os.environ.get("HACKEMPIRE_MAX_WORKERS", "4")
        try:
            max_workers = int(max_workers_str)
        except ValueError:
            max_workers = 4

        web_scheme = os.environ.get("HACKEMPIRE_WEB_SCHEME", "http")
        execution_mode = "parallel" if self._config.mode in ("pro", "lab") else "sequential"
        self._tool_manager = ToolManager(
            logger=self._logger,
            timeout_s=timeout_s,
            execution_mode=execution_mode,
            max_workers=max_workers,
            web_scheme=web_scheme,
            health_tracker=self._health_tracker,
            proxy=self._config.proxy,
        )

        if self._config.ai_key:
            base_url = os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_DEFAULT_BASE_URL)
            model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct")
            timeout_s_str = os.environ.get("OPENROUTER_TIMEOUT_S", "15.0")
            try:
                timeout_s = float(timeout_s_str)
            except ValueError:
                timeout_s = 15.0
            self._ai_client = AIClient(
                api_key=self._config.ai_key,
                base_url=base_url,
                model=model,
                timeout_s=timeout_s,
            )

        # Installer engine — auto_approve=True in pro/lab mode (no interactive prompts)
        auto_approve = self._config.mode in ("pro", "lab")
        self._installer = ToolInstaller(
            logger=self._logger,
            mode=self._config.mode,
            auto_approve=auto_approve,
        )
        self._dep_checker = DependencyChecker(logger=self._logger)
        self._tool_doctor = ToolDoctor(
            logger=self._logger,
            installer=self._installer,
            mode=self._config.mode,
        )

    def initialize(self) -> None:
        self._logger.info("Initializing HackEmpire X (Phase 1)...")
        self._logger.info(f"Mode selected: {self._config.mode}")
        self._logger.info(f"Target: {self._config.target}")
        if self._config.web_enabled:
            self._logger.info("Web dashboard enabled — state will be written after each phase.")
        if self._config.ai_key:
            self._logger.info("AI key provided (stored for future phases).")

        # --- Dependency check ---
        dep_report = self._dep_checker.run()
        if not dep_report.python_ok:
            self._logger.error(
                f"[init] Python version check failed: {dep_report.python_version}. "
                "Execution may be unstable."
            )
        if dep_report.missing_packages:
            self._logger.warning(
                f"[init] Missing pip packages: {dep_report.missing_packages}. "
                "Run: pip install " + " ".join(dep_report.missing_packages)
            )

        # --- Tool installation ---
        all_tool_names = [
            name
            for phase_tools in self._tool_manager.TOOL_REGISTRY.values()
            for name in [cls.name for cls in phase_tools]
        ]
        install_results = self._installer.ensure_tools(all_tool_names)
        for result in install_results:
            if result.status == "failed":
                self._logger.warning(
                    f"[init] Tool '{result.tool}' could not be installed: {result.message}"
                )

    def _hook(self, phase: Phase, event: str) -> None:
        if self._phase_hook is None:
            return
        self._phase_hook(phase.value, event)

    def _run_single_phase(
        self,
        phase: Phase,
        *,
        ai_tool_priorities: Optional[list[str]],
    ) -> tuple[PhaseResult, Optional[list[str]]]:
        """
        Run one phase with robust error handling.
        Ordering (required by spec): set_phase -> log start -> run tools -> update state -> build context.
        """
        self.state.set_phase(phase)
        self._hook(phase, "start")
        self._logger.info(f"Phase transition: {phase.value}")

        try:
            skip, reason = self._should_skip_phase_tools(phase)
            if skip:
                self._logger.warning(
                    f"Skipping tool execution for phase '{phase.value}': {reason}"
                )
                tool_results = self._empty_tool_results_for_phase(phase, reason)
                self.state.update(phase, tool_results)
            else:
                self._logger.info(f"Executing phase tools for '{phase.value}'...")
                tool_results = self._tool_manager.run_phase_tools(
                    phase=phase,
                    target=self._config.target,
                    ai_tool_priorities=ai_tool_priorities,
                )
                self.state.update(phase, tool_results)
                # Sync tool health into StateManager for AI context.
                self.state.update_tool_health(tool_results.get("tool_status", {}))
                self._logger.info(
                    f"State updated for phase '{phase.value}' with keys: {list(tool_results.keys())}"
                )
            self._logger.info(f"Building AI-ready context for phase '{phase.value}'...")
            context = self.context.build_context()
            self._logger.info(
                f"Context generated for phase '{phase.value}' (data keys: {list(context['data'].keys())})."
            )

            suggested_tools = self._run_ai_decision_if_enabled(phase, context)

            # Persist state for web GUI (near real-time) — lazy import avoids
            # hard dependency on Flask when --web is not used.
            if self._config.web_enabled:
                try:
                    from web.state_bridge import write_state  # noqa: PLC0415
                    write_state(
                        target=self._config.target,
                        mode=self._config.mode,
                        current_phase=self.state.current_phase or "",
                        data=self.state.get_all(),
                        tool_health=self.state.get_tool_health(),
                    )
                except Exception:
                    pass  # never crash the scan over a GUI write

            self._hook(phase, "success")
            self._logger.success(f"{phase.value} phase completed.")
            return PhaseResult(name=phase.value, status="success"), suggested_tools
        except Exception as exc:
            self._logger.error(f"Phase '{phase.value}' failed; continuing to next phase.", exc=exc)
            self._hook(phase, "error")
            return PhaseResult(name=phase.value, status="error"), None

    def _should_skip_phase_tools(self, phase: Phase) -> tuple[bool, str]:
        """
        Smart skip logic based on prior state and tool health.
        """
        if phase is Phase.RECON:
            return False, ""

        # If recon tools all failed/timed out, no reliable data — skip downstream.
        tool_health = self.state.get_tool_health()
        recon_tool_names = self._tool_manager.get_phase_tool_names(Phase.RECON)
        recon_statuses = [tool_health.get(n, "unknown") for n in recon_tool_names]
        all_recon_unhealthy = recon_tool_names and all(
            s in ("failed", "timeout", "not_installed") for s in recon_statuses
        )
        if all_recon_unhealthy:
            return True, "All recon tools failed or timed out — no reliable data for downstream phases."

        # Recon prerequisites for downstream phases.
        recon_data = self.state.get_phase_data(Phase.RECON.value)
        recon_ports = recon_data.get("ports") if isinstance(recon_data.get("ports"), list) else []
        recon_subdomains = recon_data.get("subdomains") if isinstance(recon_data.get("subdomains"), list) else []

        if not recon_ports:
            # No open ports -> avoid deeper enum/vuln steps.
            return True, "No open ports found in recon (ports closed)."

        if phase is Phase.ENUM:
            # Heuristic: if there are open ports but nothing suggests web exposure, skip heavy enum.
            has_web_hint = False
            for p in recon_ports:
                if not isinstance(p, dict):
                    continue
                service = str(p.get("service", "")).lower()
                if "http" in service or "https" in service:
                    has_web_hint = True
                    break

            if not recon_subdomains and not has_web_hint:
                return True, "No subdomains and no web service hint found in recon."

            return False, ""

        # Phase.VULN
        enum_data = self.state.get_phase_data(Phase.ENUM.value)
        enum_urls = enum_data.get("urls") if isinstance(enum_data.get("urls"), list) else []
        if not enum_urls:
            return True, "No URLs found in enum (skip vulnerability scanning)."

        return False, ""

    def _empty_tool_results_for_phase(self, phase: Phase, reason: str) -> dict[str, Any]:
        tool_names = self._tool_manager.get_phase_tool_names(phase)
        tool_status = {name: "skipped" for name in tool_names}
        # Record skipped tools in health tracker.
        for name in tool_names:
            self._health_tracker.record(name, "skipped")
        self.state.update_tool_health(tool_status)
        self._logger.info(
            f"Tool results placeholder created for phase '{phase.value}' (reason: {reason})."
        )
        return {
            "ports": [],
            "subdomains": [],
            "urls": [],
            "vulnerabilities": [],
            "tool_status": tool_status,
        }

    def _run_ai_decision_if_enabled(
        self,
        phase: Phase,
        context: dict[str, object],
    ) -> Optional[list[str]]:
        """
        AI step is best-effort:
        - on any failure, log and continue execution
        - never crashes the main phase loop
        """
        if self._ai_client is None:
            self._logger.info("AI step skipped (no --ai-key provided).")
            return None

        try:
            prompt = self._prompt_builder.build_prompt(context, phase.value)
            prompt_short = prompt.replace("\n", " ")[:500]
            self._logger.info(f"AI prompt sent (short): {prompt_short}...")

            response = self._ai_client.send_request(prompt)
            raw_text = response.get("raw_text", "") if isinstance(response, dict) else ""
            resp_short = raw_text.replace("\n", " ")[:500]
            self._logger.info(f"AI response received (short): {resp_short}...")

            parsed = self._response_parser.extract_json(raw_text)
            parsed_short = json.dumps(parsed, ensure_ascii=False)[:500]
            self._logger.info(f"AI parsed output (short): {parsed_short}...")

            # If parsing failed, ResponseParser returns phase="fallback".
            if parsed.get("phase") == "fallback":
                self._logger.warning(f"AI returned fallback decision for phase '{phase.value}'. Skipping state update.")
                return None

            self.state.update(phase, {"ai_decision": parsed})
            self._logger.info(f"AI decision stored in state for phase '{phase.value}'.")
            tools_val = parsed.get("tools")
            if isinstance(tools_val, list) and all(isinstance(x, str) for x in tools_val):
                return tools_val
            return None
        except Exception as exc:
            # Best-effort: log and continue.
            self._logger.error(f"AI decision step failed for phase '{phase.value}'; continuing without AI.", exc=exc)
            return None

    def run(self) -> list[PhaseResult]:
        self._logger.info("Starting orchestrated run with state + context (Phase 1 only)...")

        phases: list[Phase] = [Phase.RECON, Phase.ENUM, Phase.VULN]
        results: list[PhaseResult] = []
        ai_tool_priorities: Optional[list[str]] = None
        for phase in phases:
            phase_result, ai_tool_priorities = self._run_single_phase(
                phase,
                ai_tool_priorities=ai_tool_priorities,
            )
            results.append(phase_result)
            time.sleep(0.2)

        # --- Tool Doctor: diagnose and attempt fixes on unhealthy tools ---
        all_tool_status = dict(self._health_tracker.snapshot())
        if any(s not in ("ok", "skipped", "already_installed") for s in all_tool_status.values()):
            self._logger.info("[doctor] Running Tool Doctor on unhealthy tools...")
            doctor_reports = self._tool_doctor.diagnose_and_fix(all_tool_status)
            summary = self._tool_doctor.generate_summary(doctor_reports)
            self._logger.info(
                f"[doctor] Summary: {summary['total_issues']} issues, "
                f"{summary['fixed']} fixed, "
                f"{len(summary['manual_action_required'])} need manual action."
            )
            for item in summary["manual_action_required"]:
                self._logger.warning(
                    f"[doctor] Manual fix required — {item['tool']}: {item['suggestion']}"
                )

        self._logger.success("Orchestration complete for Phase 1 (tool execution attempted).")
        return results



# ---------------------------------------------------------------------------
# OrchestratorV2 — 7-phase pipeline with PhaseManager, WAF, Tor, AI, Emitter
# ---------------------------------------------------------------------------

import uuid as _uuid
from datetime import datetime as _datetime, timezone as _timezone
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from hackempire.ai.ai_engine import AIEngine
    from hackempire.core.phase_manager import PhaseManager
    from hackempire.web.realtime_emitter import RealTimeEmitter


class OrchestratorV2:
    """7-phase orchestrator wrapping PhaseManager with WAF, Tor, AI, and emitter support."""

    def __init__(
        self,
        *,
        config: "Config",
        logger: "Logger",
        emitter: "RealTimeEmitter | None" = None,
        ai_engine: "AIEngine | None" = None,
        phase_manager: "PhaseManager | None" = None,
    ) -> None:
        self._config = config
        self._logger = logger
        self._emitter = emitter
        self._ai_engine = ai_engine
        self._phase_manager = phase_manager

    def run_full_scan(self, target: str) -> dict:
        """Execute the full 7-phase scan. Never raises — returns partial results on error."""
        try:
            return self._run_full_scan_impl(target)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"[OrchestratorV2] Unexpected top-level error: {exc}")
            return {
                "target": target,
                "session_id": "",
                "mode": self._config.mode,
                "started_at": "",
                "phase_results": {},
                "waf_result": None,
                "ai_decisions": {},
                "todo_list": None,
                "error": str(exc),
            }

    def _run_full_scan_impl(self, target: str) -> dict:
        from hackempire.core.models import ScanContext, TodoList  # noqa: PLC0415

        session_id = str(_uuid.uuid4())
        started_at = _datetime.now(_timezone.utc).isoformat()

        context = ScanContext(
            target=target,
            mode=self._config.mode,
            session_id=session_id,
            started_at=started_at,
            autonomous=getattr(self._config, "autonomous", False),
        )

        # v4.3 — Query RAG KB for prior findings before generating todo
        kb_manager = None
        try:
            from hackempire.core.kb_manager import KnowledgeBaseManager  # noqa: PLC0415
            kb_manager = KnowledgeBaseManager()
            prior_entries = kb_manager.search(target)
            if prior_entries:
                context.kb_entries = prior_entries
                self._logger.info(
                    f"[OrchestratorV2] RAG KB: found {len(prior_entries)} prior entries for {target}"
                )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"[OrchestratorV2] RAG KB query failed: {exc}")

        # Step 1: Generate todo list via AIEngine (or empty fallback)
        todo = self._generate_todo(target, context)
        context.todo_list = todo

        # Step 2: Emit todo update
        if self._emitter is not None:
            try:
                self._emitter.emit_todo_update(todo)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] Failed to emit todo update: {exc}")

        # Step 3: Stealth mode — start Tor before any tool runs
        if self._config.mode == "stealth":
            self._start_tor()

        # v4.2 — Initialize AutonomousEngine if autonomous mode is active
        autonomous_engine = None
        if getattr(self._config, "autonomous", False) and self._ai_engine is not None:
            try:
                from hackempire.ai.autonomous_engine import AutonomousEngine  # noqa: PLC0415
                autonomous_engine = AutonomousEngine(ai_engine=self._ai_engine)
                self._logger.info("[OrchestratorV2] Autonomous mode active")
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] AutonomousEngine init failed: {exc}")

        # Step 4: Run all 7 phases via PhaseManager
        if self._phase_manager is not None:
            self._run_phases(self._phase_manager, target, context)
        else:
            self._logger.warning("[OrchestratorV2] No PhaseManager provided — phases will be skipped.")

        # Step 5: Emit scan_complete with final report
        final_report = self._build_final_report(context)

        # v4.3 — Write scan results to RAG KB
        if kb_manager is not None:
            try:
                from hackempire.core.models import KBEntry  # noqa: PLC0415
                from hackempire.core.phases import Phase  # noqa: PLC0415
                from datetime import datetime as _dt, timezone as _tz  # noqa: PLC0415
                vuln_data = context.phase_results.get(Phase.VULN_SCAN.value, {})
                vulns = vuln_data.get("vulnerabilities", []) if isinstance(vuln_data, dict) else []
                findings = []
                for v in vulns:
                    if hasattr(v, "name"):
                        findings.append({"name": v.name, "url": v.url, "severity": v.severity})
                    elif isinstance(v, dict):
                        findings.append(v)
                kb_entry = KBEntry(
                    target=target,
                    findings=findings,
                    payloads=[],
                    attack_patterns=[],
                    timestamp=_dt.now(_tz.utc).isoformat(),
                )
                kb_manager.write(kb_entry)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] RAG KB write failed: {exc}")
        if self._emitter is not None:
            try:
                self._emitter.emit_scan_complete(final_report)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] Failed to emit scan_complete: {exc}")

        return final_report

    def _generate_todo(self, target: str, context: Any) -> Any:
        """Generate todo list via AIEngine or return empty TodoList."""
        from hackempire.core.models import TodoList  # noqa: PLC0415

        if self._ai_engine is not None:
            try:
                return self._ai_engine.generate_todo_list(target, context)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] AI todo generation failed: {exc}")

        return TodoList(
            target=target,
            phases={},
            created_at=_datetime.now(_timezone.utc).isoformat(),
        )

    def _start_tor(self) -> None:
        """Initialize and start TorManager. Log warning if Tor fails to start within 30s."""
        try:
            from hackempire.core.tor_manager import TorManager  # noqa: PLC0415

            tor = TorManager()
            started = tor.start()
            if not started:
                self._logger.warning(
                    "[OrchestratorV2] Tor failed to start within 30s — "
                    "continuing scan without anonymization."
                )
            else:
                self._logger.info("[OrchestratorV2] Tor started successfully.")
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                f"[OrchestratorV2] TorManager initialization failed: {exc} — "
                "continuing without anonymization."
            )

    def _run_phases(self, phase_manager: Any, target: str, context: Any) -> None:
        """Run all 7 phases in order, applying post-phase hooks after each."""
        from hackempire.core.phases import Phase  # noqa: PLC0415

        # v4.2 — Initialize AutonomousEngine if autonomous mode is active
        autonomous_engine = None
        if getattr(context, "autonomous", False) and self._ai_engine is not None:
            try:
                from hackempire.ai.autonomous_engine import AutonomousEngine  # noqa: PLC0415
                autonomous_engine = AutonomousEngine(ai_engine=self._ai_engine)
                self._logger.info("[OrchestratorV2] Autonomous mode active — AutonomousEngine initialized")
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(f"[OrchestratorV2] AutonomousEngine init failed: {exc}")

        for phase in phase_manager.PHASES:
            # Gate exploitation phase behind --mode=exploit
            # Satisfies Requirement 18.3: exploitation-phase tools are disabled when mode != "exploit"
            if phase is Phase.EXPLOITATION and self._config.mode != "exploit":
                self._logger.warning(
                    "[OrchestratorV2] Skipping EXPLOITATION phase — "
                    "requires --mode=exploit (current mode: %s).",
                    self._config.mode,
                )
                context.phase_results[phase.value] = {
                    "skipped": True,
                    "reason": "mode != exploit",
                }
                continue

            # Run the phase (PhaseManager.run_phase never raises)
            try:
                if autonomous_engine is not None:
                    phase_result = autonomous_engine.run_phase_loop(
                        phase=phase,
                        target=target,
                        context=context,
                        phase_manager=phase_manager,
                        emitter=self._emitter,
                    )
                else:
                    phase_result = phase_manager.run_phase(phase, target, context)
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    f"[OrchestratorV2] Phase '{phase.value}' raised unexpectedly: {exc}"
                )
                phase_result = None

            # Store phase result in context
            if phase_result is not None:
                context.phase_results[phase.value] = phase_result

            # After RECON: run WAF detection and store in context
            if phase is Phase.RECON:
                context.waf_result = self._detect_waf(target)

            # After each phase: AI analysis -> store AIDecision in context
            if self._ai_engine is not None and phase_result is not None:
                try:
                    ai_decision = self._ai_engine.analyze_phase(
                        phase.value, phase_result, context
                    )
                    context.ai_decisions[phase.value] = ai_decision
                except Exception as exc:  # noqa: BLE001
                    self._logger.warning(
                        f"[OrchestratorV2] AI analysis failed for phase '{phase.value}': {exc}"
                    )

            # After VULN_SCAN: run false positive filter + emit finding_update events
            if phase is Phase.VULN_SCAN:
                if self._ai_engine is not None:
                    try:
                        raw_vulns = context.phase_results.get(phase.value, {})
                        if isinstance(raw_vulns, dict):
                            vulns_list = raw_vulns.get("vulnerabilities", [])
                            if vulns_list:
                                filtered = self._ai_engine.filter_false_positives(vulns_list)
                                filtered_count = len(vulns_list) - len(filtered)
                                if filtered_count > 0:
                                    self._logger.info(
                                        f"[OrchestratorV2] FP filter: removed {filtered_count} "
                                        f"false positives from {len(vulns_list)} findings"
                                    )
                                raw_vulns["vulnerabilities"] = filtered
                                raw_vulns["fp_filtered_count"] = filtered_count
                    except Exception as exc:  # noqa: BLE001
                        self._logger.warning(f"[OrchestratorV2] FP filter failed: {exc}")

                # Emit finding_update for each confirmed vulnerability (v4.6)
                if self._emitter is not None:
                    try:
                        from hackempire.ai.mitre_mapper import map_finding  # noqa: PLC0415
                        raw_vulns = context.phase_results.get(phase.value, {})
                        vulns_list = raw_vulns.get("vulnerabilities", []) if isinstance(raw_vulns, dict) else []
                        for vuln in vulns_list:
                            try:
                                name = vuln.name if hasattr(vuln, "name") else str(vuln.get("name", ""))
                                host = vuln.target if hasattr(vuln, "target") else str(vuln.get("target", target))
                                url = vuln.url if hasattr(vuln, "url") else str(vuln.get("url", ""))
                                mitre = map_finding(name)
                                finding_payload = {
                                    "host": host,
                                    "service": url,
                                    "exploit_path": url,
                                    "technique_id": mitre["technique_id"],
                                    "tactic": mitre["tactic"],
                                    "name": name,
                                }
                                self._emitter.emit_finding_update(finding_payload)
                            except Exception:  # noqa: BLE001
                                pass
                    except Exception as exc:  # noqa: BLE001
                        self._logger.warning(f"[OrchestratorV2] emit_finding_update failed: {exc}")

            # After REPORTING phase: auto-generate PoC + H1 reports
            if phase is Phase.REPORTING and self._ai_engine is not None:
                self._generate_poc_and_reports(context)

            # After each phase: persist context via StateBridge
            if self._config.web_enabled:
                self._persist_context(context)

    def _generate_poc_and_reports(self, context: Any) -> None:
        """
        Phase 3: Auto-generate PoC + HackerOne reports for all verified vulns.
        Saves reports to ./h1_reports/ directory. Never raises.
        """
        try:
            from hackempire.core.phases import Phase  # noqa: PLC0415
            # Collect all vulnerabilities from vuln_scan phase
            vuln_data = context.phase_results.get(Phase.VULN_SCAN.value, {})
            if not isinstance(vuln_data, dict):
                return
            vulns = vuln_data.get("vulnerabilities", [])
            if not vulns:
                self._logger.info("[OrchestratorV2] No vulnerabilities to generate PoC for")
                return

            self._logger.info(f"[OrchestratorV2] Generating PoC for {len(vulns)} vulnerabilities...")

            # Generate PoCs
            pocs = self._ai_engine.generate_poc(vulns)
            self._logger.success(f"[OrchestratorV2] Generated {len(pocs)} PoCs")

            # Generate H1 reports
            reports = self._ai_engine.generate_h1_reports(vulns, pocs)
            self._logger.success(f"[OrchestratorV2] Generated {len(reports)} H1 reports")

            # Save reports
            from hackempire.ai.report_writer import ReportWriter  # noqa: PLC0415
            writer = ReportWriter(ai_engine=self._ai_engine)
            saved = writer.save_all(reports, output_dir="./h1_reports")
            writer.save_json(reports, output_path="./h1_reports/all_reports.json")

            if saved:
                self._logger.success(
                    f"[OrchestratorV2] H1 reports saved to ./h1_reports/ "
                    f"({len(saved)} files)"
                )

            # Store in context for dashboard
            context.phase_results["poc_reports"] = {
                "pocs": [{"vuln": p.vuln_name, "payload": p.payload, "curl": p.curl_command} for p in pocs],
                "h1_reports": [r.to_dict() for r in reports],
                "saved_files": saved,
            }

        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"[OrchestratorV2] PoC/Report generation failed: {exc}")

    def _detect_waf(self, target: str) -> Any:
        """Run WafDetector.detect(target) and return WafResult. Never raises."""
        try:
            from hackempire.tools.waf.waf_detector import WafDetector  # noqa: PLC0415

            detector = WafDetector()
            waf_result = detector.detect(target)
            self._logger.info(
                f"[OrchestratorV2] WAF detection: detected={waf_result.detected}, "
                f"vendor={waf_result.vendor}"
            )
            return waf_result
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"[OrchestratorV2] WAF detection failed: {exc}")
            return None

    def _persist_context(self, context: Any) -> None:
        """Persist ScanContext via StateBridge. Never raises."""
        try:
            from hackempire.web.state_bridge import write_state  # noqa: PLC0415

            def _to_dict(obj: Any) -> Any:
                return obj.__dict__ if hasattr(obj, "__dict__") else obj

            write_state(
                target=context.target,
                mode=context.mode,
                current_phase="",
                data={
                    "phase_results": {
                        k: _to_dict(v)
                        for k, v in context.phase_results.items()
                    },
                },
                tool_health=context.tool_health,
                todo_list=_to_dict(context.todo_list) if context.todo_list is not None else None,
                ai_decisions={
                    k: _to_dict(v)
                    for k, v in context.ai_decisions.items()
                },
                waf_result=_to_dict(context.waf_result) if context.waf_result is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"[OrchestratorV2] StateBridge persist failed: {exc}")

    def _build_final_report(self, context: Any) -> dict:
        """Build the final report dict from ScanContext."""
        return {
            "target": context.target,
            "session_id": context.session_id,
            "mode": context.mode,
            "started_at": context.started_at,
            "phase_results": context.phase_results,
            "waf_result": context.waf_result,
            "ai_decisions": context.ai_decisions,
            "todo_list": context.todo_list,
        }
