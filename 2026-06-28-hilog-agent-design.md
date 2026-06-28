# Hilog Agent MVP Design

## 1. Background

Troubleshooting system feature issues usually requires correlating feature design, code paths, call chains, key logs, error patterns, and hilog events near the failure time. This information is scattered across code, logs, documents, and personal experience.

This agent uses structured feature knowledge, module knowledge, local code, and hilog evidence to support feature Q&A, evidence-driven log analysis, and feature knowledge maintenance.

## 2. MVP Scope

The MVP provides three CLI commands:

```bash
agent ask
agent analyze-log
agent add-module
```

Command responsibilities:

- `ask`: answer feature questions based on feature knowledge, with optional feature auto-matching.
- `analyze-log`: analyze hilog files using feature knowledge, log patterns, call chains, and evidence scoring.
- `add-module`: use an LLM to analyze a module's code, generate module YAML, update the owning feature YAML, validate both, and write them after successful validation.

Non-goals for MVP:

- Web UI
- `remove-module`
- Automatic business code modification
- Automatic modification of other features
- Vector database
- Full-repository knowledge graph
- Full provider plugin system

## 3. Storage Layout

Feature knowledge is stored as a feature directory with one feature-level YAML and multiple module YAML files:

```text
features/
  camera_capture/
    feature.yaml
    modules/
      camera_ui.yaml
      camera_framework.yaml
      image_pipeline.yaml
```

Responsibilities:

- `feature.yaml`: feature-level metadata, keywords, module index, call chains, failure patterns, and feature entrypoints.
- `modules/<module>.yaml`: module-level code path, responsibility, symbols, logs, candidate steps, failure signals, dependencies, and review notes.

`add-module` writes only inside the current feature directory. It never automatically writes other feature directories. If another feature may be related, the command reports `related_feature_suggestions`.

## 4. Configuration

Configuration file: `agent.yaml`.

CLI arguments override config values. Config values override defaults.

```yaml
repo_root: /path/to/source
features_dir: ./features
log_temp_dir: ./.tmp/hilog-agent

analysis:
  default_window_before_seconds: 60
  default_window_after_seconds: 60
  min_feature_score: 5
  feature_score_margin: 3
  max_log_events_for_llm: 200
  max_code_snippets_for_llm: 20

scoring:
  keyword_hit_weight: 3
  log_pattern_hit_weight: 5
  log_tag_hit_weight: 2
  continuous_step_bonus_per_step: 2
  missing_required_step_penalty: 5

output:
  format: text
  verbose: false
  include_evidence: true
  include_raw_log_lines: false
  include_generated_yaml: false

add_module:
  backup: false

llm:
  enabled: true
  provider: openai_compatible
  api_key_env: OPENAI_API_KEY
  api_key: null
  base_url: https://api.openai.com/v1
  model: gpt-5.5
  timeout_seconds: 120
  max_output_tokens: 4000
  structured_output: json_schema
  max_validation_retries: 3
  reasoning:
    effort: medium
    summary: auto

orchestrator:
  mode: bounded_react
  max_tool_calls: 8
  max_llm_rounds: 4
  tool_timeout_seconds: 30
  allowed_tools:
    ask:
      - read_feature
      - list_features
      - read_file
      - search_code
    analyze-log:
      - read_feature
      - filter_hilog_by_time
      - match_logs_by_patterns
      - read_file
      - search_code
    add-module:
      - read_feature
      - read_file
      - search_code

prompts:
  module_generation: prompts/module_generation.md
  feature_update: prompts/feature_update.md
```

The orchestrator is a bounded ReAct loop: the model may plan, request an allowed tool, observe the structured tool result, and continue until it emits validated structured output. It is not a free-form autonomous agent loop.

Command usage:

- `add-module` uses the bounded ReAct orchestrator by default because it must inspect code through tool calls.
- `ask` uses deterministic feature loading by default and can use bounded ReAct only for code-assisted modes.
- `analyze-log` uses deterministic parsing, matching, scoring, and evidence construction first; bounded ReAct is reserved for deep/code-assisted analysis.

LLM rules:

- `api_key_env` is preferred over `api_key`.
- Plaintext `api_key` is allowed but should produce a validation warning.
- Logs, errors, and verbose output must redact API keys.
- `structured_output` supports `json_schema`, `json_object`, and `prompt_only`.
- All LLM output is locally validated even when structured output is enabled.
- If validation fails, retry up to `llm.max_validation_retries`. The default is 3 retries after the first failed attempt.

