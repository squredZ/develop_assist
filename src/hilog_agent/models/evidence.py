"""Evidence model, chain step status, analysis stats."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRawRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: str = ""
    line: Optional[int] = None
    timestamp: Optional[str] = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    source: Literal["hilog", "feature_yaml", "module_yaml", "code", "user_input"]
    type: Literal[
        "expected_log_hit",
        "failure_log_hit",
        "missing_required_log",
        "code_reference",
        "feature_match",
        "chain_match",
    ]
    feature: str = ""
    chain: Optional[str] = None
    step: Optional[str] = None
    severity: Literal["high", "medium", "low"] = "low"
    confidence_delta: int = 0
    summary: str
    raw_ref: Optional[EvidenceRawRef] = None


class ChainStepStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    chain: str
    step_id: str
    status: Literal[
        "normal", "abnormal", "suspected_abnormal",
        "not_entered", "not_observed", "unknown",
    ]
    evidence: list[str] = Field(default_factory=list)
    detail: str = ""


class AnalysisStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_lines: int = 0
    parsed_lines: int = 0
    unparsed_lines: int = 0
    in_window_lines: int = 0
    time_span_seconds: float = 0.0
    tags_distribution: dict[str, int] = Field(default_factory=dict)
