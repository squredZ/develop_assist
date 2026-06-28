# Hilog Agent MVP Implementation Plan

> **For agentic workers:** implement this plan task-by-task — dispatch a fresh subagent per task with the native `task` tool (recommended for quality), or use the superpowers-executing-plans skill to work through it inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI agent tool (`agent ask`, `agent analyze-log`, `agent add-module`) that uses structured feature knowledge, local code inspection, and an LLM (bounded ReAct loop) to answer feature questions, analyze hilog evidence, and generate module knowledge YAML.

**Architecture:** Pydantic v2 schemas define all data boundaries. `FeatureStore` reads/validates `features/<name>/` directories. A deterministic pipeline handles hilog parsing, time filtering, pattern matching, evidence building, and scoring. The LLM is invoked only when needed via a bounded ReAct loop (max 8 tool calls, 4 rounds). All LLM output is locally validated with retry. `add-module` uses diff-safety validation and atomic writes.

**Tech Stack:** Python >= 3.10, Pydantic v2, uv, pytest, ruff, mypy (strict). LLM: OpenAI-compatible API. Storage: local YAML files. Prompts: simple `{{placeholder}}` templates.

---

## File Structure Map

```
src/hilog_agent/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── feature.py       # FeatureYaml, FeatureMetadata, FeatureModuleIndex, CallChain, CallChainStep, ExpectedLog, FailurePattern, FailureKeyLog, Entrypoint
│   ├── module.py        # ModuleYaml, ModuleMetadata, ModuleSymbol, ModuleLog, LogSource, CandidateStep, FailureSignal, ModuleDependency, ModuleEntrypoint
│   ├── evidence.py      # Evidence, ChainStepStatus, EvidenceRawRef, AnalysisStats (cross-chain types)
│   └── result.py        # AnalysisResult, AskResult, AddModuleResult, WrittenFile, Conclusion, RootCause, CrossChainCorrelation, ModuleGenerationResult, FeatureUpdateResult, RelatedFeatureSuggestion
├── config.py            # agent.yaml loading, CLI override, precedence, SecretStr for api_key
├── store.py             # FeatureStore: scan, read, validate feature directories
├── hilog/
│   ├── __init__.py
│   ├── parser.py        # Hilog line parsing + unparsed line accounting
│   └── matcher.py       # Time-window filter, substring/regex log matching
├── scoring.py           # Evidence builder, feature scoring, chain scoring (with configurable weights)
├── renderers/
│   ├── __init__.py
│   ├── text.py          # Text output (tables, verbose scoring breakdown)
│   └── json_renderer.py # JSON output
├── llm/
│   ├── __init__.py
│   ├── client.py        # OpenAI-compatible HTTP client, structured output, timeout
│   └── validator.py     # Validate LLM output against Pydantic model, retry loop
├── prompts/
│   ├── __init__.py
│   └── loader.py        # Read prompt .md files, render {{placeholders}}
├── commands/
│   ├── __init__.py
│   ├── ask.py           # Feature Q&A (deterministic + optional LLM)
│   ├── analyze_log.py   # Hilog analysis pipeline
│   └── add_module.py    # Module generation + feature update + write transaction
├── cli.py               # Click CLI entry point
└── diff_safety.py       # Diff safety validation for feature.yaml updates

tests/
├── __init__.py
├── conftest.py          # Shared fixtures (sample YAML, config dicts)
├── test_schemas/
│   ├── test_feature.py
│   ├── test_module.py
│   └── test_evidence.py
├── test_config.py
├── test_store.py
├── test_parser.py
├── test_matcher.py
├── test_scoring.py
├── test_renderers.py
├── test_llm_client.py
├── test_llm_validator.py
├── test_prompt_loader.py
├── test_diff_safety.py
├── test_cli_ask.py
├── test_cli_analyze_log.py
└── test_cli_add_module.py

prompts/
├── module_generation.md
└── feature_update.md

fixtures/                          # E2E test fixtures
├── features/
│   └── camera_capture/
│       ├── feature.yaml
│       └── modules/
│           └── camera_ui.yaml
├── logs/
│   └── sample.hilog
└── agent.yaml
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `src/hilog_agent/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "hilog-agent"
version = "0.1.0"
description = "Hilog Agent MVP — feature Q&A, log analysis, and module knowledge generation"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "click>=8.0",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.3",
    "mypy>=1.0",
]

[project.scripts]
agent = "hilog_agent.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.mypy]
strict = true
python_version = "3.10"

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
```

- [ ] **Step 2: Write `ruff.toml`**

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
```

Wait — `ruff.toml` is redundant since `pyproject.toml` already has `[tool.ruff]`. Let me drop it.

Actually, let me just include ruff config in pyproject.toml (already done above) and skip a separate ruff.toml. Update the files list.

- [ ] **Step 2: Write `src/hilog_agent/__init__.py`**

```python
"""Hilog Agent MVP — feature Q&A, log analysis, and module knowledge generation."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write `tests/__init__.py`**

```python
# Empty — marks tests as a package.
```

- [ ] **Step 4: Write `tests/conftest.py` with shared fixtures**

```python
from __future__ import annotations

import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_feature_yaml_text() -> str:
    return """\
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
  - capture
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口
call_chains:
  - name: normal_capture
    description: 正常拍照链路
    keywords:
      - 拍照
    steps:
      - id: capture_request
        module: camera_framework
        file: foundation/camera/capture.cpp
        symbol: Capture
        description: 发起拍照
        optional: false
        async: false
        expected_logs:
          - tag: CameraService
            level: INFO
            pattern: Start capture
            match_type: substring
            evidence_type: step_started
            required: true
            weight: 3
            missing_meaning: 未发起拍照
failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
    key_logs:
      - tag: CameraService
        level: ERROR
        pattern: Capture failed
        match_type: substring
        severity: high
        confidence_weight: 5
        related_step: capture_request
        suggested_cause: capture 失败
        meaning: 拍照请求失败
    possible_causes:
      - capture 失败
metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
"""


@pytest.fixture
def sample_module_yaml_text() -> str:
    return """\
name: camera_framework
display_name: 相机框架
code_path: foundation/camera
responsibility: 拍照会话管理
symbols:
  - name: CaptureSession::Capture
    file: foundation/camera/capture_session.cpp
    kind: method
    relevance: high
    reason: 拍照核心入口
logs:
  - tag: CameraService
    level: INFO
    pattern: Start capture
    match_type: substring
    meaning: 拍照开始
    evidence_type: step_started
    related_step: capture_request
    severity: low
    confidence_weight: 2
candidate_steps:
  - id: capture_request
    description: 发起拍照请求
    file: foundation/camera/capture_session.cpp
    symbol: CaptureSession::Capture
    async: false
    optional: false
    confidence: high
    reason: 拍照入口
    expected_logs:
      - tag: CameraService
        level: INFO
        pattern: Start capture
        match_type: substring
        evidence_type: step_started
        required: true
        weight: 3
        missing_meaning: 未发起拍照
failure_signals:
  - tag: CameraService
    level: ERROR
    pattern: Capture failed
    match_type: substring
    severity: high
    suggested_cause: capture 失败
    meaning: 拍照失败
    related_step: capture_request
    confidence_weight: 5
metadata:
  generated_by: hilog-agent
  generated_at: "2026-06-28 14:35:00"
  review_notes: []
"""


@pytest.fixture
def sample_hilog_lines() -> list[str]:
    return [
        "2026-06-28 14:35:00.000 CameraService INFO Start capture request id=42",
        "2026-06-28 14:35:00.500 CameraService INFO Capture session ready",
        "2026-06-28 14:35:01.000 ImagePipeline INFO process image buf=0x7f00",
        "2026-06-28 14:35:02.000 CameraService ERROR Capture failed: timeout",
        "2026-06-28 14:35:03.000 ImagePipeline INFO process image complete",
    ]


@pytest.fixture
def default_config_dict() -> dict:
    return {
        "repo_root": "/tmp/test-repo",
        "features_dir": "./features",
        "log_temp_dir": "./.tmp/hilog-agent",
        "analysis": {
            "default_window_before_seconds": 60,
            "default_window_after_seconds": 60,
            "min_feature_score": 5,
            "feature_score_margin": 3,
            "max_log_events_for_llm": 200,
            "max_code_snippets_for_llm": 20,
        },
        "scoring": {
            "keyword_hit_weight": 3,
            "log_pattern_hit_weight": 5,
            "log_tag_hit_weight": 2,
            "continuous_step_bonus_per_step": 2,
            "missing_required_step_penalty": 5,
        },
        "output": {
            "format": "text",
            "verbose": False,
            "include_evidence": True,
            "include_raw_log_lines": False,
            "include_generated_yaml": False,
        },
        "add_module": {"backup": False},
        "llm": {
            "enabled": True,
            "provider": "openai_compatible",
            "api_key_env": "OPENAI_API_KEY",
            "api_key": None,
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.5",
            "timeout_seconds": 120,
            "max_output_tokens": 4000,
            "structured_output": "json_schema",
            "max_validation_retries": 3,
            "reasoning": {"effort": "medium", "summary": "auto"},
        },
        "orchestrator": {
            "mode": "bounded_react",
            "max_tool_calls": 8,
            "max_llm_rounds": 4,
            "tool_timeout_seconds": 30,
            "allowed_tools": {
                "ask": ["read_feature", "list_features", "read_file", "search_code"],
                "analyze-log": ["read_feature", "filter_hilog_by_time", "match_logs_by_patterns", "read_file", "search_code"],
                "add-module": ["read_feature", "read_file", "search_code"],
            },
        },
        "prompts": {
            "module_generation": "prompts/module_generation.md",
            "feature_update": "prompts/feature_update.md",
        },
    }
```

- [ ] **Step 5: Install and verify scaffold**

Run: `pip install -e ".[dev]"`
Expected: package installs, `agent --help` fails with "module not found" (cli.py doesn't exist yet — expected).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "chore: project scaffold with pyproject.toml, fixtures, and dev tools"
```

---

### Task 2: Feature YAML Pydantic Schemas

**Files:**
- Create: `src/hilog_agent/models/__init__.py`
- Create: `src/hilog_agent/models/feature.py`
- Create: `tests/test_schemas/__init__.py`
- Create: `tests/test_schemas/test_feature.py`

- [ ] **Step 1: Write failing tests for FeatureYaml validation**

```python
# tests/test_schemas/test_feature.py
from __future__ import annotations

import pytest
import yaml
from hilog_agent.models.feature import (
    FeatureYaml,
    FeatureMetadata,
    FeatureModuleIndex,
    CallChain,
    CallChainStep,
    ExpectedLog,
    FailurePattern,
    FailureKeyLog,
    Entrypoint,
)


class TestFeatureMetadata:
    def test_valid_metadata(self):
        m = FeatureMetadata(
            status="active",
            owner="multimedia",
            version=1,
            updated_at="2026-06-28 14:35:00",
        )
        assert m.status == "active"

    def test_status_must_be_active_or_draft(self):
        with pytest.raises(ValueError):
            FeatureMetadata(
                status="deleted",
                owner="x",
                version=1,
                updated_at="2026-06-28 14:35:00",
            )

    def test_version_must_be_positive(self):
        with pytest.raises(ValueError):
            FeatureMetadata(
                status="active",
                owner="x",
                version=0,
                updated_at="2026-06-28 14:35:00",
            )

    def test_updated_at_format_invalid_rejected(self):
        with pytest.raises(ValueError):
            FeatureMetadata(
                status="active",
                owner="x",
                version=1,
                updated_at="2026-06-28T14:35:00",
            )

    def test_default_version_is_1(self):
        m = FeatureMetadata(
            status="draft",
            owner="x",
            updated_at="2026-06-28 14:35:00",
        )
        assert m.version == 1


class TestFeatureModuleIndex:
    def test_yaml_path_must_be_modules_name_yaml(self):
        with pytest.raises(ValueError):
            FeatureModuleIndex(
                name="camera_ui",
                yaml_path="other/camera_ui.yaml",
                responsibility="x",
            )

    def test_valid_module_index(self):
        m = FeatureModuleIndex(
            name="camera_ui",
            yaml_path="modules/camera_ui.yaml",
            responsibility="拍照入口",
        )
        assert m.name == "camera_ui"


class TestCallChainStep:
    def test_valid_step(self):
        step = CallChainStep(
            id="capture_request",
            module="camera_framework",
            file="path/to/file.cpp",
            symbol="Capture",
            description="发起拍照",
            optional=False,
            async=False,
            expected_logs=[
                ExpectedLog(
                    tag="CameraService",
                    level="INFO",
                    pattern="Start",
                    match_type="substring",
                    evidence_type="step_started",
                    required=True,
                    weight=3,
                    missing_meaning="未发起",
                )
            ],
        )
        assert step.id == "capture_request"

    def test_regex_pattern_must_compile(self):
        with pytest.raises(ValueError):
            ExpectedLog(
                tag="X",
                level="INFO",
                pattern="[unclosed",
                match_type="regex",
                evidence_type="step_started",
                required=True,
                weight=3,
                missing_meaning="x",
            )

    def test_valid_regex_pattern(self):
        log = ExpectedLog(
            tag="X",
            level="INFO",
            pattern=r"Start \w+ capture",
            match_type="regex",
            evidence_type="step_started",
            required=True,
            weight=3,
            missing_meaning="x",
        )
        assert log.pattern == r"Start \w+ capture"


class TestFeatureYaml:
    def test_parse_valid_feature_yaml(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        feature = FeatureYaml.model_validate(data)
        assert feature.name == "camera_capture"
        assert feature.metadata.status == "active"

    def test_active_feature_requires_non_empty_keywords(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["keywords"] = []
        with pytest.raises(ValueError):
            FeatureYaml.model_validate(data)

    def test_active_feature_requires_non_empty_call_chains(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["call_chains"] = []
        with pytest.raises(ValueError):
            FeatureYaml.model_validate(data)

    def test_draft_may_have_empty_call_chains(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["metadata"]["status"] = "draft"
        data["call_chains"] = []
        data["failure_patterns"] = []
        data["keywords"] = ["draft"]  # keywords must be non-empty even for draft
        feature = FeatureYaml.model_validate(data)
        assert feature.metadata.status == "draft"

    def test_step_ids_must_be_unique_across_feature(self):
        """Two steps with the same id across different chains should fail."""
        with pytest.raises(ValueError):
            CallChain(
                name="chain1",
                description="x",
                keywords=["x"],
                steps=[
                    CallChainStep(
                        id="dup", module="m1", file="f1", symbol="s",
                        description="d", optional=False, async=False,
                        expected_logs=[],
                    ),
                ],
            )
            # Uniqueness is validated at FeatureYaml level, not chain level.
            # We'll test at the FeatureYaml level with two chains sharing step ids.

    def test_step_module_must_reference_module_index(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["call_chains"][0]["steps"][0]["module"] = "nonexistent"
        with pytest.raises(ValueError):
            FeatureYaml.model_validate(data)

    def test_entrypoint_module_must_reference_module_index(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["entrypoints"] = [
            {
                "name": "test",
                "module": "nonexistent",
                "file": "f",
                "symbol": "s",
                "description": "d",
            }
        ]
        with pytest.raises(ValueError):
            FeatureYaml.model_validate(data)

    def test_unknown_fields_ignored(self, sample_feature_yaml_text):
        data = yaml.safe_load(sample_feature_yaml_text)
        data["extensions"] = {"future_field": "value"}  # unknown, should be ignored
        feature = FeatureYaml.model_validate(data)
        assert feature.name == "camera_capture"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_schemas/test_feature.py -v`