## 5. Feature YAML Schema

`features/<feature>/feature.yaml` contains feature-level knowledge.

Example:

```yaml
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路，包括 UI 触发、相机会话、拍照请求、图像回调、保存与展示

keywords:
  - 拍照
  - 出图
  - capture

modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口、UI 状态、拍照结果展示

entrypoints:
  - name: 用户点击拍照
    module: camera_ui
    file: applications/camera/src/photo/PhotoPage.ts
    symbol: onShutterClick
    description: UI 侧拍照入口

call_chains:
  - name: normal_capture
    description: 正常拍照链路
    keywords:
      - 拍照
      - 出图
    steps:
      - id: capture_request
        module: camera_framework
        file: foundation/multimedia/camera_framework/services/capture_session.cpp
        symbol: CaptureSession::Capture
        description: 发起拍照请求
        optional: false
        async: false
        expected_logs:
          - tag: CameraService
            level: INFO
            pattern: Start capture
            match_type: substring
            evidence_type: step_started
            required: true
            weight: 3
            missing_meaning: 未观察到拍照请求发起

failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
    key_logs:
      - tag: CameraService
        level: ERROR
        pattern: Capture failed
        match_type: substring
        severity: high
        confidence_weight: 5
        related_step: capture_request
        suggested_cause: capture 请求失败
        meaning: 拍照请求在 CameraService 内失败
    possible_causes:
      - capture 请求失败

metadata:
  status: active
  owner: multimedia
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
```

Required top-level fields:

- `name`
- `display_name`
- `description`
- `keywords`
- `modules`
- `call_chains`
- `failure_patterns`
- `metadata`

Optional top-level fields:

- `entrypoints`

Validation rules:

- `metadata.status` is `draft` or `active`.
- `metadata.version` starts at 1.
- `metadata.updated_at` uses `YYYY-MM-DD HH:mm:ss`.
- `active` features require non-empty `keywords`, `call_chains`, and `failure_patterns`.
- `draft` features may have empty `call_chains` and `failure_patterns`.
- `modules[].yaml_path` must be `modules/<module>.yaml`.
- `call_chains[].steps[].id` must be unique across the whole feature.
- `call_chains[].steps[].module` must reference `modules[].name`.
- `entrypoints[].module` must reference `modules[].name`.
- `failure_patterns[].related_steps` must reference existing step ids.
- `failure_patterns[].key_logs[].related_step`, if present, must reference an existing step id.
- `match_type: regex` patterns must compile.
- Pydantic `model_config` allows extra fields for forwards compatibility; unknown keys are ignored.

## 6. Module YAML Schema

`features/<feature>/modules/<module>.yaml` contains module-level knowledge.

Example:

```yaml
name: image_pipeline
display_name: 图像处理管线
code_path: foundation/multimedia/image_pipeline
responsibility: 图像接收、buffer 处理、图像回调

symbols:
  - name: ImageProcessor::Process
    file: foundation/multimedia/image_pipeline/src/image_processor.cpp
    kind: method
    relevance: high
    reason: 处理拍照图像数据的核心入口

entrypoints:
  - name: start_capture_process
    symbol: ImageProcessor::Start
    file: foundation/multimedia/image_pipeline/src/image_processor.cpp
    description: 图像处理流程入口
    trigger: CaptureSession 收到拍照结果后调用
    confidence: medium

logs:
  - tag: ImagePipeline
    level: INFO
    pattern: process image
    match_type: substring
    meaning: 开始处理图像
    evidence_type: step_started
    related_step: image_pipeline_process
    severity: low
    confidence_weight: 2
    source:
      file: foundation/multimedia/image_pipeline/src/image_processor.cpp
      line: 128
      symbol: ImageProcessor::Process

candidate_steps:
  - id: image_pipeline_process
    description: 处理拍照图像数据
    file: foundation/multimedia/image_pipeline/src/image_processor.cpp
    symbol: ImageProcessor::Process
    async: true
    optional: false
    confidence: medium
    reason: 该函数包含图像处理主日志，并在处理失败时输出错误日志
    expected_logs:
      - tag: ImagePipeline
        level: INFO
        pattern: process image
        match_type: substring
        evidence_type: step_started
        required: true
        weight: 3
        missing_meaning: 未观察到图像处理开始

failure_signals:
  - tag: ImagePipeline
    level: ERROR
    pattern: process failed
    match_type: substring
    severity: high
    suggested_cause: 图像处理失败
    meaning: 图像处理阶段返回失败
    related_step: image_pipeline_process
    confidence_weight: 5
    source:
      file: foundation/multimedia/image_pipeline/src/image_processor.cpp
      line: 152
      symbol: ImageProcessor::Process

dependencies:
  - name: camera_framework
    type: module
    direction: input
    reason: 从 CaptureSession 接收图像数据
    source:
      file: foundation/multimedia/image_pipeline/src/image_processor.cpp
      symbol: ImageProcessor::OnCaptureResult

metadata:
  generated_by: hilog-agent
  generated_at: "2026-06-28 14:35:00"
  review_notes: []
```

