# Phase 4: Data Synthesis Protocol

版本：v1.0  
日期：2026-02-07

## 1. 目标

为每个请求动态生成“小而有效”的评估集，驱动搜索而非训练模型参数。

## 2. 协议流程

1. Schema 拉取：labels/relations。  
2. Intent 推断：`query/analytics/modeling/import/qa`。  
3. 模板渲染与轻量改写。  
4. Hard-negative 注入（不可推断场景）。  
5. 去重与边界控制（6~30）。  
6. 数据切分：train/val/test。  
7. Lineage 记录与 synthesis report。

## 3. 质量控制指标

- `coverage_intent`: 意图覆盖数
- `hard_negative_ratio`
- `split_balance`
- `dedup_rate`

## 4. 与现有路线对齐

- Self-Instruct/Evol-Instruct 强于规模扩展，但图任务需要 schema-grounded 约束。
- RAGAS `TestsetGenerator` 强调 query distribution 与知识图驱动生成，可迁移到图任务评估集构造。
- TaskCraft（ICLR 2026 提交）提示“可扩展、可验证 agentic task 生成”是趋势。

## 5. 当前实现映射

文件：`src/graph_agent_automated/infrastructure/synthesis/dynamic_synthesizer.py`

已实现：

1. split ratio 校验与切分。
2. hard-negative case 生成。
3. lineage 元数据。
4. synthesis_report 输出。

## 6. 下一步增强

1. 增加执行可答性过滤（tool reachable checks）。
2. 引入 diversity-aware 重采样（embedding 层）。
3. 加入 persona/task style 控制参数。

## 7. Phase 4 Gate

- 支持 split、hard-negative、lineage、report。  
Gate 结论：`PASS`。
