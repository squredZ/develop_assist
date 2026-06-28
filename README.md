# Hilog Agent

系统排障助手 — 基于结构化特征知识的 **feature Q&A**、**hilog 日志证据分析**、**LLM 辅助模块知识生成**。提供 CLI、REST API、ChatGPT 风格 GUI 三种交互方式。

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv .venv && source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate                              # Windows

# 2. 安装
pip install -e ".[dev]"

# 3. 配置 (可选 — 默认即可运行确定性功能)
cp fixtures/agent.yaml agent.yaml
# 编辑 agent.yaml, 填入 LLM API key 等信息

# 4. 运行
agent ask --question "拍照不出图可能是什么原因"
```

## 三种使用方式

### CLI 命令行

```bash
agent ask --feature camera_capture --question "拍照失败的原因"
agent analyze-log --log ./hilog.zip --time "2026-06-28 14:35" --window 60
agent add-module --feature camera_capture --module image_pipeline --path src/image_pipeline
```

### GUI 桌面应用 (ChatGPT 风格)

```bash
hilog-gui
# 或 python -m frontend.main
```

- 暗色主题、ChatGPT 风格聊天气泡
- SSE 流式输出：思考过程、工具调用、最终结果分别渲染
- 多轮对话，会话管理
- 拖拽日志文件到窗口进行分析

### REST API

```bash
uvicorn hilog_agent.server:app --host 127.0.0.1 --port 8710
```

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `POST` | `/api/chat/stream` | SSE 流式对话 (event: thinking / tool_call / tool_result / message / final_answer) |
| `POST` | `/api/ask` | 确定性问答 (无 LLM) |
| `POST` | `/api/analyze-log` | 日志分析 |
| `POST` | `/api/add-module` | 模块知识生成 |
| `GET` | `/api/features` | 列出特征 |
| `GET` | `/api/features/{name}` | 读取单个特征 |
| `GET` | `/api/sessions` | 会话列表 |
| `POST` | `/api/sessions/{id}/clear` | 清除会话 |

## 项目结构

```
src/hilog_agent/
├── models/              # Pydantic v2 数据模型
│   ├── feature.py       #   FeatureYaml, CallChain, FailurePattern...
│   ├── module.py        #   ModuleYaml, LogSource, CandidateStep...
│   ├── evidence.py      #   Evidence, ChainStepStatus, AnalysisStats
│   └── result.py        #   AnalysisResult, AskResult, AddModuleResult...
├── config.py            # agent.yaml 加载 + CLI 覆盖
├── store.py             # features/ 目录读写验证
├── scoring.py           # 证据构建、评分引擎
├── diff_safety.py       # feature.yaml 追加式安全校验
├── hilog/               # 日志解析与匹配
│   ├── parser.py        #   HilogEvent 解析
│   └── matcher.py       #   时间窗过滤 + 模式匹配
├── llm/                 # LLM 客户端 (OpenAI SDK)
│   ├── client.py        #   思考模式 + 流式输出
│   └── validator.py     #   结构化输出校验 + 重试
├── commands/            # 三个核心命令
│   ├── ask.py           #   特征问答
│   ├── analyze_log.py   #   日志证据分析
│   └── add_module.py    #   模块知识生成
├── renderers/           # text / JSON 输出
├── prompts/             # 提示词模板加载
├── orchestrator.py      # ReAct 循环 → SSE 事件流
├── server.py            # FastAPI 后端
└── cli.py               # Click CLI 入口

frontend/
├── chat.html            # ChatGPT 风格聊天界面
├── app.py               # PyQt QWebEngineView 窗口
└── main.py              # 应用启动器
```

## 特征知识存储

```yaml
# features/<name>/feature.yaml
name: camera_capture
display_name: 相机拍照
keywords: [拍照, capture]
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
call_chains:
  - name: normal_capture
    steps:
      - id: capture_request
        expected_logs: [...]
failure_patterns:
  - symptom: 拍照不出图
    key_logs: [...]
```

## 开发

```bash
# 运行测试
pytest tests/ -v

# 代码检查
ruff check src/ tests/
ruff format src/ tests/
mypy src/

# 打包 Windows .exe
pip install pyinstaller
pyinstaller build.spec
# → dist/HilogAgent.exe
```

## 配置参考

`agent.yaml` (CLI 参数 > 配置文件 > 默认值):

```yaml
repo_root: /path/to/source
features_dir: ./features

analysis:
  default_window_before_seconds: 60
  default_window_after_seconds: 60
  min_feature_score: 5

scoring:                    # 评分权重 (可调)
  keyword_hit_weight: 3
  continuous_step_bonus_per_step: 2
  missing_required_step_penalty: 5

llm:
  provider: openai_compatible
  base_url: https://api.openai.com/v1
  model: gpt-5.5
  reasoning:
    effort: medium          # 思考模式默认开启

orchestrator:
  max_tool_calls: 8         # ReAct 循环上限
  max_llm_rounds: 4
```
