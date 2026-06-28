# tests/test_cli_analyze_log.py
from __future__ import annotations

from datetime import datetime

import pytest

from hilog_agent.commands.analyze_log import analyze_log
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore


@pytest.fixture
def cfg(fixtures_dir):
    return Config(
        features_dir=str(fixtures_dir / "features"),
        repo_root=str(fixtures_dir.parent),
    )


@pytest.fixture
def store(cfg):
    return FeatureStore(cfg)


class TestAnalyzeLog:
    def test_single_log_file_analyzes(self, store, cfg, fixtures_dir):
        log_path = str(fixtures_dir / "logs" / "sample.hilog")
        result = analyze_log(
            log_paths=[log_path],
            time=datetime(2026, 6, 28, 14, 35, 0),
            window_before=60,
            window_after=60,
            feature="camera_capture",
            store=store,
            config=cfg,
        )
        assert result.command == "analyze-log"
        assert result.feature == "camera_capture"
        assert result.stats.total_lines > 0

    def test_missing_log_file_fails(self, store, cfg):
        with pytest.raises(ValueError, match=r"[Nn]o log files found"):
            analyze_log(
                log_paths=["/nonexistent/path.hilog"],
                time=datetime(2026, 6, 28, 14, 35),
                window_before=60,
                window_after=60,
                feature="camera_capture",
                store=store,
                config=cfg,
            )

    def test_top_n_chains_expands_multiple(self, store, cfg, fixtures_dir):
        log_path = str(fixtures_dir / "logs" / "sample.hilog")
        result = analyze_log(
            log_paths=[log_path],
            time=datetime(2026, 6, 28, 14, 35, 0),
            window_before=60,
            window_after=60,
            feature="camera_capture",
            store=store,
            config=cfg,
            top_n_chains=3,
        )
        assert isinstance(result.expanded_chains, list)
