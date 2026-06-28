"""Feature YAML schema models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class FeatureMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["draft", "active"]
    owner: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    updated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    review_notes: list[str] = Field(default_factory=list)


class FeatureModuleIndex(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    yaml_path: str
    responsibility: str

    @model_validator(mode="after")
    def yaml_path_must_match(self) -> FeatureModuleIndex:
        expected = f"modules/{self.name}.yaml"
        if self.yaml_path != expected:
            raise ValueError(f"yaml_path must be '{expected}', got '{self.yaml_path}'")
        return self


class Entrypoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    module: str = Field(min_length=1)
    file: str = Field(min_length=1)
    symbol: str
    description: str = ""


class ExpectedLog(BaseModel):
    model_config = ConfigDict(extra="allow")

    tag: str = Field(min_length=1)
    level: str = Field(min_length=1)
    pattern: str
    match_type: Literal["substring", "regex"]
    evidence_type: str = Field(min_length=1)
    required: bool = True
    weight: int = Field(default=1, ge=1)
    missing_meaning: str = ""

    @model_validator(mode="after")
    def regex_must_compile(self) -> ExpectedLog:
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}") from e
        return self


class CallChainStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    module: str = Field(min_length=1)
    file: str = Field(min_length=1)
    symbol: str
    description: str
    optional: bool = False
    async_: bool = Field(default=False, alias="async")
    expected_logs: list[ExpectedLog] = Field(default_factory=list)

    @model_validator(mode="after")
    def optional_step_cannot_have_required_logs(self) -> CallChainStep:
        if self.optional:
            for elog in self.expected_logs:
                if elog.required:
                    raise ValueError(
                        f"Step '{self.id}' is optional but has required expected_log "
                        f"'{elog.pattern}'. Optional steps must not require logs."
                    )
        return self


class CallChain(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    description: str
    keywords: list[str] = Field(min_length=1)
    steps: list[CallChainStep] = Field(min_length=1)


class FailureKeyLog(BaseModel):
    model_config = ConfigDict(extra="allow")

    tag: str = Field(min_length=1)
    level: str = Field(min_length=1)
    pattern: str
    match_type: Literal["substring", "regex"]
    severity: Literal["high", "medium", "low"]
    confidence_weight: int = Field(ge=1)
    related_step: str | None = None
    suggested_cause: str = ""
    meaning: str = ""

    @model_validator(mode="after")
    def regex_must_compile(self) -> FailureKeyLog:
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}") from e
        return self


class FailurePattern(BaseModel):
    model_config = ConfigDict(extra="allow")

    symptom: str = Field(min_length=1)
    related_steps: list[str] = Field(default_factory=list)
    key_logs: list[FailureKeyLog] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)


class FeatureYaml(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str
    keywords: list[str] = Field(min_length=1)
    modules: list[FeatureModuleIndex] = Field(min_length=1)
    entrypoints: list[Entrypoint] = Field(default_factory=list)
    call_chains: list[CallChain]
    failure_patterns: list[FailurePattern]
    metadata: FeatureMetadata

    @model_validator(mode="after")
    def step_ids_unique(self) -> FeatureYaml:
        seen: set[str] = set()
        for chain in self.call_chains:
            for step in chain.steps:
                if step.id in seen:
                    raise ValueError(f"Duplicate call chain step id '{step.id}' across feature")
                seen.add(step.id)
        return self

    @model_validator(mode="after")
    def step_modules_exist(self) -> FeatureYaml:
        module_names = {m.name for m in self.modules}
        for chain in self.call_chains:
            for step in chain.steps:
                if step.module not in module_names:
                    raise ValueError(
                        f"Call chain step '{step.id}' references unknown module "
                        f"'{step.module}'. Known: {sorted(module_names)}"
                    )
        return self

    @model_validator(mode="after")
    def entrypoint_modules_exist(self) -> FeatureYaml:
        module_names = {m.name for m in self.modules}
        for ep in self.entrypoints:
            if ep.module not in module_names:
                raise ValueError(
                    f"Entrypoint '{ep.name}' references unknown module "
                    f"'{ep.module}'. Known: {sorted(module_names)}"
                )
        return self

    @model_validator(mode="after")
    def failure_related_steps_exist(self) -> FeatureYaml:
        step_ids = {s.id for ch in self.call_chains for s in ch.steps}
        for fp in self.failure_patterns:
            for rid in fp.related_steps:
                if rid not in step_ids:
                    raise ValueError(
                        f"Failure pattern '{fp.symptom}' references unknown step "
                        f"'{rid}'. Known: {sorted(step_ids)}"
                    )
            for kl in fp.key_logs:
                if kl.related_step and kl.related_step not in step_ids:
                    raise ValueError(
                        f"Failure key log '{kl.pattern}' references unknown step "
                        f"'{kl.related_step}'. Known: {sorted(step_ids)}"
                    )
        return self

    @model_validator(mode="after")
    def active_feature_requires_content(self) -> FeatureYaml:
        if self.metadata.status == "active":
            if not self.call_chains:
                raise ValueError("Active feature requires non-empty call_chains")
            if not self.failure_patterns:
                raise ValueError("Active feature requires non-empty failure_patterns")
        return self
