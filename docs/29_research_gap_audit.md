# Research Gap Audit (R0 Closure)

版本：v1.0  
日期：2026-02-07

## 1. 深入审计结论

当前最关键缺口不是“能力不存在”，而是“真实实验执行与证据沉淀效率不稳定”。

主要风险：

1. 多脚本手工串行，容易漏跑或跑错参数。  
2. 真实 runtime 长任务执行时，人工排障成本高。  
3. 结果工件存在但缺少统一 pipeline 报告，难以一次性回放审计。

## 2. 本轮新增改进

1. 一键编排脚本：`scripts/run_research_pipeline.py`  
2. pipeline 工具模块：`src/graph_agent_automated/infrastructure/runtime/research_pipeline.py`  
3. 失败分型校准分析：`scripts/analyze_failure_taxonomy.py` + `failure_taxonomy_analysis.json`  
4. 失败分型规则版本化：`docs/benchmarks/failure_taxonomy_rules_v1.json` + `scripts/recompute_failure_taxonomy.py`

## 3. 仍需完成的硬任务（R0）

1. 在真实 runtime + 真实 judge 下跑完冻结 benchmark 多 seed。  
2. 产出 `arm_comparison_summary.json`、`failure_taxonomy_analysis.json`、`gate_report.json` 并归档。  
3. 基于真实结果校准 failure taxonomy 规则（不是 mock）。  
4. 对 Idea-1 给出“支持/证伪”明确结论并写入 backlog 文档。

## 4. 下一步建议命令（单次闭环）

```bash
uv run python scripts/run_research_pipeline.py \
  --base-url http://127.0.0.1:8008 \
  --benchmark-path docs/benchmarks/research_benchmark_v1.json \
  --manual-blueprints-root /abs/path/to/GraphAgentAutomated/docs/manual_blueprints/research_benchmark_v1 \
  --seeds 5 \
  --include-idea-arms \
  --parity-async-submit \
  --parity-fail-on-errors
```
