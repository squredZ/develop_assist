"""OpenAI-compatible LLM HTTP client."""

from __future__ import annotations

import json
from typing import Any

import httpx

from hilog_agent.config import LLMConfig


class LLMClient:
    """Talks to an OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        self._cfg = config
        self._base = config.base_url.rstrip("/")

    @property
    def chat_endpoint(self) -> str:
        return f"{self._base}/chat/completions"

    @property
    def timeout(self) -> int:
        return self._cfg.timeout_seconds

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Send a chat completion request. Returns the model's text response."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = self._cfg.api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"

        body: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._cfg.max_output_tokens,
            "temperature": 0.0,
        }

        if json_schema and self._cfg.structured_output == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                },
            }

        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.post(self.chat_endpoint, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
