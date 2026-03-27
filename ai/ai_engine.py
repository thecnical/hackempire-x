"""
AIEngine v2 — AI-powered pentesting intelligence for HackEmpire X.

Extends AIClient with:
- generate_todo_list: 7-phase x 6-task todo generation with KB fallback
- analyze_phase: per-phase AI decision making
- suggest_exploits: exploit suggestion from vulnerability list
- generate_report_summary: executive summary generation

Security: all tool output is JSON-parsed before inclusion in prompts
to prevent prompt injection (Requirement 18.5).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from hackempire.ai.ai_client import AIClient
from hackempire.ai.bytez_client import BytezClient
from hackempire.ai.pentest_kb import PHASE_ORDER, PentestKnowledgeBase
from hackempire.core.models import AIDecision, TodoList, TodoTask, Vulnerability

logger = logging.getLogger(__name__)

# Number of phases and tasks per phase required by spec
_REQUIRED_PHASES = 7
_TASKS_PER_PHASE = 6


def _safe_json_parse(raw: Any) -> Any:
    """
    JSON-parse a value if it is a string, otherwise return it as-is.

    Used to sanitize tool output before embedding in AI prompts
    (prevents prompt injection via raw tool output — Req 18.5).
    """
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            # Return as a JSON-safe escaped string rather than raw text
            return raw
    return raw


def _sanitize_context_for_prompt(context: Any) -> str:
    """
    Serialize context to a JSON string, JSON-parsing any string values
    that look like tool output to prevent prompt injection.
    """
    if context is None:
        return "null"
    if isinstance(context, dict):
        sanitized: dict[str, Any] = {}
        for k, v in context.items():
            sanitized[str(k)] = _safe_json_parse(v)
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    try:
        return json.dumps(_safe_json_parse(context), ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({})


def _extract_todo_from_response(raw_text: str, target: str) -> TodoList | None:
    """
    Attempt to parse a TodoList from the AI response text.

    Returns None if parsing fails or the structure is invalid.
    """
    if not raw_text or not raw_text.strip():
        return None

    # Try to find a JSON object in the response
    text = raw_text.strip()
    # Strip markdown fences if present
    if "```" in text:
        start = text.find("```")
        end = text.find("```", start + 3)
        if end > start + 3:
            inner = text[start + 3:end].lstrip("\n")
            if inner and not inner.lstrip().startswith("{"):
                inner = "\n".join(inner.splitlines()[1:])
            text = inner

    # Find the first JSON object
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    try:
        data = json.loads(text[brace_start:])
    except (json.JSONDecodeError, ValueError):
        # Try raw_decode to find first valid object
        decoder = json.JSONDecoder()
        pos = brace_start
        data = None
        while pos < len(text):
            try:
                data, _ = decoder.raw_decode(text, pos)
                break
            except json.JSONDecodeError:
                pos = text.find("{", pos + 1)
                if pos == -1:
                    break
        if data is None:
            return None

    if not isinstance(data, dict):
        return None

    # Expect {"phases": {"recon": [{"description": ..., "tool": ...}, ...], ...}}
    phases_raw = data.get("phases")
    if not isinstance(phases_raw, dict):
        return None

    if len(phases_raw) != _REQUIRED_PHASES:
        return None

    phases: dict[str, list[TodoTask]] = {}
    for phase_name, tasks_raw in phases_raw.items():
        if not isinstance(tasks_raw, list) or len(tasks_raw) != _TASKS_PER_PHASE:
            return None
        tasks: list[TodoTask] = []
        for i, task_raw in enumerate(tasks_raw):
            if not isinstance(task_raw, dict):
                return None
            description = task_raw.get("description", "")
            tool = task_raw.get("tool", "")
            if not description or not tool:
                return None
            tasks.append(TodoTask(index=i, description=str(description), tool=str(tool), status="pending"))
        phases[phase_name] = tasks

    return TodoList(
        target=target,
        phases=phases,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _validate_todo_structure(todo: TodoList) -> bool:
    """Return True iff the TodoList has exactly 7 phases with 6 tasks each."""
    if not isinstance(todo, TodoList):
        return False
    if len(todo.phases) != _REQUIRED_PHASES:
        return False
    for tasks in todo.phases.values():
        if len(tasks) != _TASKS_PER_PHASE:
            return False
    return True


class AIEngine(AIClient):
    """
    AI-powered pentesting intelligence engine.

    Provider priority:
      1. Bytez AI (primary) — https://bytez.com
      2. OpenRouter (fallback) — https://openrouter.ai
      3. PentestKnowledgeBase (offline fallback)

    Pass bytez_key and/or openrouter_key. If both are set, Bytez is tried first.
    If Bytez fails or is not configured, OpenRouter is tried.
    If both fail, the offline KB is used.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        model: str = "meta-llama/llama-3-8b-instruct:free",
        knowledge_base: PentestKnowledgeBase | None = None,
        bytez_key: str = "",
        openrouter_key: str = "",
    ) -> None:
        # Support both old-style api_key and new explicit keys
        _openrouter_key = openrouter_key or api_key
        super().__init__(api_key=_openrouter_key, base_url=base_url, model=model)

        self._bytez_client: BytezClient | None = (
            BytezClient(api_key=bytez_key) if bytez_key else None
        )
        self._openrouter_available = bool(_openrouter_key)
        self._knowledge_base = knowledge_base if knowledge_base is not None else PentestKnowledgeBase()

    def _send(self, prompt: str) -> dict:
        """
        Send prompt using provider priority:
        1. Bytez AI (if key configured)
        2. OpenRouter (if key configured)
        3. Return empty response (triggers KB fallback)
        """
        # Try Bytez first
        if self._bytez_client is not None:
            resp = self._bytez_client.send_request(prompt)
            if resp.get("status_code") == 200 and resp.get("raw_text"):
                return resp
            logger.warning("Bytez AI unavailable (status=%s), trying OpenRouter...", resp.get("status_code"))

        # Try OpenRouter
        if self._openrouter_available:
            resp = self.send_request(prompt)
            if resp.get("status_code") == 200 and resp.get("raw_text"):
                return resp
            logger.warning("OpenRouter unavailable (status=%s), using KB fallback.", resp.get("status_code"))

        return {"raw_text": "", "status_code": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_todo_list(self, target: str, context: Any = None) -> TodoList:
        """
        Generate a 7-phase x 6-task TodoList for the given target.

        1. Calls AI API via send_request(prompt).
        2. Falls back to KB if status_code != 200 or raw_text is empty.
        3. Tries to parse response as JSON and extract a TodoList.
        4. Falls back to KB if parsing fails or structure is invalid.
        5. Always returns a valid TodoList — never raises.

        Validates: Requirements 3.1, 3.2
        """
        try:
            prompt = self._build_todo_prompt(target, context)
            response = self._send(prompt)

            status_code = response.get("status_code", 0)
            raw_text = response.get("raw_text", "")

            if status_code != 200 or not raw_text:
                logger.warning("AI API unavailable (status=%s), falling back to KB", status_code)
                return self._knowledge_base.get_default_todo(target)

            todo = _extract_todo_from_response(raw_text, target)
            if todo is None or not _validate_todo_structure(todo):
                logger.warning("AI response invalid or wrong structure, falling back to KB")
                return self._knowledge_base.get_default_todo(target)

            return todo

        except Exception as exc:  # noqa: BLE001
            logger.error("generate_todo_list error: %s — falling back to KB", exc)
            return self._knowledge_base.get_default_todo(target)

    def analyze_phase(self, phase: str, result: Any, context: Any = None) -> AIDecision:
        """
        Analyze a completed phase result and return an AIDecision.

        Tool output in result/context is JSON-parsed before prompt inclusion
        to prevent prompt injection (Req 18.5).

        Returns a safe default AIDecision on any failure.
        """
        try:
            prompt = self._build_phase_prompt(phase, result, context)
            response = self._send(prompt)

            status_code = response.get("status_code", 0)
            raw_text = response.get("raw_text", "")

            if status_code != 200 or not raw_text:
                return self._default_ai_decision(phase)

            decision = self._parse_ai_decision(phase, raw_text)
            return decision if decision is not None else self._default_ai_decision(phase)

        except Exception as exc:  # noqa: BLE001
            logger.error("analyze_phase error: %s", exc)
            return self._default_ai_decision(phase)

    def suggest_exploits(self, vulns: list[Vulnerability]) -> list[str]:
        """
        Return a list of exploit suggestion strings for the given vulnerabilities.

        Falls back to KB-derived suggestions on any failure.
        """
        try:
            if not vulns:
                return []

            prompt = self._build_exploit_prompt(vulns)
            response = self._send(prompt)

            status_code = response.get("status_code", 0)
            raw_text = response.get("raw_text", "")

            if status_code != 200 or not raw_text:
                return self._kb_exploit_suggestions(vulns)

            suggestions = self._parse_suggestions(raw_text)
            return suggestions if suggestions else self._kb_exploit_suggestions(vulns)

        except Exception as exc:  # noqa: BLE001
            logger.error("suggest_exploits error: %s", exc)
            return self._kb_exploit_suggestions(vulns)

    def filter_false_positives(
        self,
        vulns: list[Vulnerability],
        confidence_threshold: float = 0.60,
    ) -> list[Vulnerability]:
        """
        Filter false positives from a list of vulnerabilities.

        Uses FalsePositiveFilter with this AI engine for verification.
        Returns only real findings with confidence >= threshold.
        """
        try:
            from hackempire.ai.false_positive_filter import FalsePositiveFilter
            fp_filter = FalsePositiveFilter(
                ai_engine=self,
                confidence_threshold=confidence_threshold,
            )
            return fp_filter.filter(vulns)
        except Exception as exc:
            logger.warning(f"[fp_filter] Filter failed: {exc} — returning all findings")
            return vulns

    def generate_report_summary(self, full_state: dict) -> str:
        """
        Generate an executive summary string from the full scan state.

        Falls back to a static summary on any failure.
        """
        try:
            prompt = self._build_report_prompt(full_state)
            response = self._send(prompt)

            status_code = response.get("status_code", 0)
            raw_text = response.get("raw_text", "")

            if status_code != 200 or not raw_text:
                return self._static_report_summary(full_state)

            return raw_text.strip() or self._static_report_summary(full_state)

        except Exception as exc:  # noqa: BLE001
            logger.error("generate_report_summary error: %s", exc)
            return self._static_report_summary(full_state)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_todo_prompt(self, target: str, context: Any) -> str:
        context_json = _sanitize_context_for_prompt(context)
        phase_list = ", ".join(PHASE_ORDER)
        return (
            "You are an elite penetration testing AI.\n\n"
            f"Target: {target}\n"
            f"Context: {context_json}\n\n"
            "Generate a structured penetration testing todo list.\n"
            f"You MUST produce exactly 7 phases: {phase_list}\n"
            "Each phase MUST have exactly 6 tasks.\n"
            "Each task MUST have a non-empty 'description' and a 'tool' name.\n\n"
            "OUTPUT FORMAT (strict JSON only):\n"
            "{\n"
            '  "phases": {\n'
            '    "recon": [\n'
            '      {"description": "...", "tool": "..."},\n'
            "      ... (6 tasks total)\n"
            "    ],\n"
            '    "url_discovery": [...],\n'
            '    "enumeration": [...],\n'
            '    "vuln_scan": [...],\n'
            '    "exploitation": [...],\n'
            '    "post_exploit": [...],\n'
            '    "reporting": [...]\n'
            "  }\n"
            "}\n\n"
            "RULES: Output ONLY valid JSON. No explanation. No markdown."
        )

    def _build_phase_prompt(self, phase: str, result: Any, context: Any) -> str:
        # JSON-parse result and context to prevent prompt injection (Req 18.5)
        result_json = _sanitize_context_for_prompt(result)
        context_json = _sanitize_context_for_prompt(context)
        return (
            "You are an elite penetration tester and bug bounty hunter with 10+ years experience.\n\n"
            f"Current phase: {phase}\n"
            f"Phase results: {result_json}\n"
            f"Full scan context: {context_json}\n\n"
            "Analyze the results and decide the best next attack steps.\n\n"
            "Think like an attacker:\n"
            "- What attack surface was discovered?\n"
            "- What are the highest-value targets?\n"
            "- What vulnerabilities are most likely given the tech stack?\n"
            "- What tools should run next for maximum impact?\n\n"
            "OUTPUT FORMAT (strict JSON only):\n"
            "{\n"
            f'  "phase": "{phase}",\n'
            '  "summary": "Brief analysis of what was found",\n'
            '  "attack_surface": ["item1", "item2"],\n'
            '  "suggested_tools": ["tool1", "tool2"],\n'
            '  "exploit_chains": ["chain1: step1 -> step2"],\n'
            '  "priority_targets": ["url1", "url2"],\n'
            '  "vuln_hypotheses": ["possible vuln1", "possible vuln2"],\n'
            '  "confidence": 0.8\n'
            "}\n\n"
            "RULES: Output ONLY valid JSON. No explanation. No markdown. "
            "confidence must be 0.0-1.0."
        )

    def _build_exploit_prompt(self, vulns: list[Vulnerability]) -> str:
        # Serialize vulns safely
        vuln_data = [
            {
                "name": v.name,
                "severity": v.severity,
                "url": v.url,
                "cve_ids": v.cve_ids,
                "evidence": v.evidence,
            }
            for v in vulns
        ]
        vuln_json = json.dumps(vuln_data, ensure_ascii=False, default=str)
        return (
            "You are an elite penetration testing AI.\n\n"
            f"Vulnerabilities found:\n{vuln_json}\n\n"
            "Suggest specific exploit techniques for each vulnerability.\n"
            "OUTPUT FORMAT (strict JSON only):\n"
            '{"suggestions": ["suggestion1", "suggestion2", ...]}\n\n'
            "RULES: Output ONLY valid JSON. No explanation. No markdown."
        )

    def _build_report_prompt(self, full_state: dict) -> str:
        # JSON-parse all values in full_state to prevent prompt injection
        state_json = _sanitize_context_for_prompt(full_state)
        return (
            "You are an elite penetration testing AI.\n\n"
            f"Full scan state:\n{state_json}\n\n"
            "Write a concise executive summary of the penetration test findings.\n"
            "Include: overall risk level, critical findings, recommended remediation priorities.\n"
            "Output plain text only. No JSON. No markdown headers."
        )

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    def _parse_ai_decision(self, phase: str, raw_text: str) -> AIDecision | None:
        text = raw_text.strip()
        # Strip markdown fences
        if "```" in text:
            start = text.find("```")
            end = text.find("```", start + 3)
            if end > start + 3:
                inner = text[start + 3:end].lstrip("\n")
                if inner and not inner.lstrip().startswith("{"):
                    inner = "\n".join(inner.splitlines()[1:])
                text = inner

        brace_start = text.find("{")
        if brace_start == -1:
            return None

        try:
            data = json.loads(text[brace_start:])
        except (json.JSONDecodeError, ValueError):
            decoder = json.JSONDecoder()
            pos = brace_start
            data = None
            while pos < len(text):
                try:
                    data, _ = decoder.raw_decode(text, pos)
                    break
                except json.JSONDecodeError:
                    pos = text.find("{", pos + 1)
                    if pos == -1:
                        break
            if data is None:
                return None

        if not isinstance(data, dict):
            return None

        summary = str(data.get("summary", ""))
        suggested_tools = data.get("suggested_tools", [])
        exploit_chains = data.get("exploit_chains", [])
        confidence = data.get("confidence", 0.0)
        # New Phase 2 fields
        attack_surface = data.get("attack_surface", [])
        priority_targets = data.get("priority_targets", [])
        vuln_hypotheses = data.get("vuln_hypotheses", [])

        if not isinstance(suggested_tools, list):
            suggested_tools = []
        if not isinstance(exploit_chains, list):
            exploit_chains = []
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.0

        decision = AIDecision(
            phase=phase,
            summary=summary,
            suggested_tools=[str(t) for t in suggested_tools],
            exploit_chains=[str(c) for c in exploit_chains],
            confidence=confidence,
        )
        # Attach extra intelligence as dynamic attributes
        if attack_surface:
            object.__setattr__(decision, "attack_surface", attack_surface) if hasattr(decision, "__slots__") else setattr(decision, "attack_surface", attack_surface)
        if priority_targets:
            try:
                decision.priority_targets = priority_targets  # type: ignore[attr-defined]
            except Exception:
                pass
        if vuln_hypotheses:
            try:
                decision.vuln_hypotheses = vuln_hypotheses  # type: ignore[attr-defined]
            except Exception:
                pass
        return decision

    def _parse_suggestions(self, raw_text: str) -> list[str]:
        text = raw_text.strip()
        brace_start = text.find("{")
        if brace_start == -1:
            return []
        try:
            data = json.loads(text[brace_start:])
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(data, dict):
            return []
        suggestions = data.get("suggestions", [])
        if not isinstance(suggestions, list):
            return []
        return [str(s) for s in suggestions if s]

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    def _default_ai_decision(self, phase: str) -> AIDecision:
        """Return a safe default AIDecision when AI is unavailable."""
        kb = self._knowledge_base
        # Pick relevant tools from KB vuln patterns
        tools: list[str] = []
        for pattern in kb.vuln_patterns.values():
            tools.extend(pattern.get("tools", []))
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_tools: list[str] = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                unique_tools.append(t)

        return AIDecision(
            phase=phase,
            summary=f"Static KB analysis for phase: {phase}. AI API unavailable.",
            suggested_tools=unique_tools[:4],
            exploit_chains=[],
            confidence=0.3,
        )

    def _kb_exploit_suggestions(self, vulns: list[Vulnerability]) -> list[str]:
        """Derive exploit suggestions from KB vuln patterns."""
        suggestions: list[str] = []
        kb = self._knowledge_base
        for vuln in vulns:
            name_lower = vuln.name.lower()
            for pattern_key, pattern_data in kb.vuln_patterns.items():
                if pattern_key in name_lower or any(
                    ind.lower() in name_lower for ind in pattern_data.get("indicators", [])
                ):
                    tools = pattern_data.get("tools", [])
                    if tools:
                        suggestions.append(
                            f"Use {tools[0]} to exploit {vuln.name} at {vuln.url} "
                            f"(severity: {vuln.severity})"
                        )
                    break
            else:
                suggestions.append(
                    f"Manually investigate {vuln.name} at {vuln.url} "
                    f"(severity: {vuln.severity})"
                )
        return suggestions

    def _static_report_summary(self, full_state: dict) -> str:
        """Generate a minimal static report summary from scan state."""
        target = full_state.get("target", "unknown")
        phases_done = len(full_state.get("phase_results", {}))
        vulns = full_state.get("vulnerabilities", [])
        vuln_count = len(vulns) if isinstance(vulns, list) else 0
        return (
            f"Penetration test completed for target: {target}. "
            f"{phases_done} phases executed. "
            f"{vuln_count} vulnerabilities discovered. "
            "Review individual phase results for detailed findings. "
            "AI summary unavailable — manual review recommended."
        )
