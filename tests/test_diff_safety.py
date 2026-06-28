# tests/test_diff_safety.py
from __future__ import annotations

import pytest
import yaml

from hilog_agent.diff_safety import validate_diff
from hilog_agent.models.feature import FeatureYaml


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
  - name: camera_framework
    yaml_path: modules/camera_framework.yaml
    responsibility: 相机会话管理
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
        suggested_cause: capture 失败
        meaning: 拍照请求失败
    possible_causes:
      - capture 失败
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
        assert len(errors) == 0

    def test_delete_module_rejected(self, original):
        data = yaml.safe_load(
            """\
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
modules:
  - name: camera_framework
    yaml_path: modules/camera_framework.yaml
    responsibility: 相机会话管理
call_chains:
  - name: normal_capture
    description: test
    keywords:
      - 拍照
    steps:
      - id: cap
        module: camera_framework
        file: f
        symbol: s
        description: d
        optional: false
        async: false
        expected_logs: []
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
call_chains:
  - name: normal_capture
    description: test
    keywords:
      - 拍照
    steps:
      - id: cap
        module: camera_ui
        file: f
        symbol: s
        description: d
        optional: false
        async: false
        expected_logs: []
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
  - name: camera_framework
    yaml_path: modules/camera_framework.yaml
    responsibility: 相机会话管理
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
