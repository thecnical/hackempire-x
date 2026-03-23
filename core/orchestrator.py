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