Required top-level fields:

- `name`
- `display_name`
- `code_path`
- `responsibility`
- `symbols`
- `logs`
- `candidate_steps`
- `failure_signals`
- `metadata`

Optional top-level fields:

- `entrypoints`
- `dependencies`
- `logs[].source` (optional object with `file`, `line`, `symbol`)
- `failure_signals[].source` (optional object with `file`, `line`, `symbol`)

Validation rules:

- `code_path` is a relative repository path.
- `metadata.generated_at` uses `YYYY-MM-DD HH:mm:ss`.
- `metadata.generated_by` is any non-empty string.
- `candidate_steps[].id` must be unique within the module.
- `logs[].related_step`, if present, must reference a module `candidate_steps[].id`.
- `failure_signals[].related_step`, if present, must reference a module `candidate_steps[].id`.
- `source.line`, if present, must be `>= 1`.
- `match_type: regex` patterns must compile.
- `symbols`, `logs`, `candidate_steps`, and `failure_signals` are required fields but may be empty lists. Empty lists should produce warnings if there are no review notes explaining why.
- Pydantic `model_config` allows extra fields for forwards compatibility; unknown keys are ignored.

## 7. Schema Implementation

Use Pydantic v2 for internal schema validation and JSON Schema export.

Engineering baseline:

- **Python**: >= 3.10
- **Package manager**: uv (or poetry)
- **Layout**: src-layout (`src/hilog_agent/`)
- **Type checker**: mypy (strict mode)
- **Linter + formatter**: ruff
- **API keys**: use `pydantic.SecretStr` for `api_key` — `repr()` and `str()` auto-redact, preventing accidental leak in stack traces, log output, and `__repr__`.

Primary models:

- `FeatureYaml`
- `FeatureMetadata`
- `FeatureModuleIndex`
- `CallChain`
- `CallChainStep`
- `ExpectedLog`
- `FailurePattern`
- `FailureKeyLog`
- `ModuleYaml`
- `ModuleMetadata`
- `ModuleSymbol`
- `ModuleLog`
- `CandidateStep`
- `FailureSignal`
- `ModuleDependency`
- `ModuleEntrypoint`
- `AnalysisResult`
- `AskResult`
- `AddModuleResult`

Rules:

- Enums use lowercase English values, such as `high`, `medium`, `low`.
- CLI text output may localize confidence labels to Chinese.
- Path schema validation checks format only: non-empty, non-absolute, no `..`, and `/` separators.
- Runtime validation checks existence relative to `repo_root` and `features_dir`.
- Cross-file validation is done by `FeatureStore.validate_feature_dir()`.

Cross-file validation:

- `features/<feature>/feature.yaml` must exist.
- `feature.yaml.name` must equal `<feature>`.
- Each `modules[].yaml_path` must exist.
- Each module YAML must pass `ModuleYaml` validation.
- Module YAML `name` must equal the feature index `modules[].name`.
- Module YAML filename must match module name.
- Module responsibility mismatch with index responsibility is a warning, not an error.

## 8. Evidence Model

All tool results are converted into structured evidence before reasoning. LLM output cannot use raw tool results directly as conclusions.

Evidence shape:

```yaml
id: ev_001
source: hilog
type: failure_log_hit
feature: camera_capture
chain: normal_capture
step: capture_request
severity: high
confidence_delta: 5
summary: 命中 CameraService Capture failed
raw_ref:
  file: hilog.txt
  line: 12345
  timestamp: "2026-06-28 14:35:03.500"
```

