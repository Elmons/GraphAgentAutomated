# Phase 11: Paper Package

版本：v1.0  
日期：2026-02-07

## 1. 论文结构建议

1. Introduction: 图数据库 agent workflow 自动优化问题
2. Related Work: AFlow, data synthesis, LLM judge, graph-agent systems
3. Method: Dynamic synthesis + joint search + reliability-aware evaluation
4. System: runtime-decoupled architecture + run-level trace
5. Experiments: baselines/ablations/significance
6. Analysis: convergence, failure cases, judge reliability
7. Limitations & Ethics

## 2. 必备图表

1. 系统架构图
2. 搜索流程图（带 holdout 与 early-stop）
3. Round-wise val/test 曲线 + regret 曲线
4. Judge agreement vs final quality 相关图
5. 成本-质量 Pareto 图

## 3. 核心表格

1. 主结果表（各任务簇）
2. 消融表（每个 claim 对应）
3. 稳定性表（多 seed 方差）
4. 失败案例分析表

## 4. Artifact 包

1. 代码仓（含 migration、tests）
2. 运行脚本与配置模板
3. 关键 run artifacts（dataset/prompt variants/traces）
4. 复现实验说明

## 5. 风险审查

1. 是否只在 mock 结果上做结论：禁止。  
2. 是否存在评估闭环偏置：必须在正文显式披露。  
3. 是否缺少负结果：必须保留。

## 6. 投稿清单

1. Reproducibility checklist
2. Compute budget disclosure
3. Prompt/judge template disclosure
4. Statistical testing appendix
5. Failure case appendix

## 7. 当前完成度

- 方法与系统原型：已完成。  
- mock-first 机制验证：已完成。  
- 真实 key 实验：待执行（按 `docs/20_real_experiment_plan.md`）。

## 8. Phase 11 Gate

- 投稿材料结构与工件清单完整。  
Gate 结论：`PASS`。
