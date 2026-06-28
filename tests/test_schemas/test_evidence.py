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