Evidence sources:

- `hilog`
- `feature_yaml`
- `module_yaml`
- `code`
- `user_input`

Evidence types:

- `expected_log_hit`
- `failure_log_hit`
- `missing_required_log`
- `code_reference`
- `feature_match`
- `chain_match`

Chain step statuses:

- `normal`: key expected logs are present and no related high-severity failure exists.
- `abnormal`: related failure key log is present.
- `suspected_abnormal`: required expected log is missing, or neighboring evidence suggests a possible break.
- `not_entered`: upstream step is abnormal and the later step has no execution evidence.
- `not_observed`: no evidence exists, but the step cannot be inferred as abnormal.
- `unknown`: feature knowledge is insufficient.

Verbose scoring output (`--verbose`): for each scored chain, emit a per-step breakdown showing each scoring contribution. Format:

```text
Chain: normal_capture (score: 42)
  Step capture_request: normal (expected_log_hit "Start capture" +3,
    confidence_delta +3)
  Step image_pipeline_process: suspected_abnormal (missing_required_log
    "process image" -5)
  Bonus: 3 consecutive normal steps → +6 (3 × continuous_step_bonus_per_step)
  ---
  Total: 42
```

This allows operators to trace exactly how the agent arrived at a score and which evidence drove the conclusion.

## 9. ask Flow

Example:

```bash
agent ask \
  --feature camera_capture \
  --question "拍照不出图可能是什么原因"
```

`--feature` is optional.

If the user specifies a feature:

1. Read the feature directory.
2. Validate `feature.yaml`.
3. Answer using feature knowledge.

If the user does not specify a feature:

1. Score candidate features using the question.
2. If Top 1 passes threshold and margin, answer with that feature.
3. Otherwise, show Top 3 candidates with scores, exit with code 2 (`EXIT_FEATURE_AMBIGUOUS`), and expect the user to re-invoke with `--feature`. No interactive loop in MVP — the user re-runs the command. For convenience, `--interactive` (optional) enters an arrow-key selection loop that re-invokes the answered query.

Output sections:

- Based on `feature.yaml`
- Based on code, only when enabled and available
- Supplemental suggestions, explicitly marked as no direct evidence when appropriate

`--no-llm` outputs a deterministic feature summary.

## 10. analyze-log Flow

Example:

```bash
agent analyze-log \
  --log ./hilog.zip \
  --time "2026-06-28 14:35" \
  --window 60 \
  --question "拍照不出图" \
  --feature camera_capture
```

`--log` accepts multiple files and glob patterns:

```bash
agent analyze-log --log "logs/*.hilog" ...
agent analyze-log --log sys.hilog --log app.hilog ...
```

All log files are unpacked (if needed), parsed, and merged before time filtering. File provenance is preserved per event in evidence `raw_ref.file`.

Time-window options:

- `--window N`: shortcut for `--window-before N --window-after N` (symmetric).
- `--window-before N`: seconds before center time.
- `--window-after N`: seconds after center time.
- At least one of `--window` / `--window-before` / `--window-after` must be specified.

Rules:

- Hilog timestamps include year.
- `--time` must be a complete timestamp.
- Unparsed log lines are counted but excluded from time filtering.

Flow:

1. Unpack log file(s) if needed.
2. Parse hilog lines from all log sources.
3. Filter events by time window.
4. Match or read feature.
5. Score all call chains.
6. Expand chains: by default the single highest-scoring chain. Use `--chain <name>` to force a specific chain, or `--top-n-chains N` to expand the top N chains.
7. Build evidence from expected logs, failure logs, and missing required logs.
8. Infer chain statuses. When multiple chains are expanded, include a cross-chain correlation section: if chain A's step is `abnormal` or `suspected_abnormal`, flag downstream chains that depend on it as potentially affected.
9. Generate root-cause candidates.
10. Render text or JSON.

Output includes:

- Conclusion
- Top root-cause candidates
- Chain status table
- Cross-chain correlation (when `--top-n-chains > 1`)
- Evidence
- Log stats
- Warnings

Root-cause candidates must reference evidence ids. Experience-only suggestions go into `supplemental_suggestions`.

## 11. Scoring

All weights are configurable in `agent.yaml` → `scoring:`.

Feature score:

```text
feature_score =
  question keyword/symptom hits × scoring.keyword_hit_weight
+ log key pattern hits × scoring.log_pattern_hit_weight
+ log tag hits × scoring.log_tag_hit_weight
```

