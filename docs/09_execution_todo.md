# GraphAgentAutomated Master TODO (Must-read)

最后更新：2026-02-06  
状态标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 完成。

## 0. 新会话强制流程（所有新 Codex 必须执行）

1. 先读本文件：`docs/09_execution_todo.md`。  
2. 再读会话指引：`docs/24_codex_session_guide.md`。  
3. 运行最小检查：`git status --short`、`./.venv/bin/pytest -q`。  
4. 在开始改代码前，先在回复中明确：当前目标、已完成、未完成、下一步计划。  
5. 若发现本文件与代码不一致，先更新本文件再继续开发。

## 1. 终极目标（不变）

1. 研究目标：产出可投稿顶会的、可证伪的核心 idea。  
2. 工程目标：仓库达到生产级，能从自然语言自动生成图数据库智能体。  
3. 性能目标：自动生成智能体在真实评测下接近或达到人工设计水平（通过 parity protocol 验证）。

## 2. 当前真实状态快照（不要自欺）

1. 研究原型主链路已完成并可运行（含 profile 矩阵、manual parity 接口）。  
2. 现有自动化测试主要基于 mock，不能证明真实 runtime 下的生产可用性。  
3. 生产级关键能力（鉴权、队列、可靠性治理、SLO、真实回归）尚未完成。  
4. 结论：当前是“强研究原型”，不是“已达生产级”。

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

## P0 必须先做（阻塞生产判断）

- 状态：`[x]` 修复 manual parity 路径输入安全  
验收：禁止任意本地路径读取，限制在受控目录或改成文件上传。

- 状态：`[x]` 修复 manual parity 事务语义  
验收：人工蓝图校验失败时，不留下已落库的自动优化版本。

- 状态：`[x]` 修复 tool mutation 状态一致性 bug  
验收：`tool:remove(...)` 时同步更新 `blueprint.tools` 与 action/operator 引用。

- 状态：`[x]` 补齐 SDK runtime timeout/retry/circuit breaker  
验收：外部运行失败可控，错误分类清晰，不会拖垮服务。

## P1 生产化基础

- 状态：`[ ]` 鉴权与多租户隔离（API key/JWT + RBAC）  
- 状态：`[ ]` 长任务队列化（异步 optimize/parity）  
- 状态：`[ ]` 幂等键与去重机制  
- 状态：`[ ]` 结构化日志 + 指标 + 告警（延迟/错误率/成本/parity rate）  
- 状态：`[ ]` artifact 生命周期管理（清理策略/归档策略）

## P2 真实性验证（必须发生在宣称生产级之前）

- 状态：`[ ]` 非 mock 真值评测数据集与任务簇冻结  
- 状态：`[ ]` 真实 chat2graph runtime + 真实 judge 回归 pipeline  
- 状态：`[ ]` 自动 vs 人工 parity 报告（多任务、多种子、显著性分析）  
- 状态：`[ ]` 发布门槛固化（示例：parity_achieved rate >= 70%）

## 5. 完成定义（Production-ready DoD）

必须同时满足：

1. P0 全部完成并有回归测试。  
2. P1 完成最小可上线集合（鉴权、队列、观测、幂等）。  
3. P2 在真实环境达标，且报告可复现。  
4. `docs/09_execution_todo.md` 与代码状态一致。  
5. 每次会话结束写入“本次完成/剩余阻塞/下一步”。

## 6. 每次会话结束的最小更新模板

1. 本次完成了什么（文件 + 验证命令 + 结果）。  
2. 当前仍阻塞什么（按 P0/P1/P2）。  
3. 下一会话第一步做什么。  
4. 若目标或优先级变化，必须更新本文件。

## 7. 证据索引

1. 核心实现：`src/graph_agent_automated/application/services.py`、`src/graph_agent_automated/infrastructure/optimization/search_engine.py`、`src/graph_agent_automated/infrastructure/runtime/workflow_loader.py`。  
2. API：`src/graph_agent_automated/api/routers/agents.py`、`src/graph_agent_automated/api/schemas.py`。  
3. 测试：`tests/integration/test_api.py`、`tests/unit/test_search_engine.py`、`tests/unit/test_workflow_loader.py`。  
4. 脚本：`scripts/run_experiment_matrix.py`、`scripts/run_manual_parity_matrix.py`。
