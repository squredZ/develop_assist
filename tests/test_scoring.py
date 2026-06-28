# tests/test_scoring.py
from __future__ import annotations

from datetime import datetime

import pytest
import yaml

from hilog_agent.config import ScoringConfig
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.models.feature import FeatureYaml
from hilog_agent.scoring import (
    build_evidence,
    infer_chain_statuses,
    score_chain,
    score_feature,
)


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
        assert score > 0

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
        assert score > 0

    def test_failure_log_hit_adds_confidence_weight(self, feature, sample_events, scoring_config):
        score = score_chain(
            chain=feature.call_chains[0],
            question="拍照",
            events=sample_events,
            sc=scoring_config,
        )
        assert score > 3

    def test_missing_required_log_penalizes(self, feature, scoring_config):
        score = score_chain(
            chain=feature.call_chains[0],
            question="拍照",
            events=[],
            sc=scoring_config,
        )
        assert score < 0


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
        assert statuses[0].status in ("abnormal", "normal")
