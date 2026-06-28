# tests/test_schemas/test_feature.py
from __future__ import annotations

import pytest
import yaml

from hilog_agent.models.feature import (
    CallChainStep,
    ExpectedLog,
    FailureKeyLog,
    FeatureMetadata,
    FeatureModuleIndex,
    FeatureYaml,
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
        step = CallChainStep.model_validate(
            {
                "id": "capture_request",
                "module": "camera_framework",
                "file": "path/to/file.cpp",
                "symbol": "Capture",
                "description": "发起拍照",
                "optional": False,
                "async": False,
                "expected_logs": [
                    {
                        "tag": "CameraService",
                        "level": "INFO",
                        "pattern": "Start",
                        "match_type": "substring",
                        "evidence_type": "step_started",
                        "required": True,
                        "weight": 3,
                        "missing_meaning": "未发起",
                    }
                ],
            }
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
        data = {
            "name": "test_feature",
            "display_name": "Test",
            "description": "test",
            "keywords": ["test"],
            "modules": [{"name": "m1", "yaml_path": "modules/m1.yaml", "responsibility": "r"}],
            "call_chains": [
                {
                    "name": "chain1",
                    "description": "x",
                    "keywords": ["x"],
                    "steps": [
                        {
                            "id": "dup",
                            "module": "m1",
                            "file": "f1",
                            "symbol": "s",
                            "description": "d",
                            "optional": False,
                            "async": False,
                            "expected_logs": [],
                        }
                    ],
                },
                {
                    "name": "chain2",
                    "description": "x",
                    "keywords": ["x"],
                    "steps": [
                        {
                            "id": "dup",
                            "module": "m1",
                            "file": "f2",
                            "symbol": "s2",
                            "description": "d2",
                            "optional": False,
                            "async": False,
                            "expected_logs": [],
                        }
                    ],
                },
            ],
            "failure_patterns": [],
            "metadata": {
                "status": "active",
                "owner": "test",
                "version": 1,
                "updated_at": "2026-06-28 14:35:00",
            },
        }
        with pytest.raises(ValueError):
            FeatureYaml.model_validate(data)

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


class TestFailureKeyLog:
    def test_failure_key_log_regex_validation(self):
        with pytest.raises(ValueError):
            FailureKeyLog(
                tag="X",
                level="ERROR",
                pattern="[bad",
                match_type="regex",
                severity="high",
                confidence_weight=5,
                suggested_cause="x",
                meaning="x",
            )
