"""Configuration loading with YAML file + CLI override + defaults precedence."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

logger = logging.getLogger(__name__)


class AnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    default_window_before_seconds: int = 60
    default_window_after_seconds: int = 60
    min_feature_score: int = 5
    feature_score_margin: int = 3
    max_log_events_for_llm: int = 200
    max_code_snippets_for_llm: int = 20


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    keyword_hit_weight: int = 3
    log_pattern_hit_weight: int = 5
    log_tag_hit_weight: int = 2
    continuous_step_bonus_per_step: int = 2
    missing_required_step_penalty: int = 5


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: str = "text"
    verbose: bool = False
    include_evidence: bool = True
    include_raw_log_lines: bool = False
    include_generated_yaml: bool = False


class AddModuleConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    backup: bool = False


class LLMReasoningConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    effort: str = "medium"
    summary: str = "auto"


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    provider: str = "openai_compatible"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: SecretStr | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"
    timeout_seconds: int = 120
    max_output_tokens: int = 4000
    structured_output: str = "json_schema"
    max_validation_retries: int = 3
    reasoning: LLMReasoningConfig = Field(default_factory=LLMReasoningConfig)

    @model_validator(mode="after")
    def resolve_api_key(self) -> LLMConfig:
        env_val = os.environ.get(self.api_key_env)
        if env_val:
            self.api_key = SecretStr(env_val)
        if self.api_key is None and not env_val:
            pass
        return self


class OrchestratorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: str = "bounded_react"
    max_tool_calls: int = 8
    max_llm_rounds: int = 4
    tool_timeout_seconds: int = 30
    allowed_tools: dict[str, list[str]] = Field(default_factory=dict)


class PromptsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_generation: str = "prompts/module_generation.md"
    feature_update: str = "prompts/feature_update.md"


class Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    repo_root: str = "/"
    features_dir: str = "./features"
    log_temp_dir: str = "./.tmp/hilog-agent"
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    add_module: AddModuleConfig = Field(default_factory=AddModuleConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on leaf keys."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(
    config_path: str | Path = "agent.yaml",
    cli_overrides: dict[str, Any] | None = None,
) -> Config:
    """Load config from YAML file, apply CLI overrides, fall back to defaults."""
    data: dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        logger.info("loading config from %s", path)
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        logger.info("config file not found at %s — using defaults", path)
    if cli_overrides:
        logger.debug("applying CLI overrides: %s", list(cli_overrides.keys()))
        data = deep_merge(data, cli_overrides)
    return Config.model_validate(data)
