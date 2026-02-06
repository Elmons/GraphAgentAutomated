# Phase 12: Idea Comparison Protocol

版本：v1.0  
日期：2026-02-07

## 1. 目标

把 idea profile 与 `full_system` 的对照实验固定为可复现流程与标准工件。

## 2. 运行步骤

1. 跑实验矩阵（包含 idea arms）：

```bash
uv run python scripts/run_experiment_matrix.py \
  --base-url http://127.0.0.1:8008 \
  --benchmark-path docs/benchmarks/research_benchmark_v1.json \
  --seeds 5 \
  --include-idea-arms
```

2. 对比 `full_system` 与目标 idea arm：

```bash
uv run python scripts/analyze_experiment_arms.py \
  --records-path artifacts/experiments/<date>/records.json \
  --baseline-arm full_system \
  --target-arms idea_failure_aware_mutation

# 自动判定 hypothesis 是否被支持
uv run python scripts/evaluate_hypothesis.py \
  --arm-comparison-path artifacts/experiments/<date>/arm_comparison_summary.json \
  --hypothesis-spec-path docs/benchmarks/hypothesis_idea1_v1.json
```

## 3. 输出工件

- `artifacts/experiments/<date>/records.json`
- `artifacts/experiments/<date>/summary.json`
- `artifacts/experiments/<date>/arm_comparison_summary.json`
- `artifacts/experiments/<date>/hypothesis_report.json`

## 4. 判读建议

1. 主指标：`mean_score_delta`（target - baseline）应为正。  
2. 稳定性：关注 `p10_score_delta` 与 `score_delta_ci95` 下界。  
3. 显著性：关注 `wilcoxon.p_value`。  
4. 效应量：关注 `cliffs_delta`。  
5. 分簇：检查 `by_category` 与 `by_task`，避免“平均值掩盖失败簇”。
