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
        assert len(errors) == 0
