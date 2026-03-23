from __future__ import annotations

import json


class PromptBuilder:
    """
    Builds strict prompts for AI phases.
    """

    def _get_previous_ai_decisions(self, context: dict) -> str:
        """
        Build the "previous decisions" section for the prompt.

        This is best-effort:
        - prefer context["ai_history"] if provided
        - otherwise derive from context["data"][phase]["ai_decision"]
        """
        ai_history = context.get("ai_history")
        if isinstance(ai_history, list) and ai_history:
            last_two = ai_history[-2:]
            return json.dumps(last_two, ensure_ascii=False, indent=2)

        data = context.get("data", {})
        if not isinstance(data, dict):
            return "None"

        decisions: list[object] = []
        for phase_key in ("recon", "enum", "vuln"):
            phase_blob = data.get(phase_key, {})
            if isinstance(phase_blob, dict) and "ai_decision" in phase_blob:
                decisions.append(phase_blob["ai_decision"])

        if not decisions:
            return "None"

        return json.dumps(decisions[-2:], ensure_ascii=False, indent=2)

    def build_prompt(self, context: dict, phase: str) -> str:
        target = str(context.get("target", ""))
        mode = str(context.get("mode", ""))
        current_phase = str(context.get("current_phase", phase))
        full_data = context.get("data", {})
        full_data_json = json.dumps(full_data, ensure_ascii=False, indent=2)
        previous_decisions = self._get_previous_ai_decisions(context)

        # Enriched fields from ContextManager.
        tool_health = context.get("tool_health", {})
        tool_health_json = json.dumps(tool_health, ensure_ascii=False, indent=2)
        summary = context.get("summary", {})
        summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

        focus_area: str
        phase_lower = phase.lower()
        if phase_lower == "recon":
            focus_area = (
                "FOCUS (RECON): prioritize low-impact discovery and fingerprinting guidance "
                "(DNS/Whois, service identification, and reachability checks). "
                "Do not include exploitation payloads."
            )
        elif phase_lower == "enum":
            focus_area = (
                "FOCUS (ENUM): prioritize discovery of exposed surfaces "
                "(endpoints, directories/paths, and content/type triage). "
                "Prefer rate-limited/low-volume testing and avoid destructive requests."
            )
        else:
            focus_area = (
                "FOCUS (VULN): prioritize vulnerability triage and safe validation "
                "(evidence checklist, severity reasoning, and non-destructive verification). "
                "Do not provide exploit steps."
            )

        # Strict JSON output schema the model must follow.
        output_schema = (
            "{\n"
            '  "phase": "",\n'
            '  "tools": [],\n'
            '  "actions": [],\n'
            '  "manual_steps": [],\n'
            '  "confidence": 0.0\n'
            "}"
        )

        return (
            "ROLE:\n"
            "You are an elite ethical cybersecurity strategist and pentesting assistant.\n\n"
            "CONTEXT:\n"
            f"Target: {target}\n"
            f"Mode: {mode}\n"
            f"Current Phase: {current_phase}\n\n"
            "SYSTEM STATE:\n"
            f"Previous Findings:\n{full_data_json}\n\n"
            "TOOL HEALTH:\n"
            f"{tool_health_json}\n\n"
            "FINDINGS SUMMARY:\n"
            f"{summary_json}\n\n"
            "PREVIOUS AI DECISIONS:\n"
            f"{previous_decisions}\n\n"
            "TASK:\n"
            "Analyze the target and findings.\n"
            "Your job:\n"
            "- Decide next best actions\n"
            "- Suggest tools (safe usage only)\n"
            "- Provide clear step-by-step manual guidance\n"
            "- Consider tool_health when assessing data reliability\n"
            "- Prioritize high-confidence, multi-source vulnerabilities\n\n"
            f"{focus_area}\n\n"
            "OUTPUT FORMAT (STRICT JSON ONLY):\n"
            f"{output_schema}\n\n"
            "RULES (STRICT):\n"
            "- Output ONLY valid JSON\n"
            "- No explanation\n"
            "- No markdown\n"
            "- No extra text\n"
            "- confidence must be between 0 and 1\n"
            "- tools/actions must be realistic and relevant\n"
        )

