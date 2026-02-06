# Phase 0 Charter Lock

版本：v0.1  
日期：2026-02-07

## 1. 目标赛道与问题陈述

## 1.1 目标赛道
- 主目标：顶会 Systems/Agents/DB+AI 方向（强调方法创新 + 可信评估 + 可复现系统）。

## 1.2 问题陈述（一句话）
- 在图数据库智能体自动生成中，如何在**动态任务分布**下稳定优化 `prompt + tool policy + agent topology`，并通过**可靠的 LLM 评估闭环**获得可部署改进，而不是过拟合到静态评测集。

## 1.3 边界
- 本项目聚焦图任务（query/analytics/modeling/import/qa）。
- chat2graph 只作为外部 runtime，不改内核。
- 先以 mock-first 验证机制正确性，再进入真实 key 实验。

---

## 2. 可证伪核心假设（Falsifiable Hypotheses）

## H1: Dynamic Dataset Co-evolution
- 假设：按请求动态生成的 schema-grounded 评估集 + 搜索协同优化，能显著优于静态评估集驱动优化。
- 反证条件：在同预算下，动态方案在 holdout 上无显著提升，或更不稳定。

## H2: Joint Optimization Beats Single-axis Tuning
- 假设：联合优化（prompt + tool + topology）优于仅优化 prompt。
- 反证条件：联合优化在主指标上不优于 prompt-only，且成本明显更高。

## H3: Judge Reliability Controls Search Drift
- 假设：多裁判与校准机制可降低搜索漂移，减少“虚高候选”被选中的概率。
- 反证条件：加入 reliability 机制后，稳定性和泛化均无改善，或引入额外偏差。

---

## 3. 成功标准（量化）

## 3.1 质量指标
- 主指标：Task Success / Judge Score（以 holdout 为准）。
- 成功阈值：相对最强 baseline 提升 >= 10%。

## 3.2 成本与效率
- 平均 token 成本增幅 <= 25%。
- 平均延迟增幅 <= 20%。

## 3.3 稳定性
- 不同随机种子重复实验，主指标方差较 baseline 下降 >= 20%。
- 失败样本中“无证据幻觉”占比下降 >= 30%。

## 3.4 可信性
- judge 一致性（inter-judge agreement）达到预设阈值（后续在 Phase 7 固化）。
- 关键结论在至少 3 个任务簇上成立。

---

## 4. 实验与论证红线

1. 不以单次跑分结论支撑论文。  
2. 不以开发集结果替代 holdout 结果。  
3. 不只报均值，必须报方差与置信区间。  
4. 每个贡献点必须有对应 ablation。  
5. 负结果必须进入正文分析。

---

## 5. Phase 0 输出与 Gate

已输出：
- 目标赛道与问题边界
- H1/H2/H3 可证伪假设
- 定量成功阈值
- 红线规则

`GATE-P0`: 已冻结并进入 Phase 1~11 执行。
