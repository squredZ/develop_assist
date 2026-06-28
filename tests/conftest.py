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
  - name: camera_framework
    yaml_path: modules/camera_framework.yaml
    responsibility: 相机会话管理
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
