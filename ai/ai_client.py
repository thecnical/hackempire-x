"""
AIClient — OpenRouter HTTP client for HackEmpire X (fallback provider).

Primary provider: Bytez AI (bytez_client.py)
Fallback provider: OpenRouter (this file)

API: https://openrouter.ai/docs
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class AIClient:
    """
    OpenRouter-compatible client — fallback AI provider for HackEmpire X.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = OPENROUTER_BASE_URL,
        model: str = OPENROUTER_DEFAULT_MODEL,
        timeout_s: float = 25.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s

    def send_request(self, prompt: str) -> dict[str, Any]:
        """
        Send a chat completion request to OpenRouter.
        Returns {"raw_text": str, "status_code": int}.
        Never raises.
        """
        if not prompt.strip():
            return {"raw_text": "", "status_code": 0}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://github.com/thecnical/hackempire-x",
            "X-Title": "HackEmpire X",
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
                    json=payload,
                    timeout=self._timeout_s,
                )
                raw_text = ""
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            raw_text = choices[0].get("message", {}).get("content", "")
                        if not raw_text:
                            raw_text = resp.text
                    except Exception:
                        raw_text = resp.text
                else:
                    raw_text = resp.text
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
