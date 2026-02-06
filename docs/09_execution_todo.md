# GraphAgentAutomated Top-tier Execution TODO

执行模式：自主推进，完成后统一交付。  
状态标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 完成。

## Global Definition of Done

1. 每个 Phase 都有 `目标 -> 方法 -> 产出 -> 验收标准`。  
2. 关键模块必须有单元测试，关键链路必须有集成测试。  
3. 所有结论必须落到文档和可复现脚本。  
4. 本轮在无真实 key 条件下，以 mock-first 强验证完成机制证明。

---

## Phase 0: Charter Lock

- 状态：`[x]`
- 目标：冻结研究边界、核心假设、成功指标。
- 产出：
  - `docs/10_research_charter.md`
- 验收标准：
  - 有可证伪假设 H1/H2/H3
  - 有量化成功阈值
  - 有实验红线

## Phase 1: Problem & Claims

- 状态：`[~]`
- 目标：形成可投稿的问题定义与贡献叙事。
- 产出：
  - `docs/11_problem_and_claims.md`
- 验收标准：
  - 每条贡献可被独立 ablation 验证
  - 每条贡献都有反证条件

## Phase 2: Method Blueprint

- 状态：`[ ]`
- 目标：给出算法和机制蓝图（非口号式）。
- 产出：
  - `docs/12_method_blueprint.md`
- 验收标准：
  - 包含公式、伪代码、复杂度分析
  - 定义 objective 与 uncertainty 处理

## Phase 3: System Architecture V2

- 状态：`[ ]`
- 目标：把 baseline 升级到可复现研究系统。
- 产出：
  - `docs/13_system_arch_v2.md`
  - 代码：实验追踪、registry、可回放产物
- 验收标准：
  - 具备 run-level 追踪与可复现执行

## Phase 4: Data Synthesis V2

- 状态：`[ ]`
- 目标：动态合成从模板驱动升级为约束驱动。
- 产出：
  - `docs/14_synthesis_protocol.md`
  - 代码：难度控制、多样性控制、lineage、split
- 验收标准：
  - 支持 train/val/test 分割
  - 支持 hard-negative 与过滤报告

## Phase 5: Prompt Optimization V2

- 状态：`[ ]`
- 目标：把 prompt 优化做成可搜索策略，而非字符串拼接。
- 产出：
  - `docs/15_prompt_optimization_protocol.md`
  - 代码：prompt candidate 生成、registry、selection
- 验收标准：
  - prompt 版本化
  - 选择策略可解释、可回滚

## Phase 6: Tool Policy V2

- 状态：`[ ]`
- 目标：工具选择从关键词匹配升级为能力图谱+收益策略。
- 产出：
  - `docs/16_tool_mapping_and_policy.md`
  - 代码：chat2graph tool mapping + capability graph
- 验收标准：
  - 每次工具选择有证据链（匹配得分/历史收益）

## Phase 7: Judge Reliability V2

- 状态：`[ ]`
- 目标：提升 LLM-as-a-Judge 可信度。
- 产出：
  - `docs/17_judge_reliability.md`
  - 代码：multi-judge、agreement、confidence
- 验收标准：
  - 输出一致性指标与置信分数

## Phase 8: Search & Convergence V2

- 状态：`[ ]`
- 目标：给出工程收敛证据与漂移控制。
- 产出：
  - `docs/18_search_and_convergence.md`
  - 代码：holdout 选择、patience/min_improvement/regret 追踪
- 验收标准：
  - 搜索日志可视化（round-wise）
  - 早停条件可解释

## Phase 9: Mock-first Strong Validation

- 状态：`[ ]`
- 目标：无 key 条件下完成机制级可信验证。
- 产出：
  - `docs/19_mock_validation_report.md`
  - 测试：属性测试/变形测试/对抗测试
- 验收标准：
  - 覆盖关键机制与失败路径

## Phase 10: Real Experiment Protocol (Ready-to-run)

- 状态：`[ ]`
- 目标：为有 key 后真实实验提供可执行 protocol。
- 产出：
  - `docs/20_real_experiment_plan.md`
  - 脚本：benchmark runbook
- 验收标准：
  - baseline/ablation matrix 固定
  - 显著性检验流程固定

## Phase 11: Paper Package

- 状态：`[ ]`
- 目标：形成可投稿材料包。
- 产出：
  - `docs/21_paper_package.md`
  - 图表、artifact、复现说明
- 验收标准：
  - 有投稿清单与风险审查结论

---

## Execution Notes

- 不跳阶段，但实现上允许并行推进（文档与代码并行）。
- 每个 phase 完成后必须回填状态与证据链接。
