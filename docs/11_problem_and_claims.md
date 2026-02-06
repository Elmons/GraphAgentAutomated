# Phase 1: Problem & Claims

版本：v1.0  
日期：2026-02-07

## 1. 问题定义

给定用户请求 `u`（图任务描述）与外部运行时 `R`（chat2graph SDK），目标是在有限预算 `B` 内自动生成可部署智能体版本 `a*`，使其在动态构造的评估分布上性能最优：

- 联合优化对象：`prompt + tool policy + topology`
- 评估信号：`LLM-as-a-Judge + 反思反馈`
- 约束：`chat2graph` 仅作为外置 runtime，不改其内部实现。

形式化目标：

`a* = argmax_a U(a | D_train(u), D_val(u))`, 其中 `U` 同时考虑质量、延迟、成本、复杂度与不确定性。

## 2. 关键难点

1. 请求分布漂移：静态评估集无法覆盖在线任务变化。
2. 搜索空间爆炸：prompt、工具组合、拓扑结构相互耦合。
3. 评估噪声：单一 judge 易偏置，奖励信号不稳定。
4. 工程可复现性：需要 run 级别追踪、可回放、可回滚。

## 3. 可投稿贡献声明（Claims）

## C1. Dynamic Synthesis as Online Evaluator

- 声明：按请求动态合成的小评估集（含 hard-negative 与 split）能更稳定驱动优化。
- 可证伪条件：在固定预算下，holdout（val/test）无显著提升或方差更高。

## C2. Joint Search over Prompt-Tool-Topology

- 声明：联合搜索优于仅 prompt 优化。
- 可证伪条件：在主指标、稳定性或成本效率上不优于 prompt-only baseline。

## C3. Reliability-aware Judge Loop

- 声明：多裁判加权与一致性建模可降低“虚高候选”被选概率。
- 可证伪条件：引入 ensemble 后，judge agreement 与泛化性能无提升。

## C4. Holdout-guided Convergence Control

- 声明：训练驱动搜索 + 验证选择 + 早停 + regret 追踪可减少搜索漂移。
- 可证伪条件：与无 holdout 的 MCTS 变体相比，test 性能/稳定性无优势。

## C5. Reproducible AgentOps for Workflow Search

- 声明：run-level artifact + 关系型追踪可显著提升复现实验效率。
- 可证伪条件：无法复现关键结果，或 round 轨迹不能支持误差归因。

## 4. 与 AFlow 的关系

- 继承：AFlow 将工作流优化建模为代码空间搜索（MCTS）并报告了跨任务收益。
- 深化：本系统把 AFlow 思想迁移到图数据库 Agent 场景，并新增：
  - 动态数据合成（按请求）
  - split-aware 选择策略（train/val/test）
  - judge reliability 信号（agreement/confidence）
  - run-level 追踪与版本治理（DB + artifacts）

## 5. 主要风险与应对

1. 评估偏置风险：采用多裁判、置信度、人工 spot-check 协同。
2. 过拟合小样本风险：显式 val/test holdout 与多种子复现实验。
3. 搜索成本风险：早停、预算控制、阶段性回退。

## 6. Phase 1 Gate

通过标准：

1. 每个 claim 均有可证伪实验。  
2. claim 能映射到代码模块与测试证据。  
3. 与 AFlow 的“继承-创新”关系清晰。

Gate 结论：`PASS`。
