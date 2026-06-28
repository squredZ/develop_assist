# tests/test_config.py
from __future__ import annotations

import os
import tempfile

import yaml

from hilog_agent.config import Config, load_config


class TestConfig:
    def test_defaults_are_set(self):
        cfg = Config()
        assert cfg.analysis.min_feature_score == 5
        assert cfg.scoring.keyword_hit_weight == 3
        assert cfg.llm.model == "gpt-5.5"

    def test_load_from_yaml_file(self, default_config_dict):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.analysis.min_feature_score == 5
        finally:
            os.unlink(path)

    def test_cli_overrides_config(self, default_config_dict):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cli_overrides = {"llm": {"model": "gpt-4"}}
            cfg = load_config(path, cli_overrides=cli_overrides)
            assert cfg.llm.model == "gpt-4"
        finally:
            os.unlink(path)

    def test_api_key_env_preferred_over_plaintext(self, monkeypatch, default_config_dict):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        default_config_dict["llm"]["api_key"] = "sk-plaintext-key"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.llm.api_key.get_secret_value() == "sk-env-key"
        finally:
            os.unlink(path)

    def test_api_key_secret_str_redacts_in_repr(self, default_config_dict):
        default_config_dict["llm"]["api_key"] = "sk-secret-12345"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(default_config_dict, f)
            path = f.name
        try:
            cfg = load_config(path)
            r = repr(cfg.llm.api_key)
            assert "sk-secret-12345" not in r
            assert "******" in r or "Secret" in r
        finally:
            os.unlink(path)

    def test_missing_config_file_uses_defaults(self):
        cfg = load_config("/nonexistent/path.yaml")
        assert cfg.analysis.min_feature_score == 5

    def test_allowed_tools_per_command(self, default_config_dict):
        cfg = Config.model_validate(default_config_dict)
        assert "read_feature" in cfg.orchestrator.allowed_tools["ask"]
        assert "filter_hilog_by_time" not in cfg.orchestrator.allowed_tools["ask"]
        assert "filter_hilog_by_time" in cfg.orchestrator.allowed_tools["analyze-log"]
