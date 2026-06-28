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
        assert "+3" in output


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
