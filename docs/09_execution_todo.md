# GraphAgentAutomated Top-tier Execution TODO

执行模式：自主推进，完成后统一交付。  
状态标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 完成。

## Global Definition of Done

1. 每个 Phase 都有 `目标 -> 方法 -> 产出 -> 验收标准`。  
2. 关键模块必须有单元测试，关键链路必须有集成测试。  
3. 所有结论必须落到文档和可复现脚本。  
4. 在无真实 key 条件下，以 mock-first 强验证完成机制证明。

---

## Phase 0: Charter Lock

- 状态：`[x]`
- 产出：`docs/10_research_charter.md`
- 验收：H1/H2/H3、阈值、红线已定义。

## Phase 1: Problem & Claims

- 状态：`[x]`
- 产出：`docs/11_problem_and_claims.md`
- 验收：贡献可证伪、对应 ablation 与反证条件。

## Phase 2: Method Blueprint

- 状态：`[x]`
- 产出：`docs/12_method_blueprint.md`
- 验收：目标函数、伪代码、复杂度、uncertainty 机制完整。

## Phase 3: System Architecture V2

- 状态：`[x]`
- 产出：
  - `docs/13_system_arch_v2.md`
  - 代码：run-level 追踪、registry、artifact 回放
- 验收：`optimization_runs` / `optimization_round_traces` / `agent_versions.run_id` 生效。

## Phase 4: Data Synthesis V2

- 状态：`[x]`
- 产出：
  - `docs/14_synthesis_protocol.md`
  - 代码：split、hard-negative、lineage、report
- 验收：`DynamicDatasetSynthesizer` 支持 train/val/test。

## Phase 5: Prompt Optimization V2

- 状态：`[x]`
- 产出：
  - `docs/15_prompt_optimization_protocol.md`
  - 代码：candidate generation + scoring + registry
- 验收：`PromptVariantRegistry` 可记录并输出 artifact。

## Phase 6: Tool Policy V2

- 状态：`[x]`
- 产出：
  - `docs/16_tool_mapping_and_policy.md`
  - 代码：capability mapping + historical gain
- 验收：工具选择可解释，round trace 可回溯。

## Phase 7: Judge Reliability V2

- 状态：`[x]`
- 产出：
  - `docs/17_judge_reliability.md`
  - 代码：multi-judge + agreement + confidence
- 验收：`EvaluationSummary` 包含 `judge_agreement/score_std/split`。

## Phase 8: Search & Convergence V2

- 状态：`[x]`
- 产出：
  - `docs/18_search_and_convergence.md`
  - 代码：holdout 选择、早停、regret 追踪
- 验收：`SearchRoundTrace` 全链路持久化与 artifact 化。

## Phase 9: Mock-first Strong Validation

- 状态：`[x]`
- 产出：
  - `docs/19_mock_validation_report.md`
  - 测试：属性/变形/对抗样例
- 验收：`pytest` 全绿、coverage 与迁移测试通过。

## Phase 10: Real Experiment Protocol (Ready-to-run)

- 状态：`[x]`
- 产出：
  - `docs/20_real_experiment_plan.md`
  - `scripts/run_experiment_matrix.py`
- 验收：baseline/ablation matrix、统计流程、runbook 固定。

## Phase 11: Paper Package

- 状态：`[x]`
- 产出：`docs/21_paper_package.md`
- 验收：投稿清单、工件清单、风险审查齐全。

---

## Evidence Index

1. 核心实现：`src/graph_agent_automated/application/services.py`、`src/graph_agent_automated/infrastructure/optimization/search_engine.py`、`src/graph_agent_automated/infrastructure/evaluation/judges.py`。  
2. 持久化与迁移：`src/graph_agent_automated/infrastructure/persistence/models.py`、`alembic/versions/0002_add_optimization_run_tables.py`。  
3. 测试：`tests/unit/test_search_engine.py`、`tests/unit/test_mock_validation.py`、`tests/integration/test_api.py`。  
4. 实验脚本：`scripts/run_experiment_matrix.py`。
