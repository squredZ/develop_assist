"""Bounded ReAct orchestrator with SSE streaming output.

Yields structured SSE events so the frontend can render
thinking blocks, tool calls, tool results, and final answers
as distinct visual components.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from hilog_agent.config import Config
from hilog_agent.llm.client import LLMClient
from hilog_agent.store import FeatureStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """A single SSE event sent to the frontend."""

    event: str  # "thinking" | "tool_call" | "tool_result" | "message" | "final_answer" | "error"
    data: dict[str, Any]


# ---------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------


class ToolRegistry:
    """Registry of callable tools the orchestrator can invoke."""

    def __init__(self, store: FeatureStore, config: Config) -> None:
        self._store = store
        self._config = config

    def list_tools(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions."""
        feature_hint = ""
        try:
            names = self._store.list_features()
            if names:
                feature_hint = f" Available: {', '.join(names)}."
        except Exception:
            pass
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_feature",
                    "description": "Read a feature's full feature.yaml knowledge" + feature_hint,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "feature_name": {
                                "type": "string",
                                "description": "Feature directory name",
                            }
                        },
                        "required": ["feature_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_features",
                    "description": "List all available feature names",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name, return JSON string result."""
        logger.info("tool call: %s(%s)", tool_name, arguments)
        if tool_name == "list_features":
            names = self._store.list_features()
            return json.dumps({"features": names}, ensure_ascii=False)

        if tool_name == "read_feature":
            name = arguments.get("feature_name", "")
            try:
                f = self._store.read_feature(name)
                result = json.dumps(f.model_dump(), ensure_ascii=False, indent=2)
                logger.debug("read_feature(%s) → %d chars", name, len(result))
                return result
            except ValueError as e:
                logger.warning("read_feature(%s) failed: %s", name, e)
                available = self._store.list_features()
                return json.dumps({
                    "error": f"Feature '{name}' not found. Available features: {', '.join(available) or '(none)'}",
                }, ensure_ascii=False)

        logger.warning("unknown tool requested: %s", tool_name)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ---------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------


def run_react_loop(
    *,
    messages: list[dict[str, Any]],
    store: FeatureStore,
    config: Config,
    question: str = "",
) -> Generator[SSEEvent, None, None]:
    """Run a bounded ReAct loop, yielding SSE events.

    The loop:
    1. Sends messages + system prompt to LLM
    2. Streams thinking tokens → "thinking" events
    3. If the LLM requests a tool call → yield "tool_call", execute, yield "tool_result"
    4. Appends tool result to messages, loops back
    5. When the LLM emits a final answer → yield "message" + "final_answer"

    Bounded by config.orchestrator.max_llm_rounds and max_tool_calls.
    """
    tools = ToolRegistry(store, config)
    client = LLMClient(config.llm)
    max_rounds = config.orchestrator.max_llm_rounds
    max_tool_calls = config.orchestrator.max_tool_calls
    tool_call_count = 0

    logger.info(
        "ReAct loop start — max_rounds=%d, max_tool_calls=%d, messages=%d",
        max_rounds,
        max_tool_calls,
        len(messages),
    )

    system_prompt = _build_system_prompt(store)

    for round_idx in range(max_rounds):
        logger.debug(
            "round %d/%d — tool_calls so far: %d", round_idx + 1, max_rounds, tool_call_count
        )

        if tool_call_count >= max_tool_calls:
            logger.warning("max tool calls reached (%d)", max_tool_calls)
            yield SSEEvent(
                event="error",
                data={"message": f"Reached max tool calls ({max_tool_calls})"},
            )
            return

        # Build full message list for this round
        full_messages = [{"role": "system", "content": system_prompt}, *messages]

        try:
            # Stream from LLM
            stream = client._client.chat.completions.create(
                model=config.llm.model,
                messages=full_messages,
                max_tokens=config.llm.max_output_tokens,
                temperature=0.0,
                stream=True,
                tools=tools.list_tools() if tool_call_count < max_tool_calls else None,
                tool_choice="auto" if tool_call_count < max_tool_calls else None,
            )

            content_buf: list[str] = []
            tool_calls_buf: dict[int, dict[str, Any]] = {}
            thinking_buf: list[str] = []
            _MIN_THINKING_BATCH = 30

            def _flush_thinking() -> Generator[SSEEvent, None, None]:
                """Yield buffered thinking tokens as a single event."""
                nonlocal thinking_buf
                if thinking_buf:
                    text = "".join(thinking_buf)
                    thinking_buf = []
                    if text.strip():
                        yield SSEEvent(event="thinking", data={"text": text})

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # Thinking / reasoning tokens (some models emit these)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    thinking_buf.append(delta.reasoning_content)
                    if len("".join(thinking_buf)) >= _MIN_THINKING_BATCH:
                        yield from _flush_thinking()

                # Regular content — flush any pending thinking first
                if delta.content:
                    yield from _flush_thinking()
                    content_buf.append(delta.content)
                    yield SSEEvent(
                        event="message",
                        data={"role": "assistant", "content": delta.content},
                    )

                # Tool calls — flush any pending thinking first
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_buf[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buf[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_buf[idx]["function"]["arguments"] += (
                                    tc.function.arguments
                                )

            # After stream ends — flush remaining thinking, then process tool calls
            yield from _flush_thinking()
            if tool_calls_buf:
                logger.info(
                    "round %d: LLM requested %d tool call(s)", round_idx + 1, len(tool_calls_buf)
                )
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(content_buf) or None,
                }

                tc_list: list[dict[str, Any]] = []
                for idx in sorted(tool_calls_buf.keys()):
                    tc_info = tool_calls_buf[idx]
                    tc_list.append(
                        {
                            "id": tc_info["id"],
                            "type": "function",
                            "function": tc_info["function"],
                        }
                    )

                assistant_msg["tool_calls"] = tc_list
                messages.append(assistant_msg)

                for tc in tc_list:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        logger.warning(
                            "failed to parse tool call arguments: %s", tc["function"]["arguments"]
                        )
                        args = {}

                    yield SSEEvent(
                        event="tool_call",
                        data={"tool": tool_name, "args": args},
                    )

                    tool_call_count += 1
                    result = tools.call(tool_name, args)
                    yield SSEEvent(
                        event="tool_result",
                        data={"tool": tool_name, "result": result},
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        }
                    )

                continue

            # No tool calls — final answer
            final_text = "".join(content_buf)
            messages.append({"role": "assistant", "content": final_text})

            logger.info("ReAct loop done — final answer %d chars", len(final_text))
            yield SSEEvent(
                event="final_answer",
                data={"content": final_text},
            )
            return

        except Exception as e:
            logger.exception("ReAct loop error in round %d", round_idx + 1)
            yield SSEEvent(
                event="error",
                data={"message": str(e)},
            )
            return

    logger.warning("ReAct loop exhausted — max_rounds=%d", max_rounds)
    yield SSEEvent(
        event="error",
        data={"message": f"Reached max LLM rounds ({max_rounds})"},
    )


def _build_system_prompt(store: FeatureStore) -> str:
    """Build the system prompt with available feature context."""
    features = store.list_features()
    feature_list = "\n".join(f"  - {f}" for f in features) if features else "  (none)"
    return f"""You are a system troubleshooting assistant (Hilog Agent).

Available features:
{feature_list}

You have access to tools:
- list_features: list all feature names
- read_feature(feature_name): read a feature's full knowledge YAML

When troubleshooting:
1. Use tools to gather feature knowledge
2. Analyze the evidence
3. Provide a clear answer with root causes and supporting evidence
4. Mark experience-based suggestions as supplemental

Reply in Chinese unless the user asks in English."""
