# Phase 6: Tool Mapping & Policy

版本：v1.0  
日期：2026-02-07

## 1. 目标

把工具选择从关键词匹配升级为“能力图谱 + 历史收益”的组合策略，并可追踪每次选择依据。

## 2. chat2graph 工具盘点（外部 runtime）

来源：`/home/bajiao/Bajiao/code/python/lab/chat2graph/app/core/sdk/chat2graph.yml`

关键工具族：

1. Graph Query：`CypherExecutor`
2. Graph Analytics：`PageRankExecutor`、`LouvainExecutor`、`ShortestPathExecutor` 等
3. Schema/Modeling：`SchemaGetter`、`VertexLabelAdder`、`EdgeLabelAdder`
4. Import：`DataImport`、`DataStatusCheck`
5. QA/Retrieval：`KnowledgeBaseRetriever`、`BrowserUsing`

## 3. 能力映射

`Tool -> {query, analytics, modeling, import, qa, general}`

规则来源：tool name + description + tags。

## 4. 排序函数

`Score(tool) = lexical(task,intent) + capability_alignment + 0.5 * historical_gain`

- `lexical`: 任务词与工具文本匹配
- `capability_alignment`: intent 与 capability 重合
- `historical_gain`: 来自 round 改进的 EMA

## 5. 实现映射

文件：`src/graph_agent_automated/infrastructure/optimization/tool_selector.py`

组件：

- `ToolCapabilityMapper`
- `IntentAwareToolSelector`

搜索器内协同：`search_engine._update_tool_gain` 按 `tool:add(...)` mutation 更新历史收益。

## 6. 证据链输出

每次优化 run 持久化：

- selected mutation
- train/val objective
- improvement/regret

可用于回溯“某工具为何被保留/剔除”。

## 7. 后续增强

1. capability graph 改为可学习权重。  
2. 增加工具冲突/冗余惩罚。  
3. 增加 runtime 健康状态先验（降级策略）。

## 8. Phase 6 Gate

- 工具选择具备能力映射、历史收益、可追踪证据。  
Gate 结论：`PASS`。
