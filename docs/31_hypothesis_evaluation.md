# Phase 12 Addendum: Hypothesis Evaluation Protocol

版本：v1.0  
日期：2026-02-07

## 1. 目标

把“idea 是否被支持/证伪”从人工主观判断变成可执行脚本输出。

## 2. 输入

- `artifacts/experiments/<date>/arm_comparison_summary.json`
- `docs/benchmarks/hypothesis_idea1_v1.json`

## 3. 执行命令

```bash
uv run python scripts/evaluate_hypothesis.py \
  --arm-comparison-path artifacts/experiments/<date>/arm_comparison_summary.json \
  --hypothesis-spec-path docs/benchmarks/hypothesis_idea1_v1.json
```

## 4. 输出

- `artifacts/experiments/<date>/hypothesis_report.json`

关键字段：

1. `supported`
2. `checks`
3. `observed`

## 5. 推荐解释

1. `supported=true` 表示当前阈值下支持该 hypothesis。  
2. 若不支持，优先看 `checks` 中失败项（例如 `min_mean_score_delta`、`min_p10_score_delta`）。  
3. 阈值调整应通过新版本 spec（例如 `hypothesis_idea1_v2.json`），不要覆盖旧版本。
