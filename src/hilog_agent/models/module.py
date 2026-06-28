"""Module YAML schema models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class LogSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    symbol: str | None = None


class ModuleMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_by: str = Field(min_length=1)
    generated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    review_notes: list[str] = Field(default_factory=list)


class ModuleSymbol(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    kind: str = "method"
    relevance: Literal["high", "medium", "low"] = "medium"
    reason: str = ""


class ModuleLog(BaseModel):
    model_config = ConfigDict(extra="allow")

    tag: str = Field(min_length=1)
    level: str = Field(min_length=1)
    pattern: str
    match_type: Literal["substring", "regex"]
    meaning: str
    evidence_type: str = Field(min_length=1)
    related_step: str | None = None
    severity: Literal["high", "medium", "low"] = "low"
    confidence_weight: int = Field(default=1, ge=1)
    source: LogSource | None = None

    @model_validator(mode="after")
    def regex_must_compile(self) -> ModuleLog:
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}") from e
        return self


class CandidateStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    description: str
    file: str = Field(min_length=1)
    symbol: str
    async_: bool = Field(default=False, alias="async")
    optional: bool = False
    confidence: Literal["high", "medium", "low"] = "medium"
    reason: str = ""
    expected_logs: list[ModuleLog] = Field(default_factory=list)


class FailureSignal(BaseModel):
    model_config = ConfigDict(extra="allow")

    tag: str = Field(min_length=1)
    level: str = Field(min_length=1)
    pattern: str
    match_type: Literal["substring", "regex"]
    severity: Literal["high", "medium", "low"]
    suggested_cause: str = ""
    meaning: str = ""
    related_step: str | None = None
    confidence_weight: int = Field(default=1, ge=1)
    source: LogSource | None = None

    @model_validator(mode="after")
    def regex_must_compile(self) -> FailureSignal:
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}") from e
        return self


class ModuleEntrypoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    symbol: str
    file: str = Field(min_length=1)
    description: str = ""
    trigger: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class ModuleDependency(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    type: str = "module"
    direction: Literal["input", "output", "bidirectional"] = "input"
    reason: str = ""
    source: LogSource | None = None


class ModuleYaml(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    code_path: str = Field(min_length=1)
    responsibility: str
    symbols: list[ModuleSymbol]
    entrypoints: list[ModuleEntrypoint] = Field(default_factory=list)
    logs: list[ModuleLog]
    candidate_steps: list[CandidateStep]
    failure_signals: list[FailureSignal]
    dependencies: list[ModuleDependency] = Field(default_factory=list)
    metadata: ModuleMetadata

    @model_validator(mode="after")
    def candidate_step_ids_unique(self) -> ModuleYaml:
        seen: set[str] = set()
        for cs in self.candidate_steps:
            if cs.id in seen:
                raise ValueError(f"Duplicate candidate step id '{cs.id}' in module")
            seen.add(cs.id)
        return self

    @model_validator(mode="after")
    def log_related_steps_exist(self) -> ModuleYaml:
        step_ids = {cs.id for cs in self.candidate_steps}
        for log in self.logs:
            if log.related_step and log.related_step not in step_ids:
                raise ValueError(
                    f"Log '{log.pattern}' references unknown candidate step "
                    f"'{log.related_step}'. Known: {sorted(step_ids)}"
                )
        return self

    @model_validator(mode="after")
    def failure_signal_related_steps_exist(self) -> ModuleYaml:
        step_ids = {cs.id for cs in self.candidate_steps}
        for fs in self.failure_signals:
            if fs.related_step and fs.related_step not in step_ids:
                raise ValueError(
                    f"Failure signal '{fs.pattern}' references unknown candidate step "
                    f"'{fs.related_step}'. Known: {sorted(step_ids)}"
                )
        return self

    @model_validator(mode="after")
    def empty_lists_without_review_notes_warn(self) -> ModuleYaml:
        # Warnings are surfaced via the `warnings` property below.
        return self

    @property
    def warnings(self) -> list[str]:
        w: list[str] = []
        has_notes = bool(self.metadata.review_notes)
        if not self.symbols and not has_notes:
            w.append("symbols is empty without review_notes")
        if not self.logs and not has_notes:
            w.append("logs is empty without review_notes")
        if not self.candidate_steps and not has_notes:
            w.append("candidate_steps is empty without review_notes")
        if not self.failure_signals and not has_notes:
            w.append("failure_signals is empty without review_notes")
        return w
