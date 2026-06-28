# REASONIX.md — hilog-agent

## Stack

This project is currently at the **design phase** — no code has been
written yet. The design doc specifies:

- **Language**: Python (Pydantic v2 for schemas)
- **LLM backend**: OpenAI-compatible API (`gpt-5.5` target)
- **Orchestrator**: bounded ReAct loop (max 8 tool calls, 4 LLM rounds)
- **Storage**: local YAML files under `features/<name>/` (feature.yaml + modules/*.yaml)
- **Config**: `agent.yaml` with CLI-override precedence

## Layout

| Path | Purpose |
| --- | --- |
| `2026-06-28-hilog-agent-design.md` | Full MVP design document (sole file in the repo) |

Planned layout per the design doc (none exist yet):

| Dir | Planned purpose |
| --- | --- |
| `features/` | Feature knowledge directories (feature.yaml + modules/*.yaml) |
| `prompts/` | LLM prompt templates (module_generation.md, feature_update.md) |
| `.tmp/hilog-agent/` | Temporary log unpack directory |

## Commands

No manifest file exists — no build/run/test/lint scripts are configured.

The design doc describes three planned CLI commands:

- `agent ask` — feature Q&A (deterministic by default)
- `agent analyze-log` — hilog evidence analysis
- `agent add-module` — LLM-assisted module knowledge generation

## Watch out for

- **This is a design-only repo.** The `2026-06-28-hilog-agent-design.md`
  file is the sole artifact. No code, no schemas, no config — nothing
  else exists to edit or run. A Reasonix session here starts from
  scratch.
- **Implementation order is prescribed** — Section 17 of the design doc
  lists a 14-step sequence starting with Pydantic v2 schema definitions.
  Future sessions should follow it unless explicitly overridden.
