"""Prompt loading and placeholder rendering."""

from __future__ import annotations

import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class PromptLoader:
    """Loads .md prompt templates and renders {{placeholders}}."""

    def __init__(self, prompts_dir: str | Path = "prompts") -> None:
        self._dir = Path(prompts_dir)

    def load(self, name: str) -> str:
        """Load a raw prompt template by name (without .md extension)."""
        path = self._dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt '{name}' not found at {path}")
        return path.read_text(encoding="utf-8")

    def render(self, name: str, **variables: str) -> str:
        """Load a prompt and replace {{placeholders}} with provided values.

        Raises ValueError if a placeholder has no matching variable.
        """
        template = self.load(name)
        used_placeholders = set(PLACEHOLDER_RE.findall(template))
        missing = used_placeholders - set(variables.keys())
        if missing:
            raise ValueError(
                f"Missing template variables for prompt '{name}': {sorted(missing)}"
            )

        def _replace(m: re.Match) -> str:
            key = m.group(1)
            return variables.get(key, m.group(0))

        return PLACEHOLDER_RE.sub(_replace, template)
