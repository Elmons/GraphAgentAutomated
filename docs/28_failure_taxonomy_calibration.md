# Phase 10 Addendum: Failure Taxonomy Calibration Protocol

版本：v1.0  
日期：2026-02-07

## 1. 目标

将 `manual parity` 的失败分型结果转化为稳定的校准报告，支持后续规则更新。

## 2. 输入

- `artifacts/manual_parity/<date>/records.json`

每条记录应包含 `failure_taxonomy.case_items`（来自 API 返回）。

## 3. 执行命令

```bash
uv run python scripts/analyze_failure_taxonomy.py \
  --records-path artifacts/manual_parity/<date>/records.json

# 如需验证新规则：先编辑 failure_taxonomy_rules_v*.json，再离线重算
uv run python scripts/recompute_failure_taxonomy.py \
  --records-path artifacts/manual_parity/<date>/records.json \
  --rules-path docs/benchmarks/failure_taxonomy_rules_v1.json
```

## 4. 输出

- `artifacts/manual_parity/<date>/failure_taxonomy_analysis.json`

核心字段：

1. `by_category_ratio`
2. `by_severity_ratio`
3. `top_signals`
4. `top_signals_by_category`
5. `severe_cases_top`
6. `calibration_hints`

## 5. 使用建议

1. 先看 `by_category_ratio`，定位主要失败簇。  
2. 再看对应簇的 `top_signals_by_category`，校准关键词规则。  
3. 最后检查 `severe_cases_top`，确认高风险失败是否被正确分类。
