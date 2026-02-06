# Phase 10 Addendum: Failure Taxonomy Rule Versioning

版本：v1.0  
日期：2026-02-07

## 1. 目标

将 failure taxonomy 规则从硬编码改为可版本化 JSON，支持离线重算与校准。

## 2. 规则文件

- 默认规则：`docs/benchmarks/failure_taxonomy_rules_v1.json`
- 环境变量：`FAILURE_TAXONOMY_RULES_FILE`

当设置该环境变量时，服务端会在 `manual-parity` 时使用指定规则进行失败分型。

## 3. 规则结构

```json
{
  "rules_id": "failure_taxonomy_rules_v1",
  "version": "1.0.0",
  "keywords": {
    "execution_grounding": ["timeout", "..."],
    "tool_selection": ["tool", "..."],
    "decomposition": ["missing step", "..."],
    "verifier_mismatch": ["expected", "..."]
  },
  "thresholds": {
    "severe_gap": 0.4,
    "moderate_gap": 0.2,
    "fallback_decomposition_gap": 0.2
  }
}
```

## 4. 离线重算命令

```bash
uv run python scripts/recompute_failure_taxonomy.py \
  --records-path artifacts/manual_parity/<date>/records.json \
  --rules-path docs/benchmarks/failure_taxonomy_rules_v1.json
```

输出：

- `recomputed_failure_taxonomy.json`
- 可选 `--write-records-path` 输出替换后 records。

## 5. 建议流程

1. 先跑 `analyze_failure_taxonomy.py` 看主失败簇。  
2. 调整规则文件（新版本号）。  
3. 用 `recompute_failure_taxonomy.py` 对同一批 records 离线重算。  
4. 对比重算前后的 `by_category_ratio` 与 `severe_cases_top`，决定是否升级规则版本。
