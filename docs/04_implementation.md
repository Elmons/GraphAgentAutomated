# GraphAgentAutomated 系统实现说明

## 1. 当前实现范围

本版本已实现以下能力：

1. 动态评估数据合成（schema-grounded）。
2. prompt/tool/topology 联合搜索（AFlowX, MCTS 风格）。
3. LLM 评估抽象（mock/openai judge）。
4. agent 版本管理（sqlite + SQLAlchemy + Alembic）。
5. FastAPI 接口（优化、版本查询、发布、回滚、健康检查）。
6. chat2graph 运行时适配（mock + 外部 SDK 适配器）。

---

## 2. 代码结构

```text
src/graph_agent_automated/
  api/
    routers/
      agents.py
      health.py
    schemas.py
    dependencies.py
  application/
    services.py
  core/
    config.py
    database.py
  domain/
    enums.py
    models.py
    protocols.py
  infrastructure/
    synthesis/dynamic_synthesizer.py
    optimization/{search_engine.py,prompt_optimizer.py,tool_selector.py}
    evaluation/{judges.py,workflow_evaluator.py}
    runtime/{mock_runtime.py,chat2graph_sdk_runtime.py,yaml_renderer.py}
    persistence/{models.py,repositories.py}
  main.py
```

---

## 3. 关键实现点

### 3.1 动态数据合成

- 文件：`src/graph_agent_automated/infrastructure/synthesis/dynamic_synthesizer.py`
- 逻辑：任务意图识别 -> schema 模板渲染 -> paraphrase -> 去重 -> 小样本集输出。

### 3.2 搜索优化引擎

- 文件：`src/graph_agent_automated/infrastructure/optimization/search_engine.py`
- 逻辑：
  1. UCB 选择候选。
  2. 三类 mutation（prompt/tool/topology）。
  3. 评估后 backpropagate。
  4. `min_improvement + patience` 早停。

### 3.3 评估与反思

- 文件：
  - `src/graph_agent_automated/infrastructure/evaluation/judges.py`
  - `src/graph_agent_automated/infrastructure/evaluation/workflow_evaluator.py`
- 支持：
  - `HeuristicJudge`（无 key 本地可跑）
  - `OpenAIJudge`（在线 LLM 评分）
- 评估结果包含 case-level rationale 与 reflection。

### 3.4 Agent 管理

- 文件：
  - `src/graph_agent_automated/infrastructure/persistence/models.py`
  - `src/graph_agent_automated/infrastructure/persistence/repositories.py`
- 数据表：
  - `agents`
  - `agent_versions`
  - `evaluation_cases`

### 3.5 Runtime 适配

- `MockRuntimeAdapter`：本地 deterministic 执行。
- `Chat2GraphSDKRuntimeAdapter`：外部加载 chat2graph SDK（仅调用，不改内核）。
- `Chat2GraphYamlRenderer`：渲染 chat2graph 兼容 workflow yaml。

### 3.6 API

- 文件：`src/graph_agent_automated/api/routers/agents.py`
- 路径：
  - `POST /v1/agents/optimize`
  - `GET /v1/agents/{agent_name}/versions`
  - `POST /v1/agents/{agent_name}/versions/{version}/deploy`
  - `POST /v1/agents/{agent_name}/versions/{version}/rollback`

---

## 4. 数据库迁移

- Alembic 配置：`alembic.ini`, `alembic/env.py`
- 初始迁移：`alembic/versions/0001_init_schema.py`

执行：

```bash
uv run alembic upgrade head
```

---

## 5. 运行方式

1. 同步依赖：

```bash
uv sync --all-groups
```

2. 启动服务：

```bash
uv run uvicorn graph_agent_automated.main:app --reload --port 8008
```

3. 执行测试：

```bash
uv run pytest
uv run pytest --cov=src/graph_agent_automated --cov-report=term-missing
```

---

## 6. 已验证结果

在 mock runtime 下，已通过：

1. 单元测试（合成/评估/搜索/渲染/仓储）。
2. 集成测试（API 优化->发布->回滚全链路）。
3. lint 检查（ruff）。
