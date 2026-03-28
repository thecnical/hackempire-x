"""
BytezClient — Bytez AI (https://bytez.com) HTTP client for HackEmpire X.

Bytez is the primary AI provider. OpenRouter is the fallback.
API docs: https://bytez.com/docs/api
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

BYTEZ_BASE_URL = "https://api.bytez.com/models/v2"
BYTEZ_DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"


class BytezClient:
    """
    Bytez AI API client — primary AI provider for HackEmpire X.

    Usage:
        client = BytezClient(api_key="your-bytez-key")
        response = client.send_request("Your prompt here")
        # response = {"raw_text": "...", "status_code": 200}
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = BYTEZ_DEFAULT_MODEL,
        timeout_s: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s

    def send_request(self, prompt: str) -> dict[str, Any]:
        """
        Send a chat completion request to Bytez API.
        Returns {"raw_text": str, "status_code": int}.
        Never raises.
        """
        if not prompt.strip():
            return {"raw_text": "", "status_code": 0}

        headers = {
            "Authorization": f"{self._api_key}",
            "Content-Type": "application/json",
        }
        # Bytez API: POST /models/v2/{modelId} — NOT /chat/completions
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "params": {
                "max_length": 2048,
                "temperature": 0.3,
            },
        }

        last_error: Optional[BaseException] = None

        for attempt in range(1, 3):
            try:
                url = f"{BYTEZ_BASE_URL}/{self._model}"
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_s,
                )
                raw_text = ""
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        # Bytez response format
                        choices = data.get("choices", [])
                        if choices:
                            raw_text = choices[0].get("message", {}).get("content", "")
                        if not raw_text:
                            # Try output field
                            raw_text = data.get("output", "") or data.get("text", "") or resp.text
                    except Exception:
                        raw_text = resp.text
                else:
                    raw_text = resp.text
                return {"raw_text": raw_text, "status_code": resp.status_code}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
            except requests.exceptions.RequestException as exc:
                last_error = exc

            if attempt < 2:
                time.sleep(1.0)

        return {
            "raw_text": "",
            "status_code": 0,
            "error": str(last_error) if last_error else "unknown",
        }

    def is_available(self) -> bool:
        """Quick health check — returns True if Bytez API is reachable."""
        if not self._api_key:
            return False
        try:
            resp = requests.get(
                f"{BYTEZ_BASE_URL}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
