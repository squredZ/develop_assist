"""FeatureStore — read and validate feature directories."""

from __future__ import annotations

from pathlib import Path

import yaml

from hilog_agent.config import Config
from hilog_agent.models.feature import FeatureYaml
from hilog_agent.models.module import ModuleYaml


class FeatureStore:
    """Reads and validates feature knowledge from the features_dir tree."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._features_dir = Path(config.features_dir)

    @property
    def features_dir(self) -> Path:
        return self._features_dir

    def list_features(self) -> list[str]:
        """Return sorted names of all feature directories."""
        if not self._features_dir.exists():
            return []
        return sorted(
            d.name
            for d in self._features_dir.iterdir()
            if d.is_dir() and (d / "feature.yaml").exists()
        )

    def read_feature(self, name: str) -> FeatureYaml:
        """Read and parse a feature's feature.yaml."""
        path = self._features_dir / name / "feature.yaml"
        if not path.exists():
            raise ValueError(f"Feature '{name}' not found at {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return FeatureYaml.model_validate(data)

    def read_module(self, feature_name: str, module_name: str) -> ModuleYaml:
        """Read and parse a module YAML from a feature directory."""
        path = self._features_dir / feature_name / "modules" / f"{module_name}.yaml"
        if not path.exists():
            raise ValueError(
                f"Module '{module_name}' not found in feature '{feature_name}' at {path}"
            )
        with open(path) as f:
            data = yaml.safe_load(f)
        return ModuleYaml.model_validate(data)

    def validate_feature_dir(self, name: str) -> list[str]:
        """Run cross-file validation. Returns list of error strings (empty = valid)."""
        errors: list[str] = []
        feature_dir = self._features_dir / name

        feature_yaml = feature_dir / "feature.yaml"
        if not feature_yaml.exists():
            errors.append(f"feature.yaml missing in feature '{name}'")
            return errors

        try:
            feature = self.read_feature(name)
        except Exception as e:
            errors.append(f"feature.yaml invalid: {e}")
            return errors

        if feature.name != name:
            errors.append(
                f"feature.yaml name '{feature.name}' does not match directory '{name}'"
            )

        for mod_idx in feature.modules:
            mod_path = feature_dir / mod_idx.yaml_path
            if not mod_path.exists():
                errors.append(
                    f"Module YAML missing: {mod_idx.yaml_path}"
                )
                continue
            try:
                module = self.read_module(name, mod_idx.name)
            except Exception as e:
                errors.append(f"module YAML '{mod_idx.name}' invalid: {e}")
                continue

            if module.name != mod_idx.name:
                errors.append(
                    f"Module YAML name '{module.name}' != index name '{mod_idx.name}'"
                )
            module_warnings = module.warnings
            for w in module_warnings:
                errors.append(f"Warning (module '{mod_idx.name}'): {w}")

        return errors
