# GraphAgentAutomated Master TODO (Must-read)

最后更新：2026-02-06  
状态标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 完成。

## 0. 新会话强制流程（所有新 Codex 必须执行）

1. 先读本文件：`docs/09_execution_todo.md`。  
2. 再读会话指引：`docs/24_codex_session_guide.md`。  
3. 运行最小检查：`git status --short`、`./.venv/bin/pytest -q`。  
4. 在开始改代码前，先在回复中明确：当前目标、已完成、未完成、下一步计划。  
5. 若发现本文件与代码不一致，先更新本文件再继续开发。

## 1. 终极目标（Research-first）

1. 主目标（当前唯一优先级）：通过自然语言自动生成图数据库智能体，并在真实评测中达到或接近人工精心设计方案（parity）。  
2. 研究目标：形成可证伪、可复现、可投稿的核心 idea 与实验结论。  
3. 工程目标（次级）：仅建设支撑研究可信性的最小工程能力；生产级目标暂不作为当前迭代 gate。

## 2. 当前真实状态快照（不要自欺）

1. 研究原型主链路可运行（含 profile 矩阵、manual parity、异步与幂等能力）。  
2. 算法层面尚无“足够”证据：当前结论主要来自 mock 和有限任务，不能证明在真实任务簇中稳定达到人工 parity。  
3. 当前短板不在“能不能跑”，而在“研究证据是否足够强”：任务冻结、失败分型、统计显著性、idea 增益曲线仍未闭环。  
4. 结论：当前是“可迭代研究原型”，不是“算法已定型”。

## 3. 已完成里程碑

## P0-P12（研究主线）

- 状态：`[x]`
- 产出文档：
  - `docs/10_research_charter.md`
  - `docs/11_problem_and_claims.md`
  - `docs/12_method_blueprint.md`
  - `docs/13_system_arch_v2.md`
  - `docs/14_synthesis_protocol.md`
  - `docs/15_prompt_optimization_protocol.md`
  - `docs/16_tool_mapping_and_policy.md`
  - `docs/17_judge_reliability.md`
  - `docs/18_search_and_convergence.md`
  - `docs/19_mock_validation_report.md`
  - `docs/20_real_experiment_plan.md`
  - `docs/21_paper_package.md`
  - `docs/22_top_conf_idea_rcds.md`
- 核心代码：
  - `src/graph_agent_automated/infrastructure/optimization/search_engine.py`
  - `src/graph_agent_automated/application/services.py`
  - `src/graph_agent_automated/infrastructure/evaluation/judges.py`
  - `scripts/run_experiment_matrix.py`

## P13（生产对标轨）

- 状态：`[~]`
- 已完成：
  - `manual parity` 接口：`/v1/agents/benchmark/manual-parity`
  - 人工蓝图加载器：`src/graph_agent_automated/infrastructure/runtime/workflow_loader.py`
  - parity 批跑脚本：`scripts/run_manual_parity_matrix.py`
  - 规划文档：`docs/23_production_readiness.md`
- 未完成：
  - 真实 runtime 非 mock 回归闭环
  - 生产级安全与可靠性改造

## 4. 剩余工作（按优先级）

## R0 研究主线（最高优先级，当前必须先做）

- 状态：`[x]` 冻结真实任务簇与人工蓝图集（Research Benchmark Freeze）  
  - 已完成：`docs/benchmarks/research_benchmark_v1.json`（12 任务，四类各 >= 3，含 `default_seeds`）与 `docs/manual_blueprints/research_benchmark_v1/` 人工蓝图集；实验脚本默认读取该冻结基准并默认使用 benchmark seeds。

- 状态：`[ ]` 跑通真实 runtime + 真实 judge 的 parity 主实验  
验收：`full_system` vs `manual` 在冻结任务集上完成多 seed 评测，输出可复现实验工件与统计显著性。

- 状态：`[ ]` 建立 failure taxonomy（不是只看均分）  
验收：把失败切分为 tool selection / decomposition / execution grounding / verifier mismatch 等类型，并产出占比与严重度。

- 状态：`[ ]` 形成 research idea backlog（至少 3 个可证伪假设）并做小步 ablation  
验收：每个 idea 都有“动机-机制-可证伪条件-最小实验”，至少完成 1 个 idea 的端到端实现与对照实验。

- 状态：`[ ]` 明确“算法够不够”的停机准则  
验收：定义并固化 research gate（例如 parity rate、方差、最差分位、成本约束），避免主观判断“看起来差不多”。

## R1 支撑研究可信性的工程项（次优先级）

- 状态：`[x]` 鉴权与多租户隔离（API key/JWT + RBAC）  
- 状态：`[~]` 长任务队列化（异步 optimize/parity）  
  - 已完成：异步提交接口与状态查询。  
  - 未完成：持久化队列与跨进程 worker。
- 状态：`[~]` 幂等键与去重机制  
  - 已完成：`Idempotency-Key` 接入同步/异步提交。  
  - 未完成：持久化幂等存储与 TTL 回收。
- 状态：`[~]` 结构化日志 + 指标  
  - 已完成：HTTP JSON 日志与 `/metrics`。  
  - 未完成：外部指标后端与告警。
- 状态：`[~]` artifact 生命周期管理  
  - 已完成：清理策略脚本（retention + keep latest）。  
  - 未完成：归档分层与自动调度。

## 5. 完成定义（Research-ready DoD）

必须同时满足：

1. R0 全部完成，并有可复现实验工件。  
2. 在冻结任务簇上，自动方案达到预设 parity gate（含均值、方差、最差分位）。  
3. 至少 1 个核心 idea 通过对照实验被支持或被证伪，并形成可写作叙事。  
4. `docs/09_execution_todo.md` 与代码状态一致。  
5. 每次会话结束写入“本次完成/剩余阻塞/下一步”。

## 6. 每次会话结束的最小更新模板

1. 本次完成了什么（文件 + 验证命令 + 结果）。  
2. 当前仍阻塞什么（按 R0/R1）。  
3. 下一会话第一步做什么。  
4. 若目标或优先级变化，必须更新本文件。

## 7. 证据索引

1. 核心实现：`src/graph_agent_automated/application/services.py`、`src/graph_agent_automated/infrastructure/optimization/search_engine.py`、`src/graph_agent_automated/infrastructure/runtime/workflow_loader.py`。  
2. API：`src/graph_agent_automated/api/routers/agents.py`、`src/graph_agent_automated/api/schemas.py`。  
3. 测试：`tests/integration/test_api.py`、`tests/unit/test_search_engine.py`、`tests/unit/test_workflow_loader.py`。  
4. 脚本：`scripts/run_experiment_matrix.py`、`scripts/run_manual_parity_matrix.py`。
