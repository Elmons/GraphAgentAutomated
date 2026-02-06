# Phase 3: System Architecture V2

版本：v1.0  
日期：2026-02-07

## 1. 架构原则

1. runtime 解耦：chat2graph 仅通过 adapter 调用。  
2. 开闭原则：优化策略、judge、runtime 可插拔。  
3. 可追踪：每次优化 run 都有完整 DB 记录与 artifact。  
4. mock-first：无 key 也可全链路验证。

## 2. 分层设计

- `api`: FastAPI 路由与 schema
- `application`: `AgentOptimizationService` 统一编排
- `domain`: 枚举、模型、协议（Protocol）
- `infrastructure`
  - `synthesis`: 动态数据合成
  - `optimization`: search/prompt/tool policy
  - `evaluation`: judge + evaluator
  - `runtime`: mock / chat2graph sdk adapter
  - `persistence`: SQLAlchemy repository + Alembic

## 3. 关键时序

1. `/v1/agents/optimize` 接收请求。
2. service 生成 `run_id`。
3. 合成 dataset（含 split/report）。
4. 拉取 runtime tool catalog，初始化 blueprint。
5. 搜索并评估，产出 best + traces + prompt variants。
6. 持久化：
   - optimization_runs
   - optimization_round_traces
   - agent_versions（关联 run_id）
7. 产物落盘：`dataset_report.json`、`round_traces.json`、`prompt_variants.json`、`run_summary.json`。

## 4. 持久化模型

- `agents`
- `agent_versions`
- `evaluation_cases`
- `optimization_runs`
- `optimization_round_traces`

迁移：`0001_init_schema.py` + `0002_add_optimization_run_tables.py`。

## 5. 工程化机制

1. 配置统一：`pydantic_settings`。  
2. 包管理：`uv`。  
3. 测试：`pytest + mock runtime`。  
4. 质量：`ruff`。  
5. DB 可切换：SQLite 本地验证，URL 可直接切换 PG。

## 6. 设计模式映射

- Strategy: prompt optimizer / tool selector / judge / runtime adapter
- Repository: 持久化边界
- Application Service: 编排事务与副作用
- Builder-like: initial blueprint construction

## 7. Phase 3 Gate

- run-level 可追踪；runtime 与优化器解耦；可回放产物完整。  
Gate 结论：`PASS`。