Feature auto-selection:

- Top 1 must reach `analysis.min_feature_score`.
- Top 1 must lead Top 2 by `analysis.feature_score_margin`.
- Otherwise output Top 3 candidates, exit with code 2, and expect `--feature` on re-invocation.

Chain score:

```text
chain_score =
  question chain keyword/symptom hits × scoring.keyword_hit_weight
+ Σ expected_log_hit.weight
+ Σ failure_key_log_hit.confidence_weight
+ continuous_step_hit_bonus
- missing_required_step_penalty

Where:
  continuous_step_hit_bonus =
    longest_consecutive_normal_steps × scoring.continuous_step_bonus_per_step

  missing_required_step_penalty =
    count(missing_required_expected_logs) × scoring.missing_required_step_penalty
```

Rules:

- Optional steps do not receive missing penalties.
- Async steps can add hit score but do not require strict adjacency for the consecutive bonus.
- A step whose `optional: true` and whose expected log is `required: true` is contradictory — validation warns.
- Scores must be explainable in verbose output (see Section 8 for format).
- Confidence is internally numeric and externally rendered as `high`, `medium`, or `low`.

## 12. add-module Flow

Example:

```bash
agent add-module \
  --feature camera_capture \
  --module image_pipeline \
  --path foundation/multimedia/image_pipeline
```

The command adds or updates module knowledge under an existing feature directory.

Output files:

```text
features/<feature>/modules/<module>.yaml
features/<feature>/feature.yaml
```

Default behavior:

- If `modules/<module>.yaml` already exists, fail.
- `--force` allows updating an existing module.
- `--backup` or `add_module.backup: true` creates timestamped backups before writing.
- `--dry-run`: execute the full flow (LLM calls, validation) but do not write to disk. Output the generated YAML contents and validation results to stdout so a human can review before committing.
- `--review`: write both files but set new/updated module's `metadata.generated_by` to include `[pending-review]` and append a review note. Feature `metadata.status` is unchanged (an `active` feature stays `active`). Human operator reviews and removes the marker.

Flow:

1. Validate paths:
   - Feature directory is under `features_dir`.
   - Module output path is `features/<feature>/modules/<module>.yaml`.
   - Module code path is under `repo_root`.
2. Read and validate current `feature.yaml`.
3. If module YAML exists and `--force` is not set, fail.
4. Run `module_generation` prompt.
5. Validate `ModuleGenerationResult`.
6. Parse and validate `module_yaml`.
7. Run `feature_update` prompt.
8. Validate `FeatureUpdateResult`.
9. Parse and validate `updated_feature_yaml`.
10. Run diff safety validation.
11. If all validations pass, write both files.
12. Output written files, summaries, warnings, and related feature suggestions.

Validation retries:

- If LLM structured output, YAML parsing, schema validation, or business validation fails, feed the validation error back to the LLM.
- Retry up to `llm.max_validation_retries`.
- If retries are exhausted, return non-zero and write nothing.

Write transaction:

- Generate all content first.
- Validate all content.
- Optionally create backups.
- Write temporary files.
- Atomically replace target files where supported.
- Avoid leaving a half-updated feature directory.

Diff safety validation for `feature.yaml`:

Allowed changes:

- Append a new module index.
- Append call-chain steps.
- Append `failure_patterns[].related_steps`.
- Append `failure_patterns[].key_logs`.
- Append `failure_patterns[].possible_causes`.
- Set `metadata.version` to old version + 1.
- Set `metadata.updated_at` to current update time.
- Append `metadata.review_notes`.

Disallowed changes:

- Delete or rewrite existing modules.
- Delete or rewrite existing call-chain steps.
- Delete or rewrite existing failure patterns.
- Modify `name`, `display_name`, `description`, or `keywords`.
- Modify existing key logs or possible causes.
- Modify existing `metadata.owner` or `metadata.status`.

`--force` still does not allow arbitrary feature rewrites. It only allows overwriting the existing module YAML and, if needed, updating that module index responsibility.

## 13. Prompts

Prompt files:

```text
prompts/
  module_generation.md
  feature_update.md
```

Template rules:

- Use simple placeholders such as `{{feature_yaml}}`.
- Missing variables are errors.
- No Jinja or conditional syntax in MVP.
- Prompt instructions are Chinese.
- YAML and JSON field names are English.
- Code identifiers, paths, log tags, log patterns, and symbols must not be translated.

