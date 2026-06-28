# tests/test_cli_ask.py
from __future__ import annotations

import pytest

from hilog_agent.commands.ask import ask
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore


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
