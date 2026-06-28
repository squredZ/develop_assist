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
        mod = ModuleYaml.model_validate(data)
        assert any("symbols" in w.lower() for w in mod.warnings)


class TestCandidateStep:
    def test_ids_must_be_unique_within_module(self):
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