Template variables (all prompts):

| Variable | Source | Available in |
| --- | --- | --- |
| `{{module_code_path}}` | CLI `--path` argument | `module_generation.md` |
| `{{feature_yaml}}` | `FeatureStore` read of current `feature.yaml` (serialized as YAML string) | `module_generation.md`, `feature_update.md` |
| `{{module_name}}` | CLI `--module` argument | `module_generation.md`, `feature_update.md` |
| `{{feature_name}}` | CLI `--feature` argument | `feature_update.md` |
| `{{tool_results}}` | ReAct loop: all tool call returns serialized as structured JSON | `module_generation.md` (bounded ReAct mode) |

Tool results are injected into a dedicated `{{tool_results}}` placeholder as a JSON array of `{tool_name, result}` entries. Tool output is summarized if it exceeds `max_code_snippets_for_llm` items.

### module_generation.md

The module generation prompt instructs the LLM to:

1. List important files under `{{module_code_path}}`.
2. Search log macros, log tags, and ERROR/WARN logs.
3. Search classes, structs, interfaces, public methods, and entrypoints.
4. Read relevant file snippets.
5. Summarize module responsibility, symbols, logs, candidate steps, failure signals, and dependencies.
6. Output JSON:

```json
{
  "module_yaml": "string",
  "analysis_summary": ["string"],
  "warnings": ["string"]
}
```

The generated `module_yaml` must match `ModuleYaml`.

### feature_update.md

The feature update prompt instructs the LLM to:

1. Append the new module index.
2. Optionally append new call-chain steps based on module candidate steps.
3. Optionally append failure key logs based on module failure signals.
4. Increment `metadata.version`.
5. Update `metadata.updated_at`.
6. Append review notes when placement or matching is uncertain.
7. Output JSON:

```json
{
  "updated_feature_yaml": "string",
  "change_summary": ["string"],
  "warnings": ["string"],
  "related_feature_suggestions": [
    {
      "feature": "string",
      "reason": "string"
    }
  ]
}
```

The generated `updated_feature_yaml` must match `FeatureYaml` and pass diff safety validation.

## 14. Structured Output Models

LLM output models:

```python
class ModuleGenerationResult(BaseModel):
    module_yaml: str
    analysis_summary: list[str]
    warnings: list[str]

class RelatedFeatureSuggestion(BaseModel):
    feature: str
    reason: str

class FeatureUpdateResult(BaseModel):
    updated_feature_yaml: str
    change_summary: list[str]
    warnings: list[str]
    related_feature_suggestions: list[RelatedFeatureSuggestion]
```

CLI result models:

```python
class WrittenFile(BaseModel):
    path: str
    action: Literal["created", "updated", "backup_created"]

class AddModuleResult(BaseModel):
    command: Literal["add-module"] = "add-module"
    feature: str
    module: str
    written_files: list[WrittenFile]
    analysis_summary: list[str]
    change_summary: list[str]
    warnings: list[str]
    related_feature_suggestions: list[RelatedFeatureSuggestion]
```

`LogSource` (shared, optional — appears in logs and failure_signals):

```python
class LogSource(BaseModel):
    file: Optional[str] = None
    line: Optional[int] = None   # >= 1 if present
    symbol: Optional[str] = None
```

`AnalysisStats`:

```python
class AnalysisStats(BaseModel):
    total_lines: int              # total lines across all log inputs
    parsed_lines: int             # successfully parsed hilog lines
    unparsed_lines: int           # lines that failed parsing
    in_window_lines: int          # parsed lines within the time window
    time_span_seconds: float      # actual time span of events in window
    tags_distribution: dict[str, int]  # log tag → count within window
```

`AnalysisResult`:

```python
class AnalysisResult(BaseModel):
    command: Literal["analyze-log"] = "analyze-log"
    feature: str
    chain: Optional[str] = None
    expanded_chains: list[str] = []  # chain names expanded (all when --top-n-chains)
    question: Optional[str] = None
    conclusion: Conclusion
    root_causes: list[RootCause]
    chain_status: list[ChainStepStatus]
    cross_chain_correlation: list[CrossChainCorrelation] = []
    evidence: list[Evidence]
    stats: AnalysisStats
    supplemental_suggestions: list[str] = []
    warnings: list[str] = []
```