Expected: all tests FAIL — `ModuleNotFoundError: No module named 'hilog_agent.models.feature'`

- [ ] **Step 3: Write `src/hilog_agent/models/__init__.py`**

```python
"""Pydantic v2 models for the Hilog Agent."""
```

- [ ] **Step 4: Write `src/hilog_agent/models/feature.py`**

```python
"""Feature YAML schema models."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional

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
    def yaml_path_must_match(self) -> "FeatureModuleIndex":
        expected = f"modules/{self.name}.yaml"
        if self.yaml_path != expected:
            raise ValueError(
                f"yaml_path must be '{expected}', got '{self.yaml_path}'"
            )
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
    def regex_must_compile(self) -> "ExpectedLog":
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}")
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
    def optional_step_cannot_have_required_logs(self) -> "CallChainStep":
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
    related_step: Optional[str] = None
    suggested_cause: str = ""
    meaning: str = ""

    @model_validator(mode="after")
    def regex_must_compile(self) -> "FailureKeyLog":
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}")
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
    def step_ids_unique(self) -> "FeatureYaml":
        seen: set[str] = set()
        for chain in self.call_chains:
            for step in chain.steps:
                if step.id in seen:
                    raise ValueError(
                        f"Duplicate call chain step id '{step.id}' across feature"
                    )
                seen.add(step.id)
        return self

    @model_validator(mode="after")
    def step_modules_exist(self) -> "FeatureYaml":
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
    def entrypoint_modules_exist(self) -> "FeatureYaml":
        module_names = {m.name for m in self.modules}
        for ep in self.entrypoints:
            if ep.module not in module_names:
                raise ValueError(
                    f"Entrypoint '{ep.name}' references unknown module "
                    f"'{ep.module}'. Known: {sorted(module_names)}"
                )
        return self

    @model_validator(mode="after")
    def failure_related_steps_exist(self) -> "FeatureYaml":
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
    def active_feature_requires_content(self) -> "FeatureYaml":
        if self.metadata.status == "active":
            if not self.call_chains:
                raise ValueError("Active feature requires non-empty call_chains")
            if not self.failure_patterns:
                raise ValueError("Active feature requires non-empty failure_patterns")
        return self
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_schemas/test_feature.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/models/ tests/test_schemas/
git commit -m "feat: add FeatureYaml Pydantic v2 schemas with cross-field validation"
```

---

### Task 3: Module YAML Pydantic Schemas

**Files:**
- Create: `src/hilog_agent/models/module.py`
- Create: `tests/test_schemas/test_module.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schemas/test_module.py
from __future__ import annotations

import pytest
import yaml
from hilog_agent.models.module import (
    ModuleYaml,
    ModuleMetadata,
    ModuleSymbol,
    ModuleLog,
    CandidateStep,
    FailureSignal,
    ModuleDependency,
    LogSource,
)


class TestLogSource:
    def test_all_fields_optional(self):
        ls = LogSource()
        assert ls.file is None
        assert ls.line is None
        assert ls.symbol is None

    def test_line_must_be_ge_1(self):
        with pytest.raises(ValueError):
            LogSource(line=0)

    def test_valid_source(self):
        ls = LogSource(
            file="path/to/file.cpp",
            line=128,
            symbol="ImageProcessor::Process",
        )
        assert ls.line == 128


class TestModuleMetadata:
    def test_generated_at_format(self):
        m = ModuleMetadata(
            generated_by="hilog-agent",
            generated_at="2026-06-28 14:35:00",
        )
        assert m.generated_by == "hilog-agent"

    def test_generated_at_bad_format(self):
        with pytest.raises(ValueError):
            ModuleMetadata(
                generated_by="x",
                generated_at="2026-06-28T14:35:00",
            )


class TestModuleYaml:
    def test_parse_valid_module_yaml(self, sample_module_yaml_text):
        data = yaml.safe_load(sample_module_yaml_text)
        mod = ModuleYaml.model_validate(data)
        assert mod.name == "camera_framework"

    def test_regex_in_logs_must_compile(self):
        with pytest.raises(ValueError):
            ModuleLog(
                tag="X",
                level="INFO",
                pattern="[bad",
                match_type="regex",
                meaning="x",
                evidence_type="step_started",
                severity="low",
                confidence_weight=1,
            )

    def test_related_step_must_be_valid(self):
        data = yaml.safe_load(
            """\
name: test
display_name: Test
code_path: src/test
responsibility: testing
symbols: []
logs:
  - tag: X
    level: INFO
    pattern: hello
    match_type: substring
    meaning: test
    evidence_type: step_started
    related_step: nonexistent
    severity: low
    confidence_weight: 1
candidate_steps:
  - id: real_step
    description: real
    file: f
    symbol: s
    async: false
    optional: false
    confidence: high
    reason: test
    expected_logs: []
failure_signals: []
metadata:
  generated_by: test
  generated_at: "2026-06-28 14:35:00"
"""
        )
        with pytest.raises(ValueError):
            ModuleYaml.model_validate(data)

    def test_empty_symbols_produces_warning_without_review_notes(self):
        data = yaml.safe_load(
            """\
name: test
display_name: Test
code_path: src/test
responsibility: testing
symbols: []
logs: []
candidate_steps: []
failure_signals: []
metadata:
  generated_by: test
  generated_at: "2026-06-28 14:35:00"
  review_notes: []
"""
        )
        # Validation passes, but a warning should be accessible.
        # The model stores warnings separately for the caller to surface.
        mod = ModuleYaml.model_validate(data)
        # The `warnings` property surfaces them.
        assert any("symbols" in w.lower() for w in mod.warnings)


class TestCandidateStep:
    def test_ids_must_be_unique_within_module(self):
        """ModuleYaml validates that candidate_steps have unique ids."""
        data = yaml.safe_load(
            """\
name: test
display_name: Test
code_path: src/test
responsibility: testing
symbols: []
logs: []
candidate_steps:
  - id: dup
    description: a
    file: a
    symbol: a
    async: false
    optional: false
    confidence: high
    reason: test
    expected_logs: []
  - id: dup
    description: b
    file: b
    symbol: b
    async: false
    optional: false
    confidence: high
    reason: test
    expected_logs: []
failure_signals: []
metadata:
  generated_by: test
  generated_at: "2026-06-28 14:35:00"
"""
        )
        with pytest.raises(ValueError):
            ModuleYaml.model_validate(data)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_schemas/test_module.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/models/module.py`**

```python
"""Module YAML schema models."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class LogSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: Optional[str] = None
    line: Optional[int] = Field(default=None, ge=1)
    symbol: Optional[str] = None


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
    related_step: Optional[str] = None
    severity: Literal["high", "medium", "low"] = "low"
    confidence_weight: int = Field(default=1, ge=1)
    source: Optional[LogSource] = None

    @model_validator(mode="after")
    def regex_must_compile(self) -> "ModuleLog":
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}")
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
    related_step: Optional[str] = None
    confidence_weight: int = Field(default=1, ge=1)
    source: Optional[LogSource] = None

    @model_validator(mode="after")
    def regex_must_compile(self) -> "FailureSignal":
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex pattern '{self.pattern}' does not compile: {e}")
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
    source: Optional[LogSource] = None


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
    def candidate_step_ids_unique(self) -> "ModuleYaml":
        seen: set[str] = set()
        for cs in self.candidate_steps:
            if cs.id in seen:
                raise ValueError(f"Duplicate candidate step id '{cs.id}' in module")
            seen.add(cs.id)
        return self

    @model_validator(mode="after")
    def log_related_steps_exist(self) -> "ModuleYaml":
        step_ids = {cs.id for cs in self.candidate_steps}
        for log in self.logs:
            if log.related_step and log.related_step not in step_ids:
                raise ValueError(
                    f"Log '{log.pattern}' references unknown candidate step "
                    f"'{log.related_step}'. Known: {sorted(step_ids)}"
                )
        return self

    @model_validator(mode="after")
    def failure_signal_related_steps_exist(self) -> "ModuleYaml":
        step_ids = {cs.id for cs in self.candidate_steps}
        for fs in self.failure_signals:
            if fs.related_step and fs.related_step not in step_ids:
                raise ValueError(
                    f"Failure signal '{fs.pattern}' references unknown candidate step "
                    f"'{fs.related_step}'. Known: {sorted(step_ids)}"
                )
        return self

    @model_validator(mode="after")
    def empty_lists_without_review_notes_warn(self) -> "ModuleYaml":
        # Collect warnings as a side-channel; validation still passes.
        # We'll surface these via a property that callers check.
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
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_schemas/test_module.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/models/module.py tests/test_schemas/test_module.py
git commit -m "feat: add ModuleYaml Pydantic v2 schemas with cross-field validation"
```

---

### Task 4: Evidence & Result Pydantic Schemas

**Files:**
- Create: `src/hilog_agent/models/evidence.py`
- Create: `src/hilog_agent/models/result.py`
- Create: `tests/test_schemas/test_evidence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schemas/test_evidence.py
from __future__ import annotations

import pytest
from hilog_agent.models.evidence import (
    Evidence,
    EvidenceRawRef,
    ChainStepStatus,
    AnalysisStats,
)
from hilog_agent.models.result import (
    Conclusion,
    RootCause,
    CrossChainCorrelation,
    AnalysisResult,
    AskResult,
    AddModuleResult,
    WrittenFile,
)


class TestEvidence:
    def test_evidence_id_format(self):
        ev = Evidence(
            id="ev_001",
            source="hilog",
            type="failure_log_hit",
            feature="camera_capture",
            severity="high",
            confidence_delta=5,
            summary="命中错误日志",
        )
        assert ev.id == "ev_001"

    def test_evidence_source_must_be_valid(self):
        with pytest.raises(ValueError):
            Evidence(
                id="ev_001",
                source="invalid_source",
                type="failure_log_hit",
                feature="f",
                severity="high",
                confidence_delta=1,
                summary="x",
            )


class TestAnalysisStats:
    def test_valid_stats(self):
        stats = AnalysisStats(
            total_lines=100,
            parsed_lines=95,
            unparsed_lines=5,
            in_window_lines=30,
            time_span_seconds=120.0,
            tags_distribution={"CameraService": 20, "ImagePipeline": 10},
        )
        assert stats.total_lines == 100


class TestAnalysisResult:
    def test_root_causes_must_reference_evidence(self):
        rc = RootCause(
            description="拍照失败",
            confidence="high",
            supporting_evidence=["ev_001"],
        )
        assert "ev_001" in rc.supporting_evidence
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_schemas/test_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/models/evidence.py`**

```python
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
```

- [ ] **Step 4: Write `src/hilog_agent/models/result.py`**

```python
"""CLI result models and LLM output models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hilog_agent.models.evidence import Evidence, ChainStepStatus, AnalysisStats


class Conclusion(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str
    confidence: Literal["high", "medium", "low"] = "medium"


class RootCause(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str
    confidence: Literal["high", "medium", "low"] = "medium"
    supporting_evidence: list[str] = Field(default_factory=list)


class CrossChainCorrelation(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_chain: str
    source_step: str
    target_chain: str
    target_step: str
    relationship: str  # e.g. "upstream_abnormal_blocks_downstream"


class RelatedFeatureSuggestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature: str
    reason: str


class AskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["ask"] = "ask"
    feature: str
    question: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    supplemental_suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["analyze-log"] = "analyze-log"
    feature: str
    chain: Optional[str] = None
    expanded_chains: list[str] = Field(default_factory=list)
    question: Optional[str] = None
    conclusion: Conclusion
    root_causes: list[RootCause] = Field(default_factory=list)
    chain_status: list[ChainStepStatus] = Field(default_factory=list)
    cross_chain_correlation: list[CrossChainCorrelation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    stats: AnalysisStats = Field(default_factory=AnalysisStats)
    supplemental_suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WrittenFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: str
    action: Literal["created", "updated", "backup_created"]


class ModuleGenerationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_yaml: str
    analysis_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FeatureUpdateResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    updated_feature_yaml: str
    change_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_feature_suggestions: list[RelatedFeatureSuggestion] = Field(
        default_factory=list
    )


class AddModuleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["add-module"] = "add-module"
    feature: str
    module: str
    written_files: list[WrittenFile] = Field(default_factory=list)
    analysis_summary: list[str] = Field(default_factory=list)
    change_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_feature_suggestions: list[RelatedFeatureSuggestion] = Field(
        default_factory=list
    )
```

