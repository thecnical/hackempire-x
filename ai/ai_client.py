"""
AIClient — OpenRouter-compatible HTTP client for HackEmpire X.

Uses requests with exponential-backoff retry (3 attempts).
Sends JSON via the `json=` kwarg so requests sets Content-Type automatically.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests


class AIClient:
    """
    OpenRouter-compatible client for HackEmpire X (future Phase 2+).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "meta-llama/llama-3-8b-instruct",
        timeout_s: float = 25.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s

    def send_request(self, prompt: str) -> dict[str, Any]:
        """
        Send a chat completion request and return a dict with ``raw_text``.

        Retries up to 3 times with exponential back-off on transient errors.
        Never raises — errors are captured in the returned dict.
        """
        if not prompt.strip():
            return {"raw_text": "", "status_code": 0}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }

        last_error: Optional[BaseException] = None
        backoff_s = 1.0

        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    self._base_url,
                    headers=headers,
                    json=payload,          # sets Content-Type: application/json automatically
                    timeout=self._timeout_s,
                )
                raw_text = resp.text or ""
                return {"raw_text": raw_text, "status_code": resp.status_code}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
            except requests.exceptions.RequestException as exc:
                last_error = exc

            if attempt < 3:
                time.sleep(backoff_s)
                backoff_s *= 2

        return {
            "raw_text": "",
            "status_code": 0,
            "error": str(last_error) if last_error else "unknown",
        }

