"""FastAPI server — wraps hilog-agent commands as REST + SSE endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from hilog_agent.commands.add_module import add_module
from hilog_agent.commands.analyze_log import analyze_log
from hilog_agent.commands.ask import ask
from hilog_agent.config import load_config
from hilog_agent.orchestrator import run_react_loop
from hilog_agent.renderers.json_renderer import render_json
from hilog_agent.store import FeatureStore

# ---------------------------------------------------------------
# Global state (single-user desktop app — no concurrency needed)
# ---------------------------------------------------------------

_config = load_config("agent.yaml")
_store = FeatureStore(_config)

# In-memory session store (MVP: survives until restart)
_sessions: dict[str, list[dict[str, Any]]] = {}


def _get_or_create_session(session_id: str) -> list[dict[str, Any]]:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


# ---------------------------------------------------------------
# App
# ---------------------------------------------------------------

app = FastAPI(
    title="Hilog Agent",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------
# Request models
# ---------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str = "default"
    question: str
    feature: str | None = None


class AnalyzeLogRequest(BaseModel):
    log_paths: list[str]
    time: str  # "YYYY-MM-DD HH:MM"
    window_before: int | None = None
    window_after: int | None = None
    feature: str | None = None
    top_n_chains: int = 1


class AddModuleRequest(BaseModel):
    feature: str
    module: str
    code_path: str
    force: bool = False
    backup: bool = False


# ---------------------------------------------------------------
# SSE chat (main endpoint)
# ---------------------------------------------------------------


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """Streaming chat — SSE endpoint yielding thinking/tool_call/tool_result/message/final_answer."""  # noqa: E501
    session = _get_or_create_session(req.session_id)
    session.append({"role": "user", "content": req.question})

    async def event_generator():
        try:
            # If feature specified, prepend feature context
            if req.feature:
                try:
                    f = _store.read_feature(req.feature)
                    ctx_msg = {
                        "role": "system",
                        "content": (
                            f"User specified feature: {req.feature}\n"
                            f"Feature knowledge:\n{render_json(f)}"
                        ),
                    }
                    # Inject before the user message for this call
                    msgs = list(session)
                    msgs.insert(-1, ctx_msg)
                except ValueError:
                    msgs = list(session)
            else:
                msgs = list(session)

            for evt in run_react_loop(
                messages=msgs,
                store=_store,
                config=_config,
                question=req.question,
            ):
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                yield {
                    "event": evt.event,
                    "data": json.dumps(evt.data, ensure_ascii=False),
                }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------


@app.get("/api/features")
async def list_features():
    """List all available feature names."""
    return {"features": _store.list_features()}


@app.get("/api/features/{name}")
async def get_feature(name: str):
    """Read a single feature's full YAML."""
    try:
        f = _store.read_feature(name)
        return f.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/analyze-log")
async def analyze_log_endpoint(req: AnalyzeLogRequest):
    """Run the analyze-log pipeline (non-streaming, returns full result)."""
    try:
        ct = datetime.strptime(req.time, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="time must be 'YYYY-MM-DD HH:MM'") from None

    wb = req.window_before or _config.analysis.default_window_before_seconds
    wa = req.window_after or _config.analysis.default_window_after_seconds

    result = analyze_log(
        log_paths=req.log_paths,
        time=ct,
        window_before=wb,
        window_after=wa,
        feature=req.feature,
        store=_store,
        config=_config,
        top_n_chains=req.top_n_chains,
    )
    return result.model_dump()


@app.post("/api/ask")
async def ask_endpoint(req: ChatRequest):
    """Deterministic ask (no LLM needed)."""
    result = ask(
        feature=req.feature,
        question=req.question,
        store=_store,
        config=_config,
        no_llm=True,
    )
    return result.model_dump()


@app.post("/api/add-module")
async def add_module_endpoint(req: AddModuleRequest):
    """Add or update a module."""
    try:
        result = add_module(
            feature=req.feature,
            module=req.module,
            code_path=req.code_path,
            store=_store,
            config=_config,
            force=req.force,
            backup=req.backup,
            dry_run=False,
            review=False,
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/sessions")
async def list_sessions():
    """List active conversation sessions."""
    return {
        "sessions": [{"id": sid, "message_count": len(msgs)} for sid, msgs in _sessions.items()]
    }


@app.post("/api/sessions/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear a conversation session."""
    _sessions.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


@app.get("/api/config")
async def get_config():
    """Return current effective config (API keys redacted)."""
    d = _config.model_dump()
    if d.get("llm", {}).get("api_key"):
        d["llm"]["api_key"] = "***"
    return d