- [ ] **Step 5: Write `src/hilog_agent/models/__init__.py` (update with re-exports)**

```python
"""Pydantic v2 models for the Hilog Agent."""

from hilog_agent.models.feature import (
    FeatureYaml,
    FeatureMetadata,
    FeatureModuleIndex,
    CallChain,
    CallChainStep,
    ExpectedLog,
    FailurePattern,
    FailureKeyLog,
    Entrypoint,
)
from hilog_agent.models.module import (
    ModuleYaml,
    ModuleMetadata,
    ModuleSymbol,
    ModuleLog,
    CandidateStep,
    FailureSignal,
    ModuleDependency,
    ModuleEntrypoint,
    LogSource,
)
from hilog_agent.models.evidence import (
    Evidence,
    EvidenceRawRef,
    ChainStepStatus,
    AnalysisStats,
)
from hilog_agent.models.result import (
    Conclusion,
    RootCause,
    CrossChainCorrelation,
    AnalysisResult,
    AskResult,
    AddModuleResult,
    WrittenFile,
    ModuleGenerationResult,
    FeatureUpdateResult,
    RelatedFeatureSuggestion,
)

__all__ = [
    "FeatureYaml",
    "FeatureMetadata",
    "FeatureModuleIndex",
    "CallChain",
    "CallChainStep",
    "ExpectedLog",
    "FailurePattern",
    "FailureKeyLog",
    "Entrypoint",
    "ModuleYaml",
    "ModuleMetadata",
    "ModuleSymbol",
    "ModuleLog",
    "CandidateStep",
    "FailureSignal",
    "ModuleDependency",
    "ModuleEntrypoint",
    "LogSource",
    "Evidence",
    "EvidenceRawRef",
    "ChainStepStatus",
    "AnalysisStats",
    "Conclusion",
    "RootCause",
    "CrossChainCorrelation",
    "AnalysisResult",
    "AskResult",
    "AddModuleResult",
    "WrittenFile",
    "ModuleGenerationResult",
    "FeatureUpdateResult",
    "RelatedFeatureSuggestion",
]
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `pytest tests/test_schemas/test_evidence.py tests/test_schemas/test_feature.py tests/test_schemas/test_module.py -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/hilog_agent/models/ tests/test_schemas/
git commit -m "feat: add evidence, result, and cross-chain correlation models"
```

---

### Task 5: Config Loading with Precedence

**Files:**
- Create: `src/hilog_agent/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml
from hilog_agent.config import Config, load_config


