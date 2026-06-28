# tests/test_server.py
from __future__ import annotations

from fastapi.testclient import TestClient

from hilog_agent.server import app

client = TestClient(app)


class TestServer:
    def test_features_list(self):
        resp = client.get("/api/features")
        assert resp.status_code == 200
        assert "features" in resp.json()

    def test_config_redacts_api_key(self):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        llm = data.get("llm", {})
        if llm.get("api_key"):
            assert llm["api_key"] == "***"

    def test_ask_no_feature(self):
        resp = client.post("/api/ask", json={
            "session_id": "test",
            "question": "test question",
            "feature": None,
        })
        assert resp.status_code == 200
        assert resp.json()["command"] == "ask"

    def test_sessions_list(self):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert "sessions" in resp.json()

    def test_clear_session(self):
        resp = client.post("/api/sessions/test_clear/clear")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "test_clear"

    def test_missing_feature_404(self):
        resp = client.get("/api/features/nonexistent")
        assert resp.status_code == 404

    def test_analyze_log_bad_time(self):
        resp = client.post("/api/analyze-log", json={
            "log_paths": ["/dev/null"],
            "time": "not-a-time",
            "feature": None,
        })
        assert resp.status_code == 400

    def test_add_module_missing_feature(self):
        resp = client.post("/api/add-module", json={
            "feature": "nonexistent",
            "module": "test",
            "code_path": "src/test",
        })
        assert resp.status_code == 400
