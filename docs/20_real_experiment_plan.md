# Phase 10: Real Experiment Plan (Ready-to-run)

版本：v1.0  
日期：2026-02-07

## 1. 实验目标

验证本系统在真实 LLM + chat2graph runtime 上的泛化收益与成本边界。

## 2. 评测矩阵

## Baselines

1. Static dataset + prompt-only
2. Dynamic dataset + prompt-only
3. Dynamic dataset + prompt+tool
4. Full system（prompt+tool+topology+judge reliability）

## Ablations

1. -holdout（仅 train）
2. -ensemble judge（单 judge）
3. -hard-negative synthesis
4. -tool historical gain
5. -topology mutation

## Idea Arms

1. idea_failure_aware_mutation（失败分型驱动 mutation 调度）

## 3. 任务集

- Query-heavy
- Analytics-heavy
- Hybrid planning
- Schema/modeling

每类至少 3 个任务簇，固定随机种子（例如 5 seeds）。
冻结基准文件：`docs/benchmarks/research_benchmark_v1.json`。
对应人工蓝图：`docs/manual_blueprints/research_benchmark_v1/`。
固定 seeds 由 benchmark 的 `default_seeds` 提供（脚本默认使用）。

## 4. 指标

1. 质量：mean judge score / task success
2. 稳定性：score variance, judge agreement
3. 成本：token cost, latency
4. 搜索效率：rounds-to-best, regret slope

## 5. 统计检验

1. 主指标使用配对 bootstrap CI。  
2. 显著性：Wilcoxon signed-rank（非参数）。  
3. 报告效应量：Cliff's delta。

## 6. 运行工件

- `scripts/run_experiment_matrix.py`：执行实验矩阵与结果汇总。
- 推荐参数：`--benchmark-path docs/benchmarks/research_benchmark_v1.json`
- 基线：默认运行；消融：使用 `--include-ablations`；idea 对照：`--include-idea-arms`。
- `scripts/analyze_experiment_arms.py`：对 `full_system` 与目标 arm 做配对统计对照。
- `artifacts/experiments/<date>/`：原始 run 与聚合统计。
- `scripts/run_manual_parity_matrix.py`：执行 `full_system` vs `manual` 对标评测（冻结任务簇）。
- 推荐真实 runtime 参数：`--async-submit --fail-on-errors`（长任务不受同步请求超时影响）。
- `artifacts/manual_parity/<date>/parity_stats.json`：mean delta + bootstrap CI + Wilcoxon + Cliff's delta。
- `artifacts/manual_parity/<date>/failure_taxonomy_summary.json`：失败类型占比与严重度。
- `scripts/analyze_failure_taxonomy.py`：产出失败信号与严重样本校准报告。
- `artifacts/manual_parity/<date>/failure_taxonomy_analysis.json`：top signals / severe cases / calibration hints。
- `artifacts/manual_parity/<date>/errors.json`：失败样本与错误详情（支持续跑排障）。
- `scripts/evaluate_research_gate.py`：基于固定 gate 规则给出 PASS/FAIL。
- `artifacts/manual_parity/<date>/gate_report.json`：各 gate check 的 observed/threshold 与结论。
- `scripts/run_research_pipeline.py`：一键串联矩阵/对照/parity/failure/gate，并输出 pipeline 报告。

## 7. 运行门槛

1. 配置好 `OPENAI_API_KEY`。  
2. `CHAT2GRAPH_RUNTIME_MODE=sdk` 且 `CHAT2GRAPH_ROOT` 可用。  
3. DB 切换到 PostgreSQL（推荐）。

## 8. 失败预案

1. judge 成本过高：先用 rule+heuristic 过滤再调用 openai judge。  
2. 运行时抖动：重试 + timeout + 标记无效样本。  
3. 结果分歧大：扩充 holdout 与种子数。

## 9. Phase 10 Gate

- 基线与消融矩阵固定、统计流程固定、脚本入口固定。  
Gate 结论：`PASS`。