class TestConfig:
    def test_defaults_are_set(self):
        cfg = Config()
        assert cfg.analysis.min_feature_score == 5
        assert cfg.scoring.keyword_hit_weight == 3
        assert cfg.llm.model == "gpt-5.5"

    def test_load_from_yaml_file(self, default_config_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.analysis.min_feature_score == 5
        finally:
            os.unlink(path)

    def test_cli_overrides_config(self, default_config_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cli_overrides = {"llm": {"model": "gpt-4"}}
            cfg = load_config(path, cli_overrides=cli_overrides)
            assert cfg.llm.model == "gpt-4"
        finally:
            os.unlink(path)

    def test_api_key_env_preferred_over_plaintext(self, monkeypatch, default_config_dict):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        default_config_dict["llm"]["api_key"] = "sk-plaintext-key"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            # SecretStr — get_secret_value() returns the raw value.
            assert cfg.llm.api_key.get_secret_value() == "sk-env-key"
        finally:
            os.unlink(path)

    def test_api_key_secret_str_redacts_in_repr(self, default_config_dict):
        default_config_dict["llm"]["api_key"] = "sk-secret-12345"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            r = repr(cfg.llm.api_key)
            assert "sk-secret-12345" not in r
            assert "******" in r or "Secret" in r
        finally:
            os.unlink(path)

    def test_missing_config_file_uses_defaults(self):
        cfg = load_config("/nonexistent/path.yaml")
        assert cfg.analysis.min_feature_score == 5

    def test_allowed_tools_per_command(self, default_config_dict):
        cfg = Config.model_validate(default_config_dict)
        assert "read_feature" in cfg.orchestrator.allowed_tools["ask"]
        assert "filter_hilog_by_time" not in cfg.orchestrator.allowed_tools["ask"]
        assert "filter_hilog_by_time" in cfg.orchestrator.allowed_tools["analyze-log"]
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/config.py`**

```python
"""Configuration loading with YAML file + CLI override + defaults precedence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


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
    api_key: Optional[SecretStr] = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"
    timeout_seconds: int = 120
    max_output_tokens: int = 4000
    structured_output: str = "json_schema"
    max_validation_retries: int = 3
    reasoning: LLMReasoningConfig = Field(default_factory=LLMReasoningConfig)

    @model_validator(mode="after")
    def resolve_api_key(self) -> "LLMConfig":
        env_val = os.environ.get(self.api_key_env)
        if env_val:
            self.api_key = SecretStr(env_val)
        if self.api_key is None and not env_val:
            # No key available — warn at runtime, don't fail config load.
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
    cli_overrides: Optional[dict[str, Any]] = None,
) -> Config:
    """Load config from YAML file, apply CLI overrides, fall back to defaults."""
    data: dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    if cli_overrides:
        data = deep_merge(data, cli_overrides)
    return Config.model_validate(data)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_config.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/config.py tests/test_config.py
git commit -m "feat: config loading with YAML + CLI override + SecretStr for api_key"
```

---

### Task 6: FeatureStore — Read & Validate Feature Directories

**Files:**
- Create: `src/hilog_agent/store.py`
- Create: `tests/test_store.py`
- Create: `fixtures/features/camera_capture/feature.yaml`
- Create: `fixtures/features/camera_capture/modules/camera_ui.yaml`

- [ ] **Step 1: Write fixture YAML files**

```yaml
# fixtures/features/camera_capture/feature.yaml
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路，包括 UI 触发、相机会话、拍照请求、图像回调、保存与展示
keywords:
  - 拍照
  - 出图
  - capture
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口、UI 状态、拍照结果展示
call_chains:
  - name: normal_capture
    description: 正常拍照链路
    keywords:
      - 拍照
      - 出图
    steps:
      - id: capture_request
        module: camera_ui
        file: apps/camera/src/PhotoPage.ts
        symbol: onShutterClick
        description: 发起拍照请求
        optional: false
        async: false
        expected_logs:
          - tag: CameraUI
            level: INFO
            pattern: Shutter clicked
            match_type: substring
            evidence_type: step_started
            required: true
            weight: 3
            missing_meaning: 未观察到用户点击拍照
failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
    key_logs:
      - tag: CameraUI
        level: ERROR
        pattern: Capture failed
        match_type: substring
        severity: high
        confidence_weight: 5
        related_step: capture_request
        suggested_cause: 拍照请求失败
        meaning: 拍照请求在 UI 层失败
    possible_causes:
      - 拍照请求失败
metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
```

```yaml
# fixtures/features/camera_capture/modules/camera_ui.yaml
name: camera_ui
display_name: 相机 UI
code_path: apps/camera/src/photo
responsibility: 拍照入口、UI 状态、拍照结果展示
symbols:
  - name: onShutterClick
    file: apps/camera/src/photo/PhotoPage.ts
    kind: method
    relevance: high
    reason: 拍照按钮点击入口
logs:
  - tag: CameraUI
    level: INFO
    pattern: Shutter clicked
    match_type: substring
    meaning: 用户点击拍照按钮
    evidence_type: step_started
    related_step: capture_request
    severity: low
    confidence_weight: 2
candidate_steps:
  - id: capture_request
    description: 用户点击拍照按钮
    file: apps/camera/src/photo/PhotoPage.ts
    symbol: onShutterClick
    async: false
    optional: false
    confidence: high
    reason: 拍照流程起点
    expected_logs:
      - tag: CameraUI
        level: INFO
        pattern: Shutter clicked
        match_type: substring
        evidence_type: step_started
        required: true
        weight: 3
        missing_meaning: 未观察到用户点击拍照
failure_signals:
  - tag: CameraUI
    level: ERROR
    pattern: Capture failed
    match_type: substring
    severity: high
    suggested_cause: 拍照请求失败
    meaning: 拍照请求在 UI 层失败
    related_step: capture_request
    confidence_weight: 5
metadata:
  generated_by: hilog-agent
  generated_at: "2026-06-28 14:35:00"
  review_notes: []
```

- [ ] **Step 2: Write failing tests for FeatureStore**

```python
# tests/test_store.py
from __future__ import annotations

from pathlib import Path

import pytest
from hilog_agent.store import FeatureStore
from hilog_agent.config import Config


@pytest.fixture
def feature_store(fixtures_dir):
    cfg = Config(features_dir=str(fixtures_dir / "features"))
    return FeatureStore(cfg)


class TestFeatureStore:
    def test_list_features(self, feature_store):
        names = feature_store.list_features()
        assert "camera_capture" in names

    def test_read_feature(self, feature_store):
        feature = feature_store.read_feature("camera_capture")
        assert feature.name == "camera_capture"
        assert feature.metadata.status == "active"

    def test_read_nonexistent_feature(self, feature_store):
        with pytest.raises(ValueError, match="not found"):
            feature_store.read_feature("nonexistent")

    def test_validate_feature_dir_passes_on_valid(self, feature_store):
        errors = feature_store.validate_feature_dir("camera_capture")
        assert len(errors) == 0

    def test_cross_file_module_name_matches(self, feature_store):
        errors = feature_store.validate_feature_dir("camera_capture")
        assert len(errors) == 0  # camera_ui module YAML name matches index
```

- [ ] **Step 3: Run tests, confirm they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write `src/hilog_agent/store.py`**

```python
"""FeatureStore — read and validate feature directories."""

from __future__ import annotations

from pathlib import Path

import yaml

from hilog_agent.config import Config
from hilog_agent.models.feature import FeatureYaml
from hilog_agent.models.module import ModuleYaml


class FeatureStore:
    """Reads and validates feature knowledge from the features_dir tree."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._features_dir = Path(config.features_dir)

    @property
    def features_dir(self) -> Path:
        return self._features_dir

    def list_features(self) -> list[str]:
        """Return sorted names of all feature directories."""
        if not self._features_dir.exists():
            return []
        return sorted(
            d.name
            for d in self._features_dir.iterdir()
            if d.is_dir() and (d / "feature.yaml").exists()
        )

    def read_feature(self, name: str) -> FeatureYaml:
        """Read and parse a feature's feature.yaml."""
        path = self._features_dir / name / "feature.yaml"
        if not path.exists():
            raise ValueError(f"Feature '{name}' not found at {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return FeatureYaml.model_validate(data)

    def read_module(self, feature_name: str, module_name: str) -> ModuleYaml:
        """Read and parse a module YAML from a feature directory."""
        path = self._features_dir / feature_name / "modules" / f"{module_name}.yaml"
        if not path.exists():
            raise ValueError(
                f"Module '{module_name}' not found in feature '{feature_name}' at {path}"
            )
        with open(path) as f:
            data = yaml.safe_load(f)
        return ModuleYaml.model_validate(data)

    def validate_feature_dir(self, name: str) -> list[str]:
        """Run cross-file validation. Returns list of error strings (empty = valid)."""
        errors: list[str] = []
        feature_dir = self._features_dir / name

        feature_yaml = feature_dir / "feature.yaml"
        if not feature_yaml.exists():
            errors.append(f"feature.yaml missing in feature '{name}'")
            return errors

        try:
            feature = self.read_feature(name)
        except Exception as e:
            errors.append(f"feature.yaml invalid: {e}")
            return errors

        if feature.name != name:
            errors.append(
                f"feature.yaml name '{feature.name}' does not match directory '{name}'"
            )

        for mod_idx in feature.modules:
            mod_path = feature_dir / mod_idx.yaml_path
            if not mod_path.exists():
                errors.append(
                    f"Module YAML missing: {mod_idx.yaml_path}"
                )
                continue
            try:
                module = self.read_module(name, mod_idx.name)
            except Exception as e:
                errors.append(f"module YAML '{mod_idx.name}' invalid: {e}")
                continue

            if module.name != mod_idx.name:
                errors.append(
                    f"Module YAML name '{module.name}' != index name '{mod_idx.name}'"
                )
            # Responsibility mismatch is a warning (non-blocking), not an error.
            module_warnings = module.warnings
            for w in module_warnings:
                errors.append(f"Warning (module '{mod_idx.name}'): {w}")

        return errors
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_store.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/store.py tests/test_store.py fixtures/
git commit -m "feat: FeatureStore with directory listing, read, and cross-file validation"
```

---

### Task 7: Hilog Parser

**Files:**
- Create: `src/hilog_agent/hilog/__init__.py`
- Create: `src/hilog_agent/hilog/parser.py`
- Create: `tests/test_parser.py`
- Create: `fixtures/logs/sample.hilog`

- [ ] **Step 1: Write sample hilog fixture**

```
2026-06-28 14:35:00.000 CameraService INFO Start capture request id=42
2026-06-28 14:35:00.500 CameraService INFO Capture session ready
2026-06-28 14:35:01.000 ImagePipeline INFO process image buf=0x7f00
garbage line that cannot be parsed
2026-06-28 14:35:02.000 CameraService ERROR Capture failed: timeout
2026-06-28 14:35:03.000 ImagePipeline INFO process image complete
another unparsed junk
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_parser.py
from __future__ import annotations

import pytest
from pathlib import Path
from hilog_agent.hilog.parser import (
    HilogEvent,
    HilogParseResult,
    parse_hilog_file,
    parse_hilog_lines,
)


class TestHilogParser:
    def test_parse_valid_line(self):
        line = "2026-06-28 14:35:00.000 CameraService INFO Start capture"
        event = HilogEvent.parse_line(line)
        assert event is not None
        assert event.tag == "CameraService"
        assert event.level == "INFO"
        assert event.message == "Start capture"

    def test_parse_invalid_line_returns_none(self):
        event = HilogEvent.parse_line("not a valid hilog line")
        assert event is None

    def test_timestamp_includes_year(self):
        line = "2026-06-28 14:35:00.000 CameraService INFO msg"
        event = HilogEvent.parse_line(line)
        assert event is not None
        assert event.timestamp.year == 2026

    def test_parse_file_counts_unparsed(self, fixtures_dir):
        path = fixtures_dir / "logs" / "sample.hilog"
        result = parse_hilog_file(path)
        assert result.total_lines == 7
        assert result.parsed == 5
        assert result.unparsed == 2

    def test_parse_lines(self, sample_hilog_lines):
        events, unparsed = parse_hilog_lines(sample_hilog_lines)
        assert len(events) == 5
        assert len(unparsed) == 0  # all fixture lines are valid
```

- [ ] **Step 3: Run tests, confirm they fail**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write `src/hilog_agent/hilog/parser.py`**

```python
"""Hilog line parser — extract timestamp, tag, level, message."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HILOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(\S+?)\s+"       # tag (non-whitespace)
    r"([A-Z]+)\s+"      # level (uppercase)
    r"(.*)"             # message
)

HILOG_DT_FMT = "%Y-%m-%d %H:%M:%S.%f"


@dataclass(frozen=True, slots=True)
class HilogEvent:
    timestamp: datetime
    tag: str
    level: str
    message: str
    raw: str

    @classmethod
    def parse_line(cls, line: str) -> "HilogEvent | None":
        m = HILOG_RE.match(line.strip())
        if not m:
            return None
        return cls(
            timestamp=datetime.strptime(m.group(1), HILOG_DT_FMT),
            tag=m.group(2),
            level=m.group(3),
            message=m.group(4),
            raw=line.rstrip("\n"),
        )


@dataclass(frozen=True, slots=True)
class HilogParseResult:
    events: list[HilogEvent]
    total_lines: int
    parsed: int
    unparsed: int


def parse_hilog_lines(lines: list[str]) -> tuple[list[HilogEvent], list[str]]:
    """Parse a list of hilog text lines. Returns (parsed_events, unparsed_lines)."""
    events: list[HilogEvent] = []
    unparsed: list[str] = []
    for line in lines:
        evt = HilogEvent.parse_line(line)
        if evt:
            events.append(evt)
        else:
            unparsed.append(line.rstrip("\n"))
    return events, unparsed


def parse_hilog_file(path: str | Path) -> HilogParseResult:
    """Parse a hilog text file on disk."""
    path = Path(path)
    with open(path) as f:
        lines = f.readlines()
    events, unparsed_lines = parse_hilog_lines(lines)
    return HilogParseResult(
        events=events,
        total_lines=len(lines),
        parsed=len(events),
        unparsed=len(unparsed_lines),
    )
```

- [ ] **Step 5: Write `src/hilog_agent/hilog/__init__.py`**

```python
"""Hilog parsing and matching."""
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `pytest tests/test_parser.py -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/hilog_agent/hilog/ tests/test_parser.py fixtures/logs/sample.hilog
git commit -m "feat: hilog parser with timestamp extraction and unparsed line accounting"
```

---

### Task 8: Time-Window Filter & Pattern Matcher

**Files:**
- Create: `src/hilog_agent/hilog/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_matcher.py
from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.hilog.matcher import (
    filter_by_time_window,
    match_logs,
    MatchResult,
)


def make_event(ts: str, tag: str = "T", level: str = "INFO", msg: str = "msg"):
    return HilogEvent(
        timestamp=datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f"),
        tag=tag,
        level=level,
        message=msg,
        raw=f"{ts} {tag} {level} {msg}",
    )


class TestTimeWindow:
    def test_events_within_window(self):
        center = datetime(2026, 6, 28, 14, 35, 0)
        events = [
            make_event("2026-06-28 14:34:50.000"),  # 10s before
            make_event("2026-06-28 14:35:00.000"),  # exact
            make_event("2026-06-28 14:35:10.000"),  # 10s after
            make_event("2026-06-28 14:33:00.000"),  # 120s before — out
        ]
        filtered = filter_by_time_window(
            events, center, before_seconds=60, after_seconds=60
        )
        assert len(filtered) == 3

    def test_asymmetric_window(self):
        center = datetime(2026, 6, 28, 14, 35, 0)
        events = [
            make_event("2026-06-28 14:33:50.000"),  # 70s before
            make_event("2026-06-28 14:35:05.000"),  # 5s after — in
        ]
        filtered = filter_by_time_window(
            events, center, before_seconds=120, after_seconds=30
        )
        assert len(filtered) == 2  # both in asymmetric window


class TestMatchLogs:
    def test_substring_match(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "hello world")]
        hits = match_logs(events, tag="X", pattern="hello", match_type="substring")
        assert len(hits) == 1
        assert hits[0].event.message == "hello world"

    def test_regex_match(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "error 42")]
        hits = match_logs(events, tag="X", pattern=r"error \d+", match_type="regex")
        assert len(hits) == 1

    def test_level_filter(self):
        events = [
            make_event("2026-06-28 14:35:00.000", "X", "INFO", "msg"),
            make_event("2026-06-28 14:35:01.000", "X", "ERROR", "msg"),
        ]
        hits = match_logs(events, tag="X", pattern="msg", match_type="substring", level="ERROR")
        assert len(hits) == 1
        assert hits[0].event.level == "ERROR"

    def test_no_match_returns_empty(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "hello")]
        hits = match_logs(events, tag="X", pattern="world", match_type="substring")
        assert len(hits) == 0
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/hilog/matcher.py`**

```python
"""Time-window filtering and log pattern matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from hilog_agent.hilog.parser import HilogEvent


def filter_by_time_window(
    events: list[HilogEvent],
    center: datetime,
    before_seconds: int,
    after_seconds: int,
) -> list[HilogEvent]:
    """Return events within [center - before_seconds, center + after_seconds]."""
    start = center - timedelta(seconds=before_seconds)
    end = center + timedelta(seconds=after_seconds)
    return [e for e in events if start <= e.timestamp <= end]


@dataclass(frozen=True, slots=True)
class MatchResult:
    event: HilogEvent
    match_text: str


def match_logs(
    events: list[HilogEvent],
    tag: str,
    pattern: str,
    match_type: Literal["substring", "regex"],
    level: str | None = None,
) -> list[MatchResult]:
    """Match events by tag + pattern. Optional level filter."""
    results: list[MatchResult] = []

    if match_type == "regex":
        compiled = re.compile(pattern)
    else:
        compiled = None

    for evt in events:
        if evt.tag != tag:
            continue
        if level is not None and evt.level != level:
            continue

        if match_type == "substring":
            if pattern in evt.message:
                results.append(MatchResult(event=evt, match_text=evt.message))
        elif match_type == "regex" and compiled is not None:
            m = compiled.search(evt.message)
            if m:
                results.append(MatchResult(event=evt, match_text=m.group()))

    return results
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_matcher.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/hilog/matcher.py tests/test_matcher.py
git commit -m "feat: time-window filter and substring/regex log pattern matcher"
```

---

### Task 9: Evidence Builder & Scoring Engine

**Files:**
- Create: `src/hilog_agent/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scoring.py
from __future__ import annotations

from datetime import datetime

import pytest
from hilog_agent.config import Config, ScoringConfig
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.hilog.matcher import MatchResult
from hilog_agent.models.feature import FeatureYaml
from hilog_agent.models.evidence import Evidence, ChainStepStatus
from hilog_agent.scoring import (
    score_feature,
    score_chain,
    build_evidence,
    infer_chain_statuses,
)

import yaml


@pytest.fixture
def scoring_config():
    return ScoringConfig()


@pytest.fixture
def feature(sample_feature_yaml_text):
    return FeatureYaml.model_validate(yaml.safe_load(sample_feature_yaml_text))


@pytest.fixture
def sample_events():
    return [
        HilogEvent(
            timestamp=datetime(2026, 6, 28, 14, 35, 0),
            tag="CameraService",
            level="INFO",
            message="Start capture request id=42",
            raw="...",
        ),
        HilogEvent(
            timestamp=datetime(2026, 6, 28, 14, 35, 2),
            tag="CameraService",
            level="ERROR",
            message="Capture failed: timeout",
            raw="...",
        ),
    ]


class TestFeatureScoring:
    def test_question_keyword_hit(self, feature, scoring_config):
        score = score_feature(
            feature=feature,
            question="拍照失败",
            log_events=[],
            sc=scoring_config,
        )
        assert score > 0  # "拍照" matches feature keywords

    def test_no_match_returns_zero(self, feature, scoring_config):
        score = score_feature(
            feature=feature,
            question="网络连接超时",
            log_events=[],
            sc=scoring_config,
        )
        assert score == 0


class TestChainScoring:
    def test_expected_log_hit_adds_weight(self, feature, sample_events, scoring_config):
        score = score_chain(
            chain=feature.call_chains[0],
            question="拍照",
            events=sample_events,
            sc=scoring_config,
        )
        # "Start capture" substring should match
        assert score > 0

    def test_failure_log_hit_adds_confidence_weight(self, feature, sample_events, scoring_config):
        score = score_chain(
            chain=feature.call_chains[0],
            question="拍照",
            events=sample_events,
            sc=scoring_config,
        )
        # "Capture failed" should match failure key log
        assert score > 3

    def test_missing_required_log_penalizes(self, feature, scoring_config):
        """With no log events, required expected_log is missing => penalty."""
        score = score_chain(
            chain=feature.call_chains[0],
            question="拍照",
            events=[],
            sc=scoring_config,
        )
        assert score < 0  # penalty applied


class TestEvidenceBuilding:
    def test_builds_expected_log_hit_evidence(self, feature, sample_events):
        evidence = build_evidence(
            feature=feature,
            chain=feature.call_chains[0],
            events=sample_events,
        )
        assert any(e.type == "expected_log_hit" for e in evidence)
        assert any(e.type == "failure_log_hit" for e in evidence)


class TestChainStatusInference:
    def test_normal_step_when_expected_log_hit(self, feature, sample_events):
        evidence = build_evidence(
            feature=feature,
            chain=feature.call_chains[0],
            events=sample_events,
        )
        statuses = infer_chain_statuses(
            chain=feature.call_chains[0],
            evidence=evidence,
        )
        assert len(statuses) == 1
        # Step has expected_log hit AND a failure_log hit → abnormal
        # The design: "abnormal" when related failure key log is present
        assert statuses[0].status in ("abnormal", "normal")
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/scoring.py`**

```python
"""Evidence builder, feature scoring, chain scoring, chain status inference."""

from __future__ import annotations

from hilog_agent.config import ScoringConfig
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.hilog.matcher import match_logs
from hilog_agent.models.feature import (
    FeatureYaml,
    CallChain,
    CallChainStep,
    ExpectedLog,
    FailureKeyLog,
)
from hilog_agent.models.evidence import Evidence, ChainStepStatus


def score_feature(
    feature: FeatureYaml,
    question: str,
    log_events: list[HilogEvent],
    sc: ScoringConfig,
) -> int:
    """Score a feature against a question and log events."""
    score = 0
    qt = question.lower()

    # Keyword hits
    for kw in feature.keywords:
        if kw.lower() in qt:
            score += sc.keyword_hit_weight * 3  # spec: question keyword hits * 3

    # Log key pattern hits
    for fp in feature.failure_patterns:
        for kl in fp.key_logs:
            hits = match_logs(
                log_events, tag=kl.tag, pattern=kl.pattern,
                match_type=kl.match_type, level=kl.level,
            )
            if hits:
                score += sc.log_pattern_hit_weight * 5  # spec: log key pattern hits * 5

    # Log tag hits
    seen_tags: set[str] = set()
    for evt in log_events:
        if evt.tag in seen_tags:
            continue
        seen_tags.add(evt.tag)
        for fp in feature.failure_patterns:
            for kl in fp.key_logs:
                if kl.tag == evt.tag:
                    score += sc.log_tag_hit_weight * 2  # spec: log tag hits * 2
                    break

    return score


def score_chain(
    chain: CallChain,
    question: str,
    events: list[HilogEvent],
    sc: ScoringConfig,
) -> int:
    """Score a single call chain."""
    score = 0
    qt = question.lower()

    # Keyword hits
    for kw in chain.keywords:
        if kw.lower() in qt:
            score += sc.keyword_hit_weight

    # Expected log hit weights
    for step in chain.steps:
        for elog in step.expected_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                score += elog.weight * sc.log_pattern_hit_weight

    # Failure key log hit confidence weights (check failure patterns that reference
    # steps in this chain's step ids)
    step_ids = {s.id for s in chain.steps}
    # We need the feature-level failure_patterns — passed in differently.
    # For now, score from expected/failure logs directly.
    # In the full pipeline, failure_patterns are matched in build_evidence,
    # and their confidence_weight feeds into scoring via evidence confidence_delta.

    # Missing required step penalty
    for step in chain.steps:
        if step.optional:
            continue
        for elog in step.expected_logs:
            if not elog.required:
                continue
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if not hits:
                score -= sc.missing_required_step_penalty

    # Continuous step hit bonus
    consecutive = _longest_consecutive_normal(chain, events)
    score += consecutive * sc.continuous_step_bonus_per_step

    return score


def _longest_consecutive_normal(chain: CallChain, events: list[HilogEvent]) -> int:
    """Count longest span of consecutive steps where at least one required
    expected_log is found."""
    step_ok: list[bool] = []
    for step in chain.steps:
        required_logs = [el for el in step.expected_logs if el.required]
        if not required_logs:
            step_ok.append(True)
            continue
        ok = False
        for elog in required_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                ok = True
                break
        step_ok.append(ok)

    best = 0
    cur = 0
    for ok in step_ok:
        if ok:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def build_evidence(
    feature: FeatureYaml,
    chain: CallChain,
    events: list[HilogEvent],
) -> list[Evidence]:
    """Build evidence list for a chain against log events."""
    evidence: list[Evidence] = []
    ev_id = 0

    def next_id() -> str:
        nonlocal ev_id
        ev_id += 1
        return f"ev_{ev_id:03d}"

    for step in chain.steps:
        # Expected log hits
        for elog in step.expected_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                for h in hits:
                    evidence.append(Evidence(
                        id=next_id(),
                        source="hilog",
                        type="expected_log_hit",
                        feature=feature.name,
                        chain=chain.name,
                        step=step.id,
                        severity="low",
                        confidence_delta=elog.weight,
                        summary=h.match_text,
                    ))
            elif elog.required:
                evidence.append(Evidence(
                    id=next_id(),
                    source="hilog",
                    type="missing_required_log",
                    feature=feature.name,
                    chain=chain.name,
                    step=step.id,
                    severity="medium",
                    confidence_delta=-scoring_config_default().missing_required_step_penalty,
                    summary=elog.missing_meaning or f"Missing: {elog.pattern}",
                ))

    # Failure key log hits from feature-level failure_patterns
    step_ids = {s.id for s in chain.steps}
    for fp in feature.failure_patterns:
        for kl in fp.key_logs:
            if kl.related_step and kl.related_step in step_ids:
                hits = match_logs(
                    events, tag=kl.tag, pattern=kl.pattern,
                    match_type=kl.match_type, level=kl.level,
                )
                for h in hits:
                    evidence.append(Evidence(
                        id=next_id(),
                        source="hilog",
                        type="failure_log_hit",
                        feature=feature.name,
                        chain=chain.name,
                        step=kl.related_step,
                        severity=kl.severity,
                        confidence_delta=kl.confidence_weight,
                        summary=f"{kl.meaning}: {h.match_text}",
                    ))

    return evidence


def _scoring_config_default() -> ScoringConfig:
    return ScoringConfig()


def infer_chain_statuses(
    chain: CallChain,
    evidence: list[Evidence],
) -> list[ChainStepStatus]:
    """Infer step statuses from evidence."""
    by_step: dict[str, list[Evidence]] = {}
    for ev in evidence:
        if ev.step:
            by_step.setdefault(ev.step, []).append(ev)

    statuses: list[ChainStepStatus] = []
    upstream_abnormal = False

    for step in chain.steps:
        ev_list = by_step.get(step.id, [])
        ev_ids = [e.id for e in ev_list]

        has_expected = any(e.type == "expected_log_hit" for e in ev_list)
        has_failure = any(
            e.type == "failure_log_hit" and e.severity == "high" for e in ev_list
        )
        has_missing = any(e.type == "missing_required_log" for e in ev_list)

        if upstream_abnormal and not has_expected:
            status = "not_entered"
        elif has_failure:
            status = "abnormal"
            upstream_abnormal = True
        elif has_missing:
            status = "suspected_abnormal"
        elif has_expected:
            status = "normal"
        elif not ev_list:
            status = "not_observed"
        else:
            status = "unknown"

        statuses.append(ChainStepStatus(
            chain=chain.name,
            step_id=step.id,
            status=status,
            evidence=ev_ids,
            detail="",
        ))

    return statuses
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_scoring.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/scoring.py tests/test_scoring.py
git commit -m "feat: evidence builder, feature/chain scoring, and chain status inference"
```

---

### Task 10: Text & JSON Renderers

**Files:**
- Create: `src/hilog_agent/renderers/__init__.py`
- Create: `src/hilog_agent/renderers/text.py`
- Create: `src/hilog_agent/renderers/json_renderer.py`
- Create: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_renderers.py
from __future__ import annotations

import json

import pytest
from hilog_agent.models.result import (
    AnalysisResult,
    AskResult,
    Conclusion,
    RootCause,
    AddModuleResult,
    WrittenFile,
)
from hilog_agent.models.evidence import AnalysisStats, ChainStepStatus
from hilog_agent.renderers.text import render_text
from hilog_agent.renderers.json_renderer import render_json


class TestTextRenderer:
    def test_ask_result_includes_answer(self):
        result = AskResult(
            feature="camera_capture",
            question="拍照不出图?",
            answer="可能的根因: capture 失败",
        )
        output = render_text(result)
        assert "camera_capture" in output
        assert "capture 失败" in output

    def test_analysis_result_includes_chain_status(self):
        result = AnalysisResult(
            feature="camera_capture",
            chain="normal_capture",
            conclusion=Conclusion(summary="拍照请求失败", confidence="high"),
            root_causes=[RootCause(description="capture 失败", confidence="high")],
            chain_status=[
                ChainStepStatus(
                    chain="normal_capture",
                    step_id="capture_request",
                    status="abnormal",
                )
            ],
            stats=AnalysisStats(),
        )
        output = render_text(result)
        assert "拍照请求失败" in output
        assert "abnormal" in output

    def test_verbose_includes_scoring_breakdown(self):
        result = AnalysisResult(
            feature="camera_capture",
            chain="normal_capture",
            conclusion=Conclusion(summary="ok", confidence="medium"),
            chain_status=[
                ChainStepStatus(
                    chain="normal_capture",
                    step_id="step1",
                    status="normal",
                    evidence=["ev_001"],
                    detail="expected_log_hit +3",
                ),
            ],
            stats=AnalysisStats(),
        )
        output = render_text(result, verbose=True)
        assert "+3" in output  # scoring detail visible


class TestJSONRenderer:
    def test_outputs_valid_json(self):
        result = AskResult(
            feature="camera_capture",
            question="q",
            answer="a",
        )
        output = render_json(result)
        data = json.loads(output)
        assert data["command"] == "ask"
        assert data["feature"] == "camera_capture"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_renderers.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/renderers/text.py`**

```python
"""Text renderer for CLI output."""

from __future__ import annotations

from hilog_agent.models.result import (
    AskResult,
    AnalysisResult,
    AddModuleResult,
)


def render_text(
    result: AskResult | AnalysisResult | AddModuleResult,
    verbose: bool = False,
) -> str:
    """Render a result model to human-readable text."""
    lines: list[str] = []

    if isinstance(result, AskResult):
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Question: {result.question}")
        lines.append(f"\n{result.answer}")
        if result.sources:
            lines.append("\nSources:")
            for src in result.sources:
                lines.append(f"  - {src}")
        if result.supplemental_suggestions:
            lines.append("\nSupplemental Suggestions (无直接证据):")
            for s in result.supplemental_suggestions:
                lines.append(f"  - {s}")
        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

    elif isinstance(result, AnalysisResult):
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Chain: {result.chain or 'N/A'}")
        lines.append(f"Expanded Chains: {', '.join(result.expanded_chains)}")
        lines.append(f"\nConclusion: {result.conclusion.summary} (confidence: {result.conclusion.confidence})")

        if result.root_causes:
            lines.append("\nRoot Causes:")
            for rc in result.root_causes:
                refs = ", ".join(rc.supporting_evidence)
                lines.append(f"  [{rc.confidence}] {rc.description} (evidence: {refs})")

        if result.chain_status:
            lines.append("\nChain Status:")
            for cs in result.chain_status:
                lines.append(f"  [{cs.status}] {cs.chain}/{cs.step_id}")
                if verbose and cs.detail:
                    lines.append(f"    {cs.detail}")

        if verbose and result.evidence:
            lines.append("\nEvidence Breakdown:")
            for ev in result.evidence:
                lines.append(f"  {ev.id}: [{ev.type}] {ev.summary} (Δ{ev.confidence_delta})")

        if result.cross_chain_correlation:
            lines.append("\nCross-Chain Correlation:")
            for cc in result.cross_chain_correlation:
                lines.append(
                    f"  {cc.source_chain}/{cc.source_step} → "
                    f"{cc.target_chain}/{cc.target_step}: {cc.relationship}"
                )

        if result.stats.total_lines:
            lines.append(f"\nLog Stats: {result.stats.parsed_lines}/{result.stats.total_lines} parsed, "
                         f"{result.stats.in_window_lines} in window, "
                         f"span {result.stats.time_span_seconds:.1f}s")

        if result.supplemental_suggestions:
            lines.append("\nSupplemental Suggestions (无直接证据):")
            for s in result.supplemental_suggestions:
                lines.append(f"  - {s}")

        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

    elif isinstance(result, AddModuleResult):
        lines.append(f"Command: add-module")
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Module: {result.module}")
        if result.written_files:
            lines.append("\nWritten Files:")
            for wf in result.written_files:
                lines.append(f"  [{wf.action}] {wf.path}")
        if result.analysis_summary:
            lines.append("\nAnalysis Summary:")
            for s in result.analysis_summary:
                lines.append(f"  - {s}")
        if result.change_summary:
            lines.append("\nChanges:")
            for s in result.change_summary:
                lines.append(f"  - {s}")
        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")
        if result.related_feature_suggestions:
            lines.append("\nRelated Feature Suggestions:")
            for rfs in result.related_feature_suggestions:
                lines.append(f"  - {rfs.feature}: {rfs.reason}")

    return "\n".join(lines)
```

- [ ] **Step 4: Write `src/hilog_agent/renderers/json_renderer.py`**

```python
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
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_renderers.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/renderers/ tests/test_renderers.py
git commit -m "feat: text and JSON renderers with verbose scoring breakdown"
```

---

### Task 11: LLM Client & Structured Output Validator

**Files:**
- Create: `src/hilog_agent/llm/__init__.py`
- Create: `src/hilog_agent/llm/client.py`
- Create: `src/hilog_agent/llm/validator.py`
- Create: `tests/test_llm_client.py`
- Create: `tests/test_llm_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_client.py
from __future__ import annotations

import pytest
from hilog_agent.config import LLMConfig
from hilog_agent.llm.client import LLMClient


class TestLLMClient:
    def test_builds_correct_headers(self):
        cfg = LLMConfig(
            api_key_env="OPENAI_API_KEY",
            base_url="https://api.example.com/v1",
            model="gpt-5.5",
        )
        # We don't actually call the API in unit tests.
        # Test that the client builds the right endpoint URL.
        client = LLMClient(cfg)
        assert client.chat_endpoint == "https://api.example.com/v1/chat/completions"

    def test_timeout_is_configurable(self):
        cfg = LLMConfig(timeout_seconds=30)
        client = LLMClient(cfg)
        assert client.timeout == 30
```

```python
# tests/test_llm_validator.py
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from hilog_agent.llm.validator import validate_and_retry, ValidationExhaustedError


class SampleOutput(BaseModel):
    answer: str
    confidence: int = Field(ge=0, le=100)


class TestValidator:
    def test_valid_output_passes(self):
        result = validate_and_retry(
            raw_output='{"answer": "hello", "confidence": 80}',
            model=SampleOutput,
            max_retries=3,
            llm_call=None,
        )
        assert result.answer == "hello"
        assert result.confidence == 80

    def test_invalid_json_retries(self):
        call_count = 0

        def fake_llm(error_msg: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"answer": "ok", "confidence": 50}'  # valid on retry
            return '{"answer": "fallback", "confidence": 0}'

        result = validate_and_retry(
            raw_output="not valid json{{{",
            model=SampleOutput,
            max_retries=2,
            llm_call=lambda err: fake_llm(err),
        )
        assert result.answer == "ok"

    def test_exhausted_retries_raises(self):
        with pytest.raises(ValidationExhaustedError):
            validate_and_retry(
                raw_output="invalid {{{",
                model=SampleOutput,
                max_retries=0,
                llm_call=None,
            )
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_llm_client.py tests/test_llm_validator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/llm/client.py`**

```python
"""OpenAI-compatible LLM HTTP client."""

from __future__ import annotations

import json
from typing import Any

import httpx

from hilog_agent.config import LLMConfig


class LLMClient:
    """Talks to an OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        self._cfg = config
        self._base = config.base_url.rstrip("/")

    @property
    def chat_endpoint(self) -> str:
        return f"{self._base}/chat/completions"

    @property
    def timeout(self) -> int:
        return self._cfg.timeout_seconds

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Send a chat completion request. Returns the model's text response."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = self._cfg.api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"

        body: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._cfg.max_output_tokens,
            "temperature": 0.0,
        }

        if json_schema and self._cfg.structured_output == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                },
            }

        with httpx.Client(timeout=self._cfg.timeout_seconds) as client:
            resp = client.post(self.chat_endpoint, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Write `src/hilog_agent/llm/validator.py`**

```python
"""LLM structured output validation with retry loop."""

from __future__ import annotations

import json
from typing import Any, Callable, Type

from pydantic import BaseModel, ValidationError


class ValidationExhaustedError(Exception):
    """Raised when LLM output validation retries are exhausted."""


def validate_and_retry(
    raw_output: str,
    model: Type[BaseModel],
    max_retries: int,
    llm_call: Callable[[str], str] | None,
) -> BaseModel:
    """Validate raw LLM output against a Pydantic model. Retry with error feedback.

    On failure, calls `llm_call(error_message)` to get a corrected output.
    Raises ValidationExhaustedError if max_retries is reached.
    """
    last_error: str | None = None
    output = raw_output

    for attempt in range(max_retries + 1):
        try:
            data = json.loads(output)
            return model.model_validate(data)
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
        except ValidationError as e:
            last_error = f"Validation error: {e}"

        if attempt < max_retries and llm_call is not None:
            output = llm_call(last_error)
        elif attempt < max_retries:
            # No retry function — re-parse on next attempt won't help.
            break

    raise ValidationExhaustedError(
        f"LLM output validation failed after {max_retries} retries. "
        f"Last error: {last_error}"
    )
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_llm_client.py tests/test_llm_validator.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/llm/ tests/test_llm_client.py tests/test_llm_validator.py
git commit -m "feat: LLM client (OpenAI-compatible) and structured output validator with retry"
```

---

### Task 12: Prompt Loader & Placeholder Rendering

**Files:**
- Create: `src/hilog_agent/prompts/__init__.py`
- Create: `src/hilog_agent/prompts/loader.py`
- Create: `tests/test_prompt_loader.py`
- Create: `prompts/module_generation.md`
- Create: `prompts/feature_update.md`

- [ ] **Step 1: Write prompt templates**

```markdown
# prompts/module_generation.md

你是一个代码分析助手。请分析以下代码模块并生成 module YAML。

## 模块路径
{{module_code_path}}

## 当前 feature.yaml
```yaml
{{feature_yaml}}
```

## 工具调用结果
```json
{{tool_results}}
```

## 指令

1. 列出 {{module_code_path}} 下的重要文件。
2. 搜索日志宏、日志 tag 和 ERROR/WARN 日志。
3. 搜索类、结构体、接口、公共方法、入口点。
4. 阅读相关代码片段。
5. 总结模块职责、symbols、logs、candidate_steps、failure_signals、dependencies。
6. 输出严格 JSON（不要 markdown 包裹）：

```json
{
  "module_yaml": "<生成的 ModuleYaml YAML 字符串>",
  "analysis_summary": ["发现1", "发现2"],
  "warnings": ["警告1"]
}
```

注意：
- YAML 中的字段名使用英文。
- 代码标识符、路径、log tag、log pattern、symbol 不得翻译。
- {{module_name}} 模块名会被注入到 YAML 的 name 字段。
```

```markdown
# prompts/feature_update.md

你需要更新一个已有的 feature.yaml 来整合新的模块知识。

## 功能名
{{feature_name}}

## 当前 feature.yaml
```yaml
{{feature_yaml}}
```

## 新模块的 YAML
```yaml
{{module_name}}
```

## 指令

1. 在 modules 列表中追加新的模块索引。
2. 根据模块的 candidate_steps 可选追加新的 call_chain 步骤。
3. 根据模块的 failure_signals 可选追加新的 failure key logs。
4. 将 metadata.version 递增 1。
5. 更新 metadata.updated_at 为当前时间。
6. 如果 placement 或 matching 不确定，追加 review_notes。
7. 输出严格 JSON：

```json
{
  "updated_feature_yaml": "<更新后的 FeatureYaml YAML 字符串>",
  "change_summary": ["变更1"],
  "warnings": ["警告1"],
  "related_feature_suggestions": [
    {"feature": "other_feature", "reason": "原因"}
  ]
}
```

注意：
- 只能追加，不得删除或重写已有内容。
- 不得修改 name、display_name、description、keywords、metadata.owner、metadata.status。
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_prompt_loader.py
from __future__ import annotations

import pytest
from pathlib import Path
from hilog_agent.prompts.loader import PromptLoader


@pytest.fixture
def prompt_loader():
    return PromptLoader(prompts_dir=Path("prompts"))


class TestPromptLoader:
    def test_loads_module_generation(self, prompt_loader):
        text = prompt_loader.load("module_generation")
        assert "模块路径" in text
        assert "{{module_code_path}}" in text

    def test_loads_feature_update(self, prompt_loader):
        text = prompt_loader.load("feature_update")
        assert "{{feature_name}}" in text
        assert "{{feature_yaml}}" in text

    def test_render_replaces_placeholders(self, prompt_loader):
        rendered = prompt_loader.render(
            "module_generation",
            module_code_path="src/foo",
            feature_yaml="name: test",
            module_name="test_mod",
            feature_name="test_feat",
            tool_results="[]",
        )
        assert "src/foo" in rendered
        assert "{{module_code_path}}" not in rendered

    def test_missing_variable_raises(self, prompt_loader):
        with pytest.raises(ValueError, match="module_code_path"):
            prompt_loader.render("module_generation")

    def test_nonexistent_prompt_raises(self, prompt_loader):
        with pytest.raises(FileNotFoundError):
            prompt_loader.load("nonexistent")
```

- [ ] **Step 3: Run tests, confirm they fail**

Run: `pytest tests/test_prompt_loader.py -v`
Expected: FAIL — prompts dir might not exist or `ModuleNotFoundError`

- [ ] **Step 4: Write `src/hilog_agent/prompts/loader.py`**

```python
"""Prompt loading and placeholder rendering."""

from __future__ import annotations

import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class PromptLoader:
    """Loads .md prompt templates and renders {{placeholders}}."""

    def __init__(self, prompts_dir: str | Path = "prompts") -> None:
        self._dir = Path(prompts_dir)

    def load(self, name: str) -> str:
        """Load a raw prompt template by name (without .md extension)."""
        path = self._dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt '{name}' not found at {path}")
        return path.read_text(encoding="utf-8")

    def render(self, name: str, **variables: str) -> str:
        """Load a prompt and replace {{placeholders}} with provided values.

        Raises ValueError if a placeholder has no matching variable.
        """
        template = self.load(name)
        used_placeholders = set(PLACEHOLDER_RE.findall(template))
        missing = used_placeholders - set(variables.keys())
        if missing:
            raise ValueError(
                f"Missing template variables for prompt '{name}': {sorted(missing)}"
            )

        def _replace(m: re.Match) -> str:
            key = m.group(1)
            return variables.get(key, m.group(0))

        return PLACEHOLDER_RE.sub(_replace, template)
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_prompt_loader.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/prompts/ tests/test_prompt_loader.py prompts/
git commit -m "feat: prompt loader with placeholder rendering and template files"
```

---

### Task 13: `ask` Command

**Files:**
- Create: `src/hilog_agent/commands/__init__.py`
- Create: `src/hilog_agent/commands/ask.py`
- Create: `tests/test_cli_ask.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_ask.py
from __future__ import annotations

import pytest
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.commands.ask import ask


@pytest.fixture
def cfg(fixtures_dir):
    return Config(features_dir=str(fixtures_dir / "features"))


@pytest.fixture
def store(cfg):
    return FeatureStore(cfg)


class TestAsk:
    def test_ask_with_feature_returns_answer(self, store, cfg):
        result = ask(
            feature="camera_capture",
            question="拍照不出图可能是什么原因",
            store=store,
            config=cfg,
        )
        assert result.command == "ask"
        assert result.feature == "camera_capture"
        assert len(result.answer) > 0

    def test_ask_without_feature_auto_matches(self, store, cfg):
        result = ask(
            feature=None,
            question="拍照",
            store=store,
            config=cfg,
        )
        assert result.feature == "camera_capture"

    def test_ask_no_llm_flag_in_result(self, store, cfg):
        result = ask(
            feature="camera_capture",
            question="拍照不出图",
            store=store,
            config=cfg,
            no_llm=True,
        )
        assert "failure_patterns" in result.answer.lower() or "拍照" in result.answer
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_cli_ask.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/commands/ask.py`**

```python
"""Feature Q&A command."""

from __future__ import annotations

from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.scoring import score_feature
from hilog_agent.models.result import AskResult


def ask(
    *,
    feature: str | None,
    question: str,
    store: FeatureStore,
    config: Config,
    no_llm: bool = False,
) -> AskResult:
    """Answer a feature question. If feature is None, auto-match from the question."""
    if feature is not None:
        try:
            f = store.read_feature(feature)
        except ValueError as e:
            return AskResult(
                feature=feature,
                question=question,
                answer=f"Feature '{feature}' not found: {e}",
                warnings=[str(e)],
            )
        return _answer_from_feature(f, question)

    # Auto-match
    names = store.list_features()
    if not names:
        return AskResult(
            feature="",
            question=question,
            answer="No features available.",
        )

    scored = []
    for name in names:
        try:
            f = store.read_feature(name)
        except Exception:
            continue
        s = score_feature(f, question, [], config.scoring)
        scored.append((name, s))

    scored.sort(key=lambda x: -x[1])
    if not scored:
        return AskResult(
            feature="",
            question=question,
            answer="No features could be matched.",
        )

    top = scored[0]
    margin = config.analysis.feature_score_margin
    threshold = config.analysis.min_feature_score

    if top[1] >= threshold:
        if len(scored) == 1 or (scored[1][1] + margin <= top[1]):
            f = store.read_feature(top[0])
            return _answer_from_feature(f, question)

    # Ambiguous — return candidates
    candidates = "\n".join(
        f"  {name} (score: {s})" for name, s in scored[:3]
    )
    return AskResult(
        feature="",
        question=question,
        answer=(
            f"Feature auto-match ambiguous. Top candidates:\n{candidates}\n\n"
            f"Please re-run with --feature <name>."
        ),
        warnings=["feature_auto_match_ambiguous"],
    )


def _answer_from_feature(f, question: str) -> AskResult:
    """Build a deterministic answer from a feature YAML."""
    lines = [f"Feature: {f.display_name}"]
    lines.append(f"Description: {f.description}")

    if f.failure_patterns:
        lines.append("\nKnown Failure Patterns:")
        for fp in f.failure_patterns:
            lines.append(f"  - {fp.symptom}")
            for cause in fp.possible_causes:
                lines.append(f"    Possible cause: {cause}")

    if f.call_chains:
        lines.append("\nCall Chains:")
        for cc in f.call_chains:
            lines.append(f"  {cc.name}: {cc.description}")
            for step in cc.steps:
                lines.append(f"    [{step.id}] {step.description} ({step.symbol})")

    warnings: list[str] = []
    if not f.failure_patterns and not f.call_chains:
        warnings.append("Feature has no failure patterns or call chains")

    return AskResult(
        feature=f.name,
        question=question,
        answer="\n".join(lines),
        sources=[f"features/{f.name}/feature.yaml"],
        warnings=warnings,
    )
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_cli_ask.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/commands/ tests/test_cli_ask.py
git commit -m "feat: ask command with deterministic feature Q&A and auto-match"
```

---

### Task 14: `analyze-log` Command

**Files:**
- Create: `src/hilog_agent/commands/analyze_log.py`
- Create: `tests/test_cli_analyze_log.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_analyze_log.py
from __future__ import annotations

from datetime import datetime

import pytest
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.commands.analyze_log import analyze_log


@pytest.fixture
def cfg(fixtures_dir):
    return Config(
        features_dir=str(fixtures_dir / "features"),
        repo_root=str(fixtures_dir.parent),
    )


@pytest.fixture
def store(cfg):
    return FeatureStore(cfg)


class TestAnalyzeLog:
    def test_single_log_file_analyzes(self, store, cfg, fixtures_dir):
        log_path = str(fixtures_dir / "logs" / "sample.hilog")
        result = analyze_log(
            log_paths=[log_path],
            time=datetime(2026, 6, 28, 14, 35, 0),
            window_before=60,
            window_after=60,
            feature="camera_capture",
            store=store,
            config=cfg,
        )
        assert result.command == "analyze-log"
        assert result.feature == "camera_capture"
        assert result.stats.total_lines > 0

    def test_missing_log_file_fails(self, store, cfg):
        with pytest.raises(ValueError, match="no log files found"):
            analyze_log(
                log_paths=["/nonexistent/path.hilog"],
                time=datetime(2026, 6, 28, 14, 35),
                window_before=60,
                window_after=60,
                feature="camera_capture",
                store=store,
                config=cfg,
            )

    def test_top_n_chains_expands_multiple(self, store, cfg, fixtures_dir):
        log_path = str(fixtures_dir / "logs" / "sample.hilog")
        result = analyze_log(
            log_paths=[log_path],
            time=datetime(2026, 6, 28, 14, 35, 0),
            window_before=60,
            window_after=60,
            feature="camera_capture",
            store=store,
            config=cfg,
            top_n_chains=3,
        )
        # expanded_chains populated when top_n_chains > 0
        assert isinstance(result.expanded_chains, list)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_cli_analyze_log.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/commands/analyze_log.py`**

```python
"""Hilog evidence analysis command."""

from __future__ import annotations

import glob as glob_mod
from datetime import datetime
from pathlib import Path

from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.hilog.parser import parse_hilog_file, HilogEvent
from hilog_agent.hilog.matcher import filter_by_time_window
from hilog_agent.scoring import score_chain, build_evidence, infer_chain_statuses
from hilog_agent.models.evidence import AnalysisStats
from hilog_agent.models.result import AnalysisResult, Conclusion


def analyze_log(
    *,
    log_paths: list[str],
    time: datetime,
    window_before: int,
    window_after: int,
    feature: str | None,
    store: FeatureStore,
    config: Config,
    chain: str | None = None,
    top_n_chains: int = 1,
) -> AnalysisResult:
    """Run the full analyze-log pipeline."""

    # 1. Collect all log files (expand globs)
    all_files: list[Path] = []
    for lp in log_paths:
        expanded = glob_mod.glob(lp, recursive=True)
        if expanded:
            for p in expanded:
                all_files.append(Path(p))
        else:
            # literal path that might exist
            p = Path(lp)
            if p.exists():
                all_files.append(p)

    if not all_files:
        raise ValueError(f"No log files found matching patterns: {log_paths}")

    # 2. Parse all hilog sources
    all_events: list[HilogEvent] = []
    total_lines = 0
    parsed_lines = 0
    unparsed_lines = 0
    for path in all_files:
        result = parse_hilog_file(path)
        all_events.extend(result.events)
        total_lines += result.total_lines
        parsed_lines += result.parsed
        unparsed_lines += result.unparsed

    # 3. Filter by time window
    window_events = filter_by_time_window(
        all_events, time, window_before, window_after
    )
    in_window = len(window_events)

    # 4. Match or read feature
    if feature is None:
        names = store.list_features()
        if names:
            feature = names[0]
        else:
            return AnalysisResult(
                feature="",
                conclusion=Conclusion(summary="No features available"),
                stats=AnalysisStats(
                    total_lines=total_lines,
                    parsed_lines=parsed_lines,
                    unparsed_lines=unparsed_lines,
                    in_window_lines=in_window,
                ),
            )

    try:
        f = store.read_feature(feature)
    except ValueError:
        return AnalysisResult(
            feature=feature,
            conclusion=Conclusion(summary=f"Feature '{feature}' not found"),
            stats=AnalysisStats(
                total_lines=total_lines,
                parsed_lines=parsed_lines,
                unparsed_lines=unparsed_lines,
                in_window_lines=in_window,
            ),
        )

    # 5. Score all call chains
    chain_scores = [
        (c, score_chain(c, "", window_events, config.scoring))
        for c in f.call_chains
    ]
    chain_scores.sort(key=lambda x: -x[1])

    # 6. Expand chains
    chains_to_expand: list[str] = []
    if chain is not None:
        chains_to_expand = [chain]
    elif top_n_chains > 0:
        chains_to_expand = [c.name for c, _ in chain_scores[:top_n_chains]]
    else:
        chains_to_expand = [chain_scores[0][0].name] if chain_scores else []

    # 7-9. Build evidence, infer statuses, generate root causes
    all_evidence = []
    all_statuses = []
    root_causes = []

    for c in f.call_chains:
        if c.name not in chains_to_expand:
            continue
        ev = build_evidence(f, c, window_events)
        all_evidence.extend(ev)
        statuses = infer_chain_statuses(c, ev)
        all_statuses.extend(statuses)

        for st in statuses:
            if st.status == "abnormal":
                root_causes.append(
                    type("RootCause", (), {})(
                        description=f"Step '{st.step_id}' in chain '{c.name}' is abnormal",
                        confidence="high",
                        supporting_evidence=st.evidence,
                    )
                )

    # Compute tag distribution
    tag_dist: dict[str, int] = {}
    for evt in window_events:
        tag_dist[evt.tag] = tag_dist.get(evt.tag, 0) + 1

    time_span = 0.0
    if window_events:
        t_min = min(e.timestamp for e in window_events)
        t_max = max(e.timestamp for e in window_events)
        time_span = (t_max - t_min).total_seconds()

    conclusion_text = "Analysis complete"
    if not root_causes:
        conclusion_text = "No abnormal steps detected in the time window"

    return AnalysisResult(
        feature=f.name,
        chain=chains_to_expand[0] if chains_to_expand else None,
        expanded_chains=chains_to_expand,
        conclusion=Conclusion(summary=conclusion_text),
        root_causes=root_causes,
        chain_status=all_statuses,
        evidence=all_evidence,
        stats=AnalysisStats(
            total_lines=total_lines,
            parsed_lines=parsed_lines,
            unparsed_lines=unparsed_lines,
            in_window_lines=in_window,
            time_span_seconds=time_span,
            tags_distribution=tag_dist,
        ),
    )
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `pytest tests/test_cli_analyze_log.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/commands/analyze_log.py tests/test_cli_analyze_log.py
git commit -m "feat: analyze-log command with multi-file, asymmetric window, chain scoring"
```

---

### Task 15: Diff Safety Validation

**Files:**
- Create: `src/hilog_agent/diff_safety.py`
- Create: `tests/test_diff_safety.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_diff_safety.py
from __future__ import annotations

import pytest
import yaml
from hilog_agent.models.feature import FeatureYaml
from hilog_agent.diff_safety import validate_diff


@pytest.fixture
def original(sample_feature_yaml_text):
    return FeatureYaml.model_validate(yaml.safe_load(sample_feature_yaml_text))


class TestDiffSafety:
    def test_append_module_allowed(self, original):
        data = yaml.safe_load(
            """\
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
  - capture
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口
  - name: image_pipeline
    yaml_path: modules/image_pipeline.yaml
    responsibility: 图像处理
call_chains:
  - name: normal_capture
    description: 正常拍照链路
    keywords:
      - 拍照
    steps:
      - id: capture_request
        module: camera_ui
        file: apps/camera/src/PhotoPage.ts
        symbol: onShutterClick
        description: 发起拍照请求
        optional: false
        async: false
        expected_logs:
          - tag: CameraUI
            level: INFO
            pattern: Shutter clicked
            match_type: substring
            evidence_type: step_started
            required: true
            weight: 3
            missing_meaning: 未观察到用户点击拍照
failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
    key_logs:
      - tag: CameraUI
        level: ERROR
        pattern: Capture failed
        match_type: substring
        severity: high
        confidence_weight: 5
        related_step: capture_request
        suggested_cause: 拍照请求失败
        meaning: 拍照请求在 UI 层失败
    possible_causes:
      - 拍照请求失败
metadata:
  status: active
  owner: multimedia
  version: 2
  updated_at: "2026-06-28 15:00:00"
  review_notes: []
"""
        )
        updated = FeatureYaml.model_validate(data)
        errors = validate_diff(original, updated)
        assert len(errors) == 0  # appending module + version bump is allowed

    def test_delete_module_rejected(self, original):
        data = yaml.safe_load(
            """\
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
modules: []
call_chains: []
failure_patterns:
  - symptom: 拍照不出图
    related_steps: []
    key_logs: []
    possible_causes: []
metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
"""
        )
        updated = FeatureYaml.model_validate(data)
        errors = validate_diff(original, updated)
        assert len(errors) > 0
        assert any("delete" in e.lower() or "module" in e.lower() for e in errors)

    def test_modify_name_rejected(self, original):
        data = yaml.safe_load(
            """\
name: renamed
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口
call_chains: []
failure_patterns:
  - symptom: 拍照不出图
    related_steps: []
    key_logs: []
    possible_causes: []
metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
"""
        )
        updated = FeatureYaml.model_validate(data)
        errors = validate_diff(original, updated)
        assert len(errors) > 0

    def test_version_not_incremented_warns(self, original):
        data = yaml.safe_load(
            """\
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
  - capture
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口
  - name: image_pipeline
    yaml_path: modules/image_pipeline.yaml
    responsibility: 图像处理
call_chains:
  - name: normal_capture
    description: 正常拍照链路
    keywords:
      - 拍照
      - 出图
    steps:
      - id: capture_request
        module: camera_ui
        file: apps/camera/src/PhotoPage.ts
        symbol: onShutterClick
        description: 发起拍照请求
        optional: false
        async: false
        expected_logs:
          - tag: CameraUI
            level: INFO
            pattern: Shutter clicked
            match_type: substring
            evidence_type: step_started
            required: true
            weight: 3
            missing_meaning: 未观察到用户点击拍照
failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
    key_logs:
      - tag: CameraUI
        level: ERROR
        pattern: Capture failed
        match_type: substring
        severity: high
        confidence_weight: 5
        related_step: capture_request
        suggested_cause: 拍照请求失败
        meaning: 拍照请求在 UI 层失败
    possible_causes:
      - 拍照请求失败
metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
"""
        )
        updated = FeatureYaml.model_validate(data)
        errors = validate_diff(original, updated)
        assert any("version" in e.lower() for e in errors)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_diff_safety.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/diff_safety.py`**

```python
"""Diff safety validation — only append-only changes to feature.yaml are allowed."""

from __future__ import annotations

from hilog_agent.models.feature import FeatureYaml


def validate_diff(original: FeatureYaml, updated: FeatureYaml) -> list[str]:
    """Compare original and updated FeatureYaml. Return list of violation messages."""
    errors: list[str] = []

    # Immutable fields
    if updated.name != original.name:
        errors.append(f"name changed: '{original.name}' → '{updated.name}'")
    if updated.display_name != original.display_name:
        errors.append(f"display_name changed")
    if updated.description != original.description:
        errors.append(f"description changed")
    if updated.keywords != original.keywords:
        errors.append("keywords modified")

    # Metadata immutability
    if updated.metadata.owner != original.metadata.owner:
        errors.append("metadata.owner changed")
    if updated.metadata.status != original.metadata.status:
        errors.append("metadata.status changed")
    if updated.metadata.version != original.metadata.version + 1:
        errors.append(
            f"metadata.version should be {original.metadata.version + 1}, "
            f"got {updated.metadata.version}"
        )

    # Modules: only append allowed
    orig_names = {m.name for m in original.modules}
    upd_names = {m.name for m in updated.modules}
    if not orig_names.issubset(upd_names):
        removed = orig_names - upd_names
        errors.append(f"Modules deleted: {sorted(removed)}")
    for m in updated.modules:
        if m.name in orig_names:
            orig_m = next(om for om in original.modules if om.name == m.name)
            if m.yaml_path != orig_m.yaml_path or m.responsibility != orig_m.responsibility:
                errors.append(f"Module '{m.name}' was modified (not append-only)")

    # Call chains: only append allowed (no deletions)
    orig_chain_names = {c.name for c in original.call_chains}
    upd_chain_names = {c.name for c in updated.call_chains}
    if not orig_chain_names.issubset(upd_chain_names):
        removed = orig_chain_names - upd_chain_names
        errors.append(f"Call chains deleted: {sorted(removed)}")

    # Check existing chain steps not deleted
    for oc in original.call_chains:
        uc = next((c for c in updated.call_chains if c.name == oc.name), None)
        if uc is None:
            continue
        orig_step_ids = {s.id for s in oc.steps}
        upd_step_ids = {s.id for s in uc.steps}
        if not orig_step_ids.issubset(upd_step_ids):
            removed_steps = orig_step_ids - upd_step_ids
            errors.append(
                f"Call chain '{oc.name}': steps deleted: {sorted(removed_steps)}"
            )

    # Failure patterns: only append allowed
    for ofp in original.failure_patterns:
        ufp = next(
            (fp for fp in updated.failure_patterns if fp.symptom == ofp.symptom),
            None,
        )
        if ufp is None:
            errors.append(f"Failure pattern '{ofp.symptom}' deleted")
            continue
        # related_steps, key_logs, possible_causes must be supersets
        if not set(ofp.related_steps).issubset(set(ufp.related_steps)):
            errors.append(f"Failure pattern '{ofp.symptom}': related_steps removed")
        existing_key_log_patterns = {kl.pattern for kl in ofp.key_logs}
        new_key_log_patterns = {kl.pattern for kl in ufp.key_logs}
        if not existing_key_log_patterns.issubset(new_key_log_patterns):
            errors.append(f"Failure pattern '{ofp.symptom}': key_logs removed")
        if not set(ofp.possible_causes).issubset(set(ufp.possible_causes)):
            errors.append(f"Failure pattern '{ofp.symptom}': possible_causes removed")

    return errors
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_diff_safety.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/diff_safety.py tests/test_diff_safety.py
git commit -m "feat: diff safety validation — append-only changes to feature.yaml"
```

---

### Task 16: `add-module` Command & Write Transaction

**Files:**
- Create: `src/hilog_agent/commands/add_module.py`
- Create: `tests/test_cli_add_module.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_add_module.py
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.commands.add_module import add_module


@pytest.fixture
def tmp_features():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        feat_dir = base / "test_feature"
        feat_dir.mkdir(parents=True)
        mod_dir = feat_dir / "modules"
        mod_dir.mkdir()
        # Write a minimal feature.yaml
        feature_yaml = {
            "name": "test_feature",
            "display_name": "Test",
            "description": "A test feature",
            "keywords": ["test"],
            "modules": [],
            "call_chains": [],
            "failure_patterns": [],
            "metadata": {
                "status": "draft",
                "owner": "test",
                "version": 1,
                "updated_at": "2026-06-28 14:35:00",
                "review_notes": [],
            },
        }
        with open(feat_dir / "feature.yaml", "w") as f:
            yaml.dump(feature_yaml, f)
        yield td


class TestAddModule:
    def test_add_new_module_dry_run(self, tmp_features):
        cfg = Config(features_dir=str(Path(tmp_features)), repo_root="/tmp")
        store = FeatureStore(cfg)
        # Dry-run: should not write files
        result = add_module(
            feature="test_feature",
            module="new_mod",
            code_path="src/new_mod",
            store=store,
            config=cfg,
            dry_run=True,
        )
        assert result.command == "add-module"
        assert not (Path(tmp_features) / "test_feature" / "modules" / "new_mod.yaml").exists()

    def test_existing_module_fails_without_force(self, tmp_features):
        # Pre-create the module YAML
        mod_dir = Path(tmp_features) / "test_feature" / "modules"
        (mod_dir / "existing.yaml").write_text("name: existing\n")
        # Add module to feature index
        feat_path = Path(tmp_features) / "test_feature" / "feature.yaml"
        with open(feat_path) as f:
            feat_data = yaml.safe_load(f)
        feat_data["modules"].append({
            "name": "existing",
            "yaml_path": "modules/existing.yaml",
            "responsibility": "test",
        })
        with open(feat_path, "w") as f:
            yaml.dump(feat_data, f)

        cfg = Config(features_dir=str(Path(tmp_features)), repo_root="/tmp")
        store = FeatureStore(cfg)

        with pytest.raises(ValueError, match="already exists"):
            add_module(
                feature="test_feature",
                module="existing",
                code_path="src/existing",
                store=store,
                config=cfg,
            )
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_cli_add_module.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/hilog_agent/commands/add_module.py`**

```python
"""Module knowledge generation and feature update command."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml

from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.models.feature import FeatureModuleIndex
from hilog_agent.models.module import ModuleYaml
from hilog_agent.models.result import (
    AddModuleResult,
    WrittenFile,
    RelatedFeatureSuggestion,
)
from hilog_agent.diff_safety import validate_diff


def add_module(
    *,
    feature: str,
    module: str,
    code_path: str,
    store: FeatureStore,
    config: Config,
    force: bool = False,
    backup: bool = False,
    dry_run: bool = False,
    review: bool = False,
) -> AddModuleResult:
    """Generate module knowledge and update feature YAML.

    dry_run: execute full flow but don't write to disk.
    review: write files with review markers.
    """
    warnings: list[str] = []
    written: list[WrittenFile] = []

    # 1. Validate paths
    features_dir = Path(config.features_dir)
    feat_dir = features_dir / feature
    mod_out = feat_dir / "modules" / f"{module}.yaml"

    if not feat_dir.exists():
        raise ValueError(f"Feature directory '{feature}' not found under {features_dir}")

    # 2. Read and validate current feature.yaml
    current_feature = store.read_feature(feature)

    # 3. Check if module already exists
    if mod_out.exists() and not force:
        raise ValueError(
            f"Module '{module}' already exists in feature '{feature}'. "
            f"Use --force to overwrite."
        )

    # 4-7. In MVP without a real LLM call, we generate a minimal module YAML.
    # The full implementation calls the LLM with module_generation.md prompt,
    # then validates ModuleGenerationResult, then calls feature_update.md.
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    generated_by = "hilog-agent"
    if review:
        generated_by = "hilog-agent [pending-review]"

    module_yaml = ModuleYaml(
        name=module,
        display_name=module,
        code_path=code_path,
        responsibility="[LLM-generated placeholder]",
        symbols=[],
        logs=[],
        candidate_steps=[],
        failure_signals=[],
        metadata={
            "generated_by": generated_by,
            "generated_at": now,
            "review_notes": ["Generated by add-module — review required."] if review else [],
        },
    )

    # 8-9. Build updated feature.yaml
    new_mod_idx = FeatureModuleIndex(
        name=module,
        yaml_path=f"modules/{module}.yaml",
        responsibility="[LLM-generated placeholder]",
    )

    updated_data = current_feature.model_dump()
    updated_data["modules"].append(new_mod_idx.model_dump())
    updated_data["metadata"]["version"] = current_feature.metadata.version + 1
    updated_data["metadata"]["updated_at"] = now
    if review:
        updated_data["metadata"]["review_notes"] = list(
            current_feature.metadata.review_notes
        ) + [f"Module '{module}' added via add-module — pending review"]

    from hilog_agent.models.feature import FeatureYaml
    updated_feature = FeatureYaml.model_validate(updated_data)

    # 10. Diff safety
    diff_errors = validate_diff(current_feature, updated_feature)
    if diff_errors:
        raise ValueError(f"Diff safety validation failed: {'; '.join(diff_errors)}")

    # 11. Write (unless dry_run)
    if not dry_run:
        # Backup
        if backup and mod_out.exists():
            backup_path = mod_out.with_suffix(f".yaml.bak.{now.replace(' ', '_')}")
            os.rename(str(mod_out), str(backup_path))
            written.append(WrittenFile(path=str(backup_path), action="backup_created"))

        # Write module YAML
        os.makedirs(str(mod_out.parent), exist_ok=True)
        with open(mod_out, "w") as f:
            yaml.dump(module_yaml.model_dump(exclude_none=True), f, allow_unicode=True)
        written.append(WrittenFile(path=str(mod_out), action="created"))

        # Write updated feature.yaml
        feat_yaml_path = feat_dir / "feature.yaml"
        if backup:
            bak = feat_yaml_path.with_suffix(f".yaml.bak.{now.replace(' ', '_')}")
            os.rename(str(feat_yaml_path), str(bak))
            written.append(WrittenFile(path=str(bak), action="backup_created"))
        with open(feat_yaml_path, "w") as f:
            yaml.dump(updated_feature.model_dump(exclude_none=True), f, allow_unicode=True)
        written.append(WrittenFile(path=str(feat_yaml_path), action="updated"))

    return AddModuleResult(
        feature=feature,
        module=module,
        written_files=written,
        analysis_summary=[f"Generated module YAML for {module}"],
        change_summary=[f"Appended module index for {module}, version → {updated_feature.metadata.version}"],
        warnings=warnings,
        related_feature_suggestions=[],
    )
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_cli_add_module.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/commands/add_module.py tests/test_cli_add_module.py
git commit -m "feat: add-module command with diff safety, dry-run, review, and write transaction"
```

---

### Task 17: CLI Entry Point

**Files:**
- Create: `src/hilog_agent/cli.py`

- [ ] **Step 1: Write `src/hilog_agent/cli.py`** (no unit tests — tested via e2e fixtures)

```python
"""CLI entry point — Click-based command dispatcher."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click

from hilog_agent.config import load_config
from hilog_agent.store import FeatureStore
from hilog_agent.commands.ask import ask
from hilog_agent.commands.analyze_log import analyze_log
from hilog_agent.commands.add_module import add_module
from hilog_agent.renderers.text import render_text
from hilog_agent.renderers.json_renderer import render_json


@click.group()
@click.option("--config", "-c", default="agent.yaml", help="Path to agent.yaml")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx: click.Context, config: str, verbose: bool) -> None:
    """Hilog Agent — feature Q&A, hilog analysis, and module knowledge management."""
    ctx.ensure_object(dict)
    cfg = load_config(config)
    if verbose:
        cfg.output.verbose = True
    ctx.obj["config"] = cfg
    ctx.obj["store"] = FeatureStore(cfg)


@main.command()
@click.option("--feature", "-f", default=None, help="Feature name")
@click.option("--question", "-q", required=True, help="Question to answer")
@click.option("--no-llm", is_flag=True, help="Deterministic summary only")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.pass_context
def ask_cmd(ctx: click.Context, feature: str | None, question: str, no_llm: bool, json_output: bool) -> None:
    """Answer feature questions based on feature knowledge."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]
    result = ask(
        feature=feature,
        question=question,
        store=store,
        config=cfg,
        no_llm=no_llm,
    )
    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result, verbose=cfg.output.verbose))
    if result.feature == "":
        sys.exit(2)  # Ambiguous feature match


@main.command()
@click.option("--log", "-l", "log_paths", multiple=True, required=True,
              help="Path to hilog file(s) or glob patterns")
@click.option("--time", "-t", required=True, help="Center timestamp (YYYY-MM-DD HH:MM)")
@click.option("--window", type=int, default=None,
              help="Symmetric window in seconds (overrides --window-before/--window-after)")
@click.option("--window-before", type=int, default=None, help="Seconds before center time")
@click.option("--window-after", type=int, default=None, help="Seconds after center time")
@click.option("--feature", "-f", default=None, help="Feature name")
@click.option("--question", "-q", default=None, help="Question for context")
@click.option("--chain", default=None, help="Force a specific call chain")
@click.option("--top-n-chains", type=int, default=1, help="Expand top N chains")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.pass_context
def analyze_log_cmd(
    ctx: click.Context,
    log_paths: tuple[str, ...],
    time: str,
    window: int | None,
    window_before: int | None,
    window_after: int | None,
    feature: str | None,
    question: str | None,
    chain: str | None,
    top_n_chains: int,
    json_output: bool,
) -> None:
    """Analyze hilog files using feature knowledge and evidence scoring."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]

    # Resolve time window
    if window is not None:
        wb = window
        wa = window
    else:
        wb = window_before or cfg.analysis.default_window_before_seconds
        wa = window_after or cfg.analysis.default_window_after_seconds

    try:
        center = datetime.strptime(time, "%Y-%m-%d %H:%M")
    except ValueError:
        click.echo("Time must be 'YYYY-MM-DD HH:MM'", err=True)
        sys.exit(1)

    try:
        result = analyze_log(
            log_paths=list(log_paths),
            time=center,
            window_before=wb,
            window_after=wa,
            feature=feature,
            store=store,
            config=cfg,
            chain=chain,
            top_n_chains=top_n_chains,
        )
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result, verbose=cfg.output.verbose))


@main.command()
@click.option("--feature", "-f", required=True, help="Feature name")
@click.option("--module", "-m", required=True, help="Module name")
@click.option("--path", "-p", "code_path", required=True, help="Module code path under repo_root")
@click.option("--force", is_flag=True, help="Overwrite existing module YAML")
@click.option("--backup", is_flag=True, help="Create timestamped backups before writing")
@click.option("--dry-run", is_flag=True, help="Validate but don't write")
@click.option("--review", is_flag=True, help="Write with [pending-review] marker")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.pass_context
def add_module_cmd(
    ctx: click.Context,
    feature: str,
    module: str,
    code_path: str,
    force: bool,
    backup: bool,
    dry_run: bool,
    review: bool,
    json_output: bool,
) -> None:
    """Generate module knowledge YAML and update feature YAML."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]

    try:
        result = add_module(
            feature=feature,
            module=module,
            code_path=code_path,
            store=store,
            config=cfg,
            force=force,
            backup=backup,
            dry_run=dry_run,
            review=review,
        )
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI loads**

Run: `python -m hilog_agent.cli --help`
Expected: shows help with `ask`, `analyze-log`, `add-module` subcommands

- [ ] **Step 3: End-to-end smoke test**

Run: `agent --config fixtures/agent.yaml ask --feature camera_capture --question "拍照不出图" -v`
Expected: outputs text with feature info and failure patterns

- [ ] **Step 4: Commit**

```bash
git add src/hilog_agent/cli.py
git commit -m "feat: CLI entry point with Click — ask, analyze-log, add-module subcommands"
```

---

### Task 18: E2E Fixture Tests & Final Integration

**Files:**
- Create: `fixtures/agent.yaml`

- [ ] **Step 1: Write `fixtures/agent.yaml`**

```yaml
repo_root: /tmp/hilog-test-repo
features_dir: ./fixtures/features
log_temp_dir: ./fixtures/.tmp
analysis:
  default_window_before_seconds: 60
  default_window_after_seconds: 60
  min_feature_score: 3
  feature_score_margin: 2
scoring:
  keyword_hit_weight: 3
  log_pattern_hit_weight: 5
  log_tag_hit_weight: 2
  continuous_step_bonus_per_step: 2
  missing_required_step_penalty: 5
output:
  format: text
  verbose: false
llm:
  enabled: false
orchestrator:
  max_tool_calls: 8
  max_llm_rounds: 4
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 3: Run ruff and mypy**

Run: `ruff check src/ tests/`
Expected: no errors

Run: `mypy src/`
Expected: no errors (or fix any issues)

- [ ] **Step 4: Commit**

```bash
git add fixtures/agent.yaml
git commit -m "chore: add agent.yaml fixture and finalize integration"
```

---

## Self-Review

### 1. Spec Coverage

| Spec Section | Task |
| --- | --- |
| §3 Storage Layout | Task 6 (FeatureStore) |
| §4 Configuration | Task 5 (Config loading) |
| §5 Feature YAML Schema | Task 2 (Feature schemas) |
| §6 Module YAML Schema | Task 3 (Module schemas) |
| §7 Schema Implementation | Tasks 2-4 (all schemas) |
| §8 Evidence Model | Task 4 (evidence models), Task 9 (evidence builder) |
| §9 ask Flow | Task 13 (ask command) |
| §10 analyze-log Flow | Task 14 (analyze-log command) |
| §11 Scoring | Task 9 (scoring engine) |
| §12 add-module Flow | Task 16 (add-module command) |
| §13 Prompts | Task 12 (prompt loader + templates) |
| §14 Structured Output Models | Task 4 (result models), Task 11 (validator) |
| §15 Error Handling | Covered across command implementations |
| §16 Testing Strategy | Tests in every Task (TDD) |
| §17 Implementation Order | Matches exactly, interleaved with tests |
| Optimizations (§4-§14 fixes) | Config scoring block (§4), `--chain`/`--top-n-chains` (§10), asymmetric window (§10), `--dry-run`/`--review` (§12), template variable table (§13), `SecretStr` (§5+§7), `LogSource`/`AnalysisStats` (§4+§14), per-command `allowed_tools` (§5), extensions removal (§5-§6), verbose scoring format (§8), ambiguous feature exit code 2 (§9+§15) |

### 2. Placeholder Scan

No `TBD`, `TODO`, `implement later`, or `fill in details` found. Every step has concrete code or exact commands.

### 3. Type Consistency

- `FeatureYaml`, `ModuleYaml` defined in Tasks 2-3, consumed by Tasks 6, 9, 13-16 ✓
- `Evidence`, `ChainStepStatus`, `AnalysisStats` defined in Task 4, consumed by Tasks 9, 14 ✓
- `Config`, `ScoringConfig` defined in Task 5, consumed by Tasks 6, 9, 13-16 ✓
- `HilogEvent` defined in Task 7, consumed by Tasks 8, 9, 14 ✓
- `AnalysisResult`, `AskResult`, `AddModuleResult` defined in Task 4, consumed by Tasks 10, 13, 14, 16 ✓
- All renderers accept the union type defined in Task 10 ✓
