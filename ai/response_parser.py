from __future__ import annotations

import copy
import json
from json import JSONDecodeError
from typing import Any, Optional


class ResponseParser:
    """
    Parses AI response text and enforces a strict JSON schema.

    Falls back to a safe default dict when parsing fails so callers
    never receive None or raise an exception.
    """

    # Immutable sentinel — never mutate this directly; always deepcopy.
    _DEFAULT: dict[str, Any] = {
        "phase": "fallback",
        "tools": [],
        "actions": [],
        "manual_steps": [],
        "confidence": 0.0,
    }

    def extract_json(self, response_text: str) -> dict[str, Any]:
        if not response_text or not response_text.strip():
            return copy.deepcopy(self._DEFAULT)

        text = response_text.strip()

        # Common case: fenced JSON.
        fenced_start = text.find("```")
        if fenced_start != -1:
            # Extract between the first ``` and the next ```
            # (works whether it's ```json or ```).
            first_tick = text.find("```", 0)
            second_tick = text.find("```", first_tick + 3)
            if second_tick != -1 and second_tick > first_tick + 3:
                inner = text[first_tick + 3 : second_tick].lstrip("\n")
                # If the fence includes language, drop first line if it doesn't start with `{`.
                if inner and not inner.lstrip().startswith("{"):
                    inner = "\n".join(inner.splitlines()[1:])
                parsed = self._try_parse_json(inner)
                if parsed is not None:
                    return parsed

        # Fallback: find any JSON object and attempt to parse from it.
        parsed = self._try_parse_json_from_object(text)
        if parsed is not None:
            return parsed

        return copy.deepcopy(self._DEFAULT)

    def validate_schema(self, data: dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        phase = data.get("phase")
        tools = data.get("tools")
        actions = data.get("actions")
        manual_steps = data.get("manual_steps")

        if not isinstance(phase, str):
            return False
        if not isinstance(tools, list) or not isinstance(actions, list) or not isinstance(manual_steps, list):
            return False
        if not all(isinstance(x, str) for x in tools):
            return False
        if not all(isinstance(x, str) for x in actions):
            return False
        if not all(isinstance(x, str) for x in manual_steps):
            return False
        return True

    def _try_parse_json(self, candidate: str) -> Optional[dict[str, Any]]:
        try:
            obj = json.loads(candidate)
        except JSONDecodeError:
            return None

        if isinstance(obj, dict) and self.validate_schema(obj):
            return obj
        return None

    def _try_parse_json_from_object(self, text: str) -> Optional[dict[str, Any]]:
        decoder = json.JSONDecoder()
        start = text.find("{")
        while start != -1:
            try:
                obj, _end = decoder.raw_decode(text[start:])
            except JSONDecodeError:
                start = text.find("{", start + 1)
                continue

            if isinstance(obj, dict) and self.validate_schema(obj):
                return obj

            start = text.find("{", start + 1)

        return None

