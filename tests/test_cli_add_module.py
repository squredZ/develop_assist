# tests/test_cli_add_module.py
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from hilog_agent.commands.add_module import add_module
from hilog_agent.config import Config
from hilog_agent.store import FeatureStore


@pytest.fixture
def tmp_features():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        feat_dir = base / "test_feature"
        feat_dir.mkdir(parents=True)
        mod_dir = feat_dir / "modules"
        mod_dir.mkdir()
        feature_yaml = {
            "name": "test_feature",
            "display_name": "Test",
            "description": "A test feature",
            "keywords": ["test"],
            "modules": [
                {
                    "name": "dummy",
                    "yaml_path": "modules/dummy.yaml",
                    "responsibility": "placeholder",
                }
            ],
            "call_chains": [],
            "failure_patterns": [],
            "metadata": {
                "status": "draft",
                "owner": "test",
                "version": 1,
                "updated_at": "2026-06-28 14:35:00",
                "review_notes": [],
            },
        }
        with open(feat_dir / "feature.yaml", "w") as f:
            yaml.dump(feature_yaml, f)
        # Also create the dummy module YAML
        dummy_yaml = {
            "name": "dummy",
            "display_name": "Dummy",
            "code_path": "src/dummy",
            "responsibility": "placeholder",
            "symbols": [],
            "logs": [],
            "candidate_steps": [],
            "failure_signals": [],
            "metadata": {
                "generated_by": "test",
                "generated_at": "2026-06-28 14:35:00",
                "review_notes": [],
            },
        }
        with open(mod_dir / "dummy.yaml", "w") as f:
            yaml.dump(dummy_yaml, f)
        yield td


class TestAddModule:
    def test_add_new_module_dry_run(self, tmp_features):
        cfg = Config(features_dir=str(Path(tmp_features)), repo_root="/tmp")
        store = FeatureStore(cfg)
        result = add_module(
            feature="test_feature",
            module="new_mod",
            code_path="src/new_mod",
            store=store,
            config=cfg,
            dry_run=True,
        )
        assert result.command == "add-module"
        assert not (Path(tmp_features) / "test_feature" / "modules" / "new_mod.yaml").exists()

    def test_existing_module_fails_without_force(self, tmp_features):
        mod_dir = Path(tmp_features) / "test_feature" / "modules"
        (mod_dir / "existing.yaml").write_text("name: existing\n")
        feat_path = Path(tmp_features) / "test_feature" / "feature.yaml"
        with open(feat_path) as f:
            feat_data = yaml.safe_load(f)
        feat_data["modules"].append(
            {
                "name": "existing",
                "yaml_path": "modules/existing.yaml",
                "responsibility": "test",
            }
        )
        with open(feat_path, "w") as f:
            yaml.dump(feat_data, f)

        cfg = Config(features_dir=str(Path(tmp_features)), repo_root="/tmp")
        store = FeatureStore(cfg)

        with pytest.raises(ValueError, match="already exists"):
            add_module(
                feature="test_feature",
                module="existing",
                code_path="src/existing",
                store=store,
                config=cfg,
            )
