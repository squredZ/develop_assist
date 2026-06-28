"""JSON renderer for CLI output."""

from __future__ import annotations

import json

from hilog_agent.models.result import (
    AskResult,
    AnalysisResult,
    AddModuleResult,
)


def render_json(
    result: AskResult | AnalysisResult | AddModuleResult,
    indent: int = 2,
) -> str:
    """Render a result model to JSON string."""
    return json.dumps(
        result.model_dump(mode="json"),
        indent=indent,
        ensure_ascii=False,
    )
