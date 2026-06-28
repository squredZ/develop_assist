# tests/test_prompt_loader.py
from __future__ import annotations

from pathlib import Path

import pytest

from hilog_agent.prompts.loader import PromptLoader


@pytest.fixture
def prompt_loader():
    return PromptLoader(prompts_dir=Path("prompts"))


class TestPromptLoader:
    def test_loads_module_generation(self, prompt_loader):
        text = prompt_loader.load("module_generation")
        assert "模块路径" in text
        assert "{{module_code_path}}" in text

    def test_loads_feature_update(self, prompt_loader):
        text = prompt_loader.load("feature_update")
        assert "{{feature_name}}" in text
        assert "{{feature_yaml}}" in text

    def test_render_replaces_placeholders(self, prompt_loader):
        rendered = prompt_loader.render(
            "module_generation",
            module_code_path="src/foo",
            feature_yaml="name: test",
            module_name="test_mod",
            feature_name="test_feat",
            tool_results="[]",
        )
        assert "src/foo" in rendered
        assert "{{module_code_path}}" not in rendered

    def test_missing_variable_raises(self, prompt_loader):
        with pytest.raises(ValueError, match="module_code_path"):
            prompt_loader.render("module_generation")

    def test_nonexistent_prompt_raises(self, prompt_loader):
        with pytest.raises(FileNotFoundError):
            prompt_loader.load("nonexistent")