`root_causes[].supporting_evidence` and `chain_status[].evidence` must reference existing evidence ids.

Config models use `pydantic.SecretStr` for `api_key` — the `str()` and `repr()` representations are redacted, preventing exposure in tracebacks, debug logs, and verbose output.

MVP JSON output does not include `schema_version`.

## 15. Error Handling

| Scenario | Handling |
| --- | --- |
| Feature not found | Show available features |
| Feature YAML invalid | Show validation errors |
| Module YAML invalid | Show validation errors |
| Module exists without `--force` | Fail and suggest `--force` |
| Regex compile failure | Schema error |
| Log path missing | Fail |
| Zip unpack failure | Fail |
| Time format invalid | Show expected format |
| No logs in window | Suggest widening window |
| Feature auto-match ambiguous | Output Top 3 candidates with scores, exit code 2 (`EXIT_FEATURE_AMBIGUOUS`). User re-runs with `--feature`. |
| LLM output invalid | Retry up to 3 times |
| `ask` LLM retries exhausted | Fall back to deterministic summary |
| `analyze-log` LLM retries exhausted | Fall back to rule result |
| `add-module` LLM retries exhausted | Fail and write nothing |
| Template variable missing | Fail with error listing the missing variable name |
| `--log` glob matches zero files | Fail with "no log files found matching pattern" |
| Module YAML empty symbols/logs/candidate_steps/failure_signals without review notes | Warn; proceed (accept valid but incomplete knowledge) |

## 16. Testing Strategy

Use focused unit tests plus fixture-level CLI e2e tests.

Unit tests:

- Config precedence and API key redaction
- Feature directory scanning
- Feature and module schema validation
- Cross-file feature directory validation
- Regex compile validation
- Path format validation
- Hilog parsing and unparsed line accounting
- Time-window filtering
- Substring and regex matching
- Feature and chain scoring
- Evidence generation
- Chain status inference
- LLM structured output validation and retry
- `add-module` diff safety validation
- `add-module` write transaction behavior

CLI e2e tests:

- `ask --feature`
- `ask` with feature auto-match (successful auto-pick and ambiguous exit code 2)
- `ask --interactive`
- `analyze-log` text output
- `analyze-log --json`
- `analyze-log --top-n-chains 3`
- `analyze-log --chain <name>`
- `analyze-log --window-before 120 --window-after 30`
- `analyze-log --log "logs/*.hilog"` (multi-file glob)
- `add-module` creates module YAML and updates feature YAML
- `add-module` existing module fails without `--force`
- `add-module --force`
- `add-module --backup`
- `add-module --dry-run` (validates but writes nothing)
- `add-module --review` (writes with review marker)

## 17. Implementation Order

Each step includes its corresponding unit tests written immediately after, before moving to the next step. Tests are not deferred to the end.

1. Define Pydantic v2 schemas → write schema validation unit tests.
2. Implement config loading (incl. `SecretStr` for `api_key`, config precedence) → write config unit tests.
3. Implement FeatureStore and feature directory validation → write FeatureStore unit tests.
4. Implement hilog parser, time filtering (asymmetric window support), and pattern matcher → write parser/filter/matcher unit tests.
5. Implement evidence builder and scoring (all configurable weights) → write scoring unit tests.
6. Implement text and JSON renderers (incl. verbose scoring breakdown format).
7. Implement LLM client and structured output validation (with retry loop) → write LLM validation unit tests.
8. Add prompt loading and placeholder rendering (all template variables per Section 13 table).
9. Implement `ask` (deterministic + feature auto-match with exit code 2) → write `ask` e2e tests.
10. Implement `analyze-log` (multi-log, asymmetric window, `--chain`, `--top-n-chains`, cross-chain correlation) → write `analyze-log` e2e tests.
11. Implement `add-module` module generation (incl. `--dry-run`, `--review`) → write `add-module` e2e tests.
12. Implement `add-module` feature update.
13. Implement diff safety validation and write transaction → write diff safety and write transaction unit tests.
14. Add remaining fixture-level CLI e2e tests for edge cases.

## 18. Future Work

- `remove-module`
- Cross-feature automatic updates
- Deeper code search across existing feature modules
- Call graph and symbol graph analysis
- Vector retrieval
- Web UI
- IDE integration
- Issue tracker and build system integration
