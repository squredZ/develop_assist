# tests/test_llm_client.py
from __future__ import annotations

from hilog_agent.config import LLMConfig
from hilog_agent.llm.client import LLMClient


class TestLLMClient:
    def test_builds_correct_headers(self):
        cfg = LLMConfig(
            api_key_env="OPENAI_API_KEY",
            base_url="https://api.example.com/v1",
            model="gpt-5.5",
        )
        client = LLMClient(cfg)
        assert client.chat_endpoint == "https://api.example.com/v1/chat/completions"

    def test_timeout_is_configurable(self):
        cfg = LLMConfig(timeout_seconds=30)
        client = LLMClient(cfg)
        assert client.timeout == 30
