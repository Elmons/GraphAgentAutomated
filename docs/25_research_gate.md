# Phase 11: Research Gate Specification

版本：v1.0  
日期：2026-02-07

## 1. 目标

将“算法是否够用”的判断从主观讨论改为可执行 gate。

## 2. Gate 文件

- 规则文件：`docs/benchmarks/research_gate_v1.json`
- 评估脚本：`scripts/evaluate_research_gate.py`

## 3. 输入工件

来自 parity 主实验目录（`artifacts/manual_parity/<date>/`）：

1. `records.json`
2. `parity_stats.json`
3. `failure_taxonomy_summary.json`

## 4. 当前 gate 指标（v1）

1. `min_runs`
2. `min_parity_rate`
3. `min_mean_score_delta`
4. `min_ci95_lower_bound`
5. `max_delta_std`
6. `min_p10_score_delta`
7. `max_mean_auto_latency_ms`
8. `max_mean_auto_token_cost`
9. `max_failure_severe_ratio`
10. `wilcoxon_significance`（可选开关）

## 5. 运行方式

```bash
uv run python scripts/evaluate_research_gate.py \
  --records-path artifacts/manual_parity/<date>/records.json \
  --gate-spec-path docs/benchmarks/research_gate_v1.json
```

输出：

- `gate_report.json`（默认写入与 `records.json` 同目录）
- 终端打印每项 check 的 observed/threshold/pass
- gate fail 时返回非 0 退出码，便于 CI/批跑自动拦截

## 6. 解释原则

1. gate pass 不等于“生产级”；只表示达到当前 research 证据阈值。  
2. gate fail 时优先读取 `failure_taxonomy_summary.json` 定位失败类型。  
3. 阈值升级需要版本化（`research_gate_v2.json`），不可覆盖旧版本。
