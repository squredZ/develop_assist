"""OpenAI SDK-based LLM client with thinking mode and streaming support."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from hilog_agent.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Talks to an OpenAI-compatible chat completions endpoint via the OpenAI SDK.

    Defaults: thinking mode on (reasoning_effort=medium), streaming output.
    """

    def __init__(self, config: LLMConfig) -> None:
        self._cfg = config
        api_key = config.api_key
        key_str = api_key.get_secret_value() if api_key else "no-key"
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=key_str,
            timeout=float(config.timeout_seconds),
        )
        logger.info(
            "LLM client initialized: model=%s base_url=%s timeout=%ds",
            config.model,
            config.base_url,
            config.timeout_seconds,
        )

    @property
    def chat_endpoint(self) -> str:
        return f"{self._cfg.base_url.rstrip('/')}/chat/completions"

    @property
    def timeout(self) -> int:
        return self._cfg.timeout_seconds

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        stream: bool = True,
    ) -> str:
        """Send a chat completion request. Returns the full text response.

        When stream=True (default), collects all chunks into a single string.
        Thinking/reasoning mode is enabled by default via reasoning_effort.
        """
        kwargs: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._cfg.max_output_tokens,
            "temperature": 0.0,
            "stream": stream,
        }

        effort = self._cfg.reasoning.effort
        if effort:
            kwargs["reasoning_effort"] = effort

        if json_schema and self._cfg.structured_output == "json_schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                },
            }
            kwargs["stream"] = False
            logger.debug("structured output mode — streaming disabled")

        logger.debug(
            "LLM chat: model=%s stream=%s max_tokens=%d",
            self._cfg.model,
            kwargs["stream"],
            kwargs["max_tokens"],
        )

        try:
            if stream:
                chunks: list[str] = []
                response = self._client.chat.completions.create(**kwargs)
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        chunks.append(chunk.choices[0].delta.content)
                result = "".join(chunks)
                logger.info("LLM chat complete — %d chars from %d chunks", len(result), len(chunks))
                return result
            else:
                response = self._client.chat.completions.create(**kwargs)
                result = response.choices[0].message.content or ""
                logger.info("LLM chat complete — %d chars", len(result))
                return result
        except Exception:
            logger.exception("LLM API call failed")
            raise

    def chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        """Streaming chat — yields content deltas as they arrive."""
        kwargs: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._cfg.max_output_tokens,
            "temperature": 0.0,
            "stream": True,
        }

        effort = self._cfg.reasoning.effort
        if effort:
            kwargs["reasoning_effort"] = effort

        logger.debug("LLM chat_stream: model=%s", self._cfg.model)
        chunk_count = 0
        try:
            response = self._client.chat.completions.create(**kwargs)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_count += 1
                    yield chunk.choices[0].delta.content
            logger.info("LLM stream complete — %d chunks", chunk_count)
        except Exception:
            logger.exception("LLM streaming call failed")
            raise
