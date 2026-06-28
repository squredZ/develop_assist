"""Bounded ReAct orchestrator with SSE streaming output.

Yields structured SSE events so the frontend can render
thinking blocks, tool calls, tool results, and final answers
as distinct visual components.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from hilog_agent.config import Config
from hilog_agent.llm.client import LLMClient
from hilog_agent.store import FeatureStore


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
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_feature",
                    "description": "Read a feature's full feature.yaml knowledge",
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
        if tool_name == "list_features":
            names = self._store.list_features()
            return json.dumps({"features": names}, ensure_ascii=False)

        if tool_name == "read_feature":
            name = arguments.get("feature_name", "")
            try:
                f = self._store.read_feature(name)
                return json.dumps(f.model_dump(), ensure_ascii=False, indent=2)
            except ValueError as e:
                return json.dumps({"error": str(e)})

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

    system_prompt = _build_system_prompt(store)

    for _round_idx in range(max_rounds):
        if tool_call_count >= max_tool_calls:
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

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # Thinking / reasoning tokens (some models emit these)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    yield SSEEvent(
                        event="thinking",
                        data={"text": delta.reasoning_content},
                    )

                # Regular content
                if delta.content:
                    content_buf.append(delta.content)
                    yield SSEEvent(
                        event="message",
                        data={"role": "assistant", "content": delta.content},
                    )

                # Tool calls
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

            # After stream ends — process any tool calls
            if tool_calls_buf:
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

                # Loop back for next round with tool results
                continue

            # No tool calls — final answer
            final_text = "".join(content_buf)
            messages.append({"role": "assistant", "content": final_text})

            yield SSEEvent(
                event="final_answer",
                data={"content": final_text},
            )
            return

        except Exception as e:
            yield SSEEvent(
                event="error",
                data={"message": str(e)},
            )
            return

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
