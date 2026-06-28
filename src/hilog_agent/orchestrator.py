"""Bounded ReAct orchestrator with SSE streaming output.

Yields structured SSE events so the frontend can render
thinking blocks, tool calls, tool results, and final answers
as distinct visual components.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from hilog_agent.config import Config
from hilog_agent.hilog.matcher import filter_by_time_window, match_logs
from hilog_agent.hilog.parser import parse_hilog_file
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
        self._repo_root = Path(config.repo_root).resolve()

    def _resolve_path(self, path: str) -> Path | None:
        """Resolve a user-provided path relative to repo_root, ensuring it stays within bounds."""
        try:
            p = (self._repo_root / path).resolve()
            # Must be within repo_root
            if self._repo_root in p.parents or p == self._repo_root:
                return p
        except (ValueError, OSError):
            pass
        return None

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
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a text file from the project. Returns content up to 100KB.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path from project root, e.g. src/hilog_agent/server.py",
                            }
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search source code for a pattern (case-insensitive regex). Returns matching file:line snippets, max 50 results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Regular expression to search for",
                            },
                            "file_pattern": {
                                "type": "string",
                                "description": "Optional glob pattern to filter files, e.g. *.py or *.yaml",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_hilog_by_time",
                    "description": "Parse a hilog file and return events within a time window. Returns event count and up to 20 sample events.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "log_path": {
                                "type": "string",
                                "description": "Path to the hilog file",
                            },
                            "time": {
                                "type": "string",
                                "description": "Center time, format: YYYY-MM-DD HH:MM",
                            },
                            "window_before": {
                                "type": "integer",
                                "description": "Seconds before center time (default 60)",
                            },
                            "window_after": {
                                "type": "integer",
                                "description": "Seconds after center time (default 60)",
                            },
                        },
                        "required": ["log_path", "time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "match_logs_by_patterns",
                    "description": "Search parsed log events by tag and text pattern. Returns matching events with their raw text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "log_path": {
                                "type": "string",
                                "description": "Path to the hilog file",
                            },
                            "time": {
                                "type": "string",
                                "description": "Center time, format: YYYY-MM-DD HH:MM",
                            },
                            "window_before": {
                                "type": "integer",
                                "description": "Seconds before center time (default 60)",
                            },
                            "window_after": {
                                "type": "integer",
                                "description": "Seconds after center time (default 60)",
                            },
                            "tag": {
                                "type": "string",
                                "description": "Log tag to match (exact), e.g. CAM, CameraService",
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Text or regex pattern to search in log messages",
                            },
                            "match_type": {
                                "type": "string",
                                "enum": ["substring", "regex"],
                                "description": "substring for plain text match, regex for pattern match",
                            },
                            "level": {
                                "type": "string",
                                "enum": ["D", "I", "W", "E", "F"],
                                "description": "Optional log level filter: D(ebug), I(nfo), W(arn), E(rror), F(atal)",
                            },
                        },
                        "required": ["log_path", "time", "tag", "pattern", "match_type"],
                    },
                },
            },
        ]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name, return JSON string result."""
        logger.info("tool call: %s(%s)", tool_name, arguments)

        # --- list_features ---
        if tool_name == "list_features":
            names = self._store.list_features()
            return json.dumps({"features": names}, ensure_ascii=False)

        # --- read_feature ---
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

        # --- read_file ---
        if tool_name == "read_file":
            path_str = arguments.get("path", "")
            resolved = self._resolve_path(path_str)
            if not resolved or not resolved.is_file():
                return json.dumps({"error": f"File not found or outside project: {path_str}"})
            try:
                text = resolved.read_text(encoding="utf-8")
                if len(text) > 100_000:
                    text = text[:100_000] + "\n\n... (truncated at 100KB)"
                return json.dumps({"path": path_str, "content": text}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": f"Failed to read file: {e}"})

        # --- search_code ---
        if tool_name == "search_code":
            pattern = arguments.get("pattern", "")
            file_pattern = arguments.get("file_pattern", "*")
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return json.dumps({"error": f"Invalid regex: {e}"})
            matches = []
            root = self._repo_root
            if not root.is_dir():
                return json.dumps({"error": f"Project root not found: {root}"})
            try:
                for dirpath, _dirnames, filenames in os.walk(root):
                    # Skip hidden dirs and common non-source dirs
                    rel = Path(dirpath).relative_to(root).as_posix()
                    if any(p.startswith(".") for p in rel.split("/") if p):
                        continue
                    if rel in (".venv", "__pycache__", ".git", "node_modules", ".tmp"):
                        continue
                    for fn in filenames:
                        if not Path(fn).suffix:  # skip extensionless files
                            continue
                        if file_pattern != "*" and not Path(fn).match(file_pattern):
                            continue
                        fp = Path(dirpath) / fn
                        try:
                            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                                for i, line in enumerate(f, 1):
                                    if compiled.search(line):
                                        rel_path = fp.relative_to(root).as_posix()
                                        matches.append(f"{rel_path}:{i}: {line.rstrip()[:200]}")
                                        if len(matches) >= 50:
                                            break
                            if len(matches) >= 50:
                                break
                        except (OSError, UnicodeDecodeError):
                            continue
                    if len(matches) >= 50:
                        break
            except Exception as e:
                return json.dumps({"error": f"Search failed: {e}"})
            if not matches:
                return json.dumps({"matches": [], "count": 0})
            return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)

        # --- filter_hilog_by_time ---
        if tool_name == "filter_hilog_by_time":
            log_path = arguments.get("log_path", "")
            time_str = arguments.get("time", "")
            window_before = arguments.get("window_before", 60)
            window_after = arguments.get("window_after", 60)
            try:
                center = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                return json.dumps({"error": "Invalid time format. Use YYYY-MM-DD HH:MM"})
            try:
                parsed = parse_hilog_file(log_path)
            except Exception as e:
                return json.dumps({"error": f"Failed to parse log file '{log_path}': {e}"})
            filtered = filter_by_time_window(parsed.events, center, window_before, window_after)
            samples = [
                {
                    "tag": e.tag,
                    "level": e.level,
                    "timestamp": e.timestamp.isoformat(),
                    "message": e.message[:300],
                    "raw": e.raw[:300],
                }
                for e in filtered[:20]
            ]
            return json.dumps({
                "total_events": len(parsed.events),
                "window_events": len(filtered),
                "time_range": {
                    "from": (center.timestamp() - window_before),
                    "to": (center.timestamp() + window_after),
                },
                "samples": samples,
            }, ensure_ascii=False)

        # --- match_logs_by_patterns ---
        if tool_name == "match_logs_by_patterns":
            log_path = arguments.get("log_path", "")
            time_str = arguments.get("time", "")
            window_before = arguments.get("window_before", 60)
            window_after = arguments.get("window_after", 60)
            tag = arguments.get("tag", "")
            pattern = arguments.get("pattern", "")
            match_type = arguments.get("match_type", "substring")
            level = arguments.get("level", None)
            if match_type not in ("substring", "regex"):
                return json.dumps({"error": "match_type must be 'substring' or 'regex'"})
            try:
                center = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                return json.dumps({"error": "Invalid time format. Use YYYY-MM-DD HH:MM"})
            try:
                parsed = parse_hilog_file(log_path)
            except Exception as e:
                return json.dumps({"error": f"Failed to parse log file '{log_path}': {e}"})
            filtered = filter_by_time_window(parsed.events, center, window_before, window_after)
            try:
                results = match_logs(filtered, tag=tag, pattern=pattern, match_type=match_type, level=level)
            except re.error as e:
                return json.dumps({"error": f"Invalid regex pattern: {e}"})
            matches = [
                {
                    "tag": r.event.tag,
                    "level": r.event.level,
                    "timestamp": r.event.timestamp.isoformat(),
                    "message": r.event.message[:300],
                    "match_text": r.match_text[:200],
                    "raw": r.event.raw[:400],
                }
                for r in results[:50]
            ]
            return json.dumps({
                "total_in_window": len(filtered),
                "matches_found": len(results),
                "tag": tag,
                "pattern": pattern,
                "match_type": match_type,
                "matches": matches,
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
- read_file(path): read a source file from the project
- search_code(pattern, file_pattern?): search source code with regex
- filter_hilog_by_time(log_path, time, window_before?, window_after?): parse and filter hilog events by time window
- match_logs_by_patterns(log_path, time, tag, pattern, match_type, window_before?, window_after?, level?): search parsed logs for matching patterns

When troubleshooting:
1. Use tools to gather feature knowledge
2. Analyze the evidence
3. Provide a clear answer with root causes and supporting evidence
4. Mark experience-based suggestions as supplemental

Reply in Chinese unless the user asks in English."""
