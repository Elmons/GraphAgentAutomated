# Phase 12: Research Idea Backlog (Falsifiable)

版本：v1.0  
日期：2026-02-07

## 1. Idea-1（已实现）: Failure-aware Mutation Scheduler

1. 动机：当前 mutation 轮转是固定顺序，无法根据失败类型自适应。  
2. 机制：当低分 case 以 tool/decomposition/execution/verifier 类型失败为主时，动态提升 `tool/topology/prompt` mutation 优先级。  
3. 可证伪条件：在冻结 benchmark 上，`idea_failure_aware_mutation` 相比 `full_system` 的 `mean_score_delta` 与 `parity_rate` 无提升，或 `delta_std` 变差。  
4. 最小实验：
   - 命令：`uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --benchmark-path docs/benchmarks/research_benchmark_v1.json --seeds 5 --include-idea-arms`
   - 对照：`full_system` vs `idea_failure_aware_mutation`
   - 关注：`test_mean / test_std / CI`

## 2. Idea-2（待实现）: Case Difficulty-aware Prompt Mutation

1. 动机：当前 prompt 优化对失败 case 等权，未区分难例与易例。  
2. 机制：对高难度（L3/L4）失败样本给予更高权重，减少“只优化易题”的过拟合。  
3. 可证伪条件：加入难例加权后，`p10_score_delta` 无提升或 `failure_severe_ratio` 上升。  
4. 最小实验：新增 profile 并在 parity 主实验中比较分位数与 severe failure 占比。

## 3. Idea-3（待实现）: Judge-disagreement-targeted Data Augmentation

1. 动机：judge disagreement 高时，往往说明样本歧义大或 verifier 不稳定。  
2. 机制：优先扩充 disagreement 高的任务簇，生成反事实样本做定向校准。  
3. 可证伪条件：加入该机制后，`judge_agreement` 无提升，且成本明显上升。  
4. 最小实验：加入 disagreement 触发的合成策略，报告 agreement 与 token 成本变化。

## 4. 当前落地状态

1. 已有 3 个可证伪 hypothesis。  
2. Idea-1 已端到端落地为新 profile：`idea_failure_aware_mutation`。  
3. 已新增 hypothesis 自动判定脚本：`scripts/evaluate_hypothesis.py`（基于 `hypothesis_idea1_v1.json`）。  
4. 尚未完成真实 runtime + 真实 judge 的对照实验工件沉淀。
