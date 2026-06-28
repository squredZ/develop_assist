# tests/test_orchestrator.py
from __future__ import annotations

from hilog_agent.config import Config
from hilog_agent.orchestrator import SSEEvent, ToolRegistry
from hilog_agent.store import FeatureStore


class TestToolRegistry:
    def test_list_features(self, fixtures_dir):
        cfg = Config(features_dir=str(fixtures_dir / "features"))
        store = FeatureStore(cfg)
        reg = ToolRegistry(store, cfg)
        result = reg.call("list_features", {})
        assert "camera_capture" in result

    def test_read_feature(self, fixtures_dir):
        cfg = Config(features_dir=str(fixtures_dir / "features"))
        store = FeatureStore(cfg)
        reg = ToolRegistry(store, cfg)
        result = reg.call("read_feature", {"feature_name": "camera_capture"})
        assert "camera_capture" in result

    def test_unknown_tool(self, fixtures_dir):
        cfg = Config(features_dir=str(fixtures_dir / "features"))
        store = FeatureStore(cfg)
        reg = ToolRegistry(store, cfg)
        result = reg.call("nonexistent", {})
        assert "Unknown tool" in result

    def test_read_nonexistent_feature(self, fixtures_dir):
        cfg = Config(features_dir=str(fixtures_dir / "features"))
        store = FeatureStore(cfg)
        reg = ToolRegistry(store, cfg)
        result = reg.call("read_feature", {"feature_name": "nonexistent"})
        assert "error" in result.lower()


class TestSSEEvent:
    def test_sse_event_construction(self):
        evt = SSEEvent(event="thinking", data={"text": "hello"})
        assert evt.event == "thinking"
        assert evt.data["text"] == "hello"
