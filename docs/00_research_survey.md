# GraphAgentAutomated 调研报告（2026-02-06）

## 1. 调研目标与范围

本轮调研聚焦 4 个方向：

1. 图数据库领域近两年进展（标准、产品能力、Graph+AI 形态）。
2. 数据合成方法与工程路线（用于动态小样本评估集生成）。
3. 基于大模型的评估方法（LLM-as-a-Judge、持续评估）。
4. AFlow 的方法、实现与可迁移点。

调研输出目标：为新项目 `GraphAgentAutomated` 设计一个“**独立系统**”，仅把 `chat2graph` 当作外部 runtime/SDK 使用，不修改其内部实现。

---

## 2. 图数据库领域进展

### 2.1 标准层：GQL 已成国际标准，且在持续演进

- **ISO/IEC 39075:2024 (GQL)** 已发布，定义 property graph 的数据结构与查询/管理语言语义。
- ISO 页面显示该标准已进入后续修订生命周期（下一版 CD 已在推进）。

这意味着：

1. 多图数据库的查询语言/能力正在向可移植性靠拢。
2. 新系统在 DSL 和评估样本设计上，应尽量抽象到 “GQL/属性图语义层”，而不是绑定单一厂商语法。

### 2.2 能力层：Graph + Vector + Analytics 融合已成主流

- Neo4j 文档显示向量索引已在 5.x 进入 GA（5.13 起），并与 Cypher 语义索引体系融合。
- AWS Neptune Analytics 明确提供：内存优化图分析、低延迟图查询、图遍历中的向量搜索能力。

结论：

1. 图数据库不再只承担关系查询，也承担语义检索和图算法推理。
2. 自动编排系统要把“检索动作”“图查询动作”“图算法动作”作为独立能力粒度建模。

### 2.3 生态层：GraphRAG 进入工程化阶段

- `microsoft/graphrag` 仓库活跃度很高（大规模 star/fork），定位是“模块化 graph-based RAG 系统”，并强调索引成本与 prompt tuning。

启发：

1. GraphRAG 的关键不是单次检索，而是“索引管线 + 图结构化中间层 + 查询编排”。
2. 我们的智能体自动生成系统应支持 topology 层优化（比如 planner-worker-reviewer），而不仅是 prompt 文本层微调。

---

## 3. 数据合成：方法与路线

### 3.1 主流方法族

#### A. Instruction Bootstrapping

- Self-Instruct：模型自生成指令 + 过滤再训练。
- WizardLM / Evol-Instruct：通过逐步改写提升任务复杂度。

特点：成本低、规模化快，但易出现语义漂移与分布偏置。

#### B. Self-Play / Self-Rewarding

- SPIN（Self-Play Fine-Tuning）：模型与历史版本自博弈，理论分析给出分布对齐方向。
- Self-Rewarding LM：模型同时做生成与评估，形成闭环优化。

特点：能持续提升，但易出现“自我强化偏差”，需要锚定与外部校准。

#### C. 工程化合成管线

- NVIDIA NeMo Curator：模块化合成、过滤、去重、偏好数据生成，支持 OpenAI 兼容推理端点。

特点：强调“合成 + 质量控制 + 数据工程”的全链路，而非单点 prompt。

### 3.2 本项目建议路线（面向图任务）

我们采用 **Schema-grounded Dynamic Synthesis**：

1. 从 runtime 拉取图 schema/能力快照。
2. 基于任务意图生成 seed cases（query/analysis/modeling/import/qa）。
3. 通过模板扰动 + 语义改写构造候选样本。
4. 用可执行约束过滤（字段、可答性、工具可达性）。
5. 采样得到小规模评估集（默认 6~30 条），用于当前请求的 workflow 搜索。

关键点：

- 评估集“按请求动态生成”，不追求一次性大数据集。
- 质量控制优先于规模。
- 保留样本 lineage（来源、改写、过滤原因），用于事后分析。

---

## 4. LLM 评估方法

### 4.1 学术与工程共识

- G-Eval：证明了 LLM 评分在部分任务上更接近人工判断，但存在模型偏好风险。
- Prometheus 2：开源 evaluator 模型，强调“直接评分 + pairwise 排序 + 自定义 rubric”。
- RAGAS：提供 RAG 场景的 reference-free 指标体系（如 faithfulness, context precision）。

### 4.2 生产实践趋势

- OpenAI 文档强调 eval-driven 开发：明确目标、构建数据集、定义指标、持续评估。
- OpenAI Evals API 已支持 eval 创建、run 管理、输出项追踪，适合接入 CI。

### 4.3 本项目评估策略

采用三层评估：

1. **Case-level**：LLM Judge 打分（0~1）+ rationale。
2. **Aggregate-level**：均分 + latency/cost 惩罚 + 拓扑复杂度惩罚。
3. **Reflection-level**：失败样本归因，生成下一轮 prompt/tool/topology 改进建议。

控制偏差的措施：

- 首选 pairwise/rubric 化判别任务，减少开放式评分漂移。
- 固定 judge prompt 版本与温度。
- 周期性引入人工 spot-check。
- 使用“参考模型 + 裁判模型”双轨校准。

---

## 5. AFlow 调研与可借鉴点

### 5.1 AFlow 核心机制

根据论文与仓库说明：

- 将 workflow 优化建模为搜索问题（代码表示节点+边）。
- 使用 MCTS 迭代：选择、扩展、执行评估、经验回传。
- 通过代码/算子修改不断提升性能。
- 仓库中已提供 `--check_convergence`、`--validation_rounds` 等早停参数。

### 5.2 AFlow 的强项

1. 把工作流自动化优化做成统一框架，而非单次 prompt 优化。
2. 显式记录迭代轨迹，便于回放/对比。
3. 支持从 benchmark 扩展到自定义任务。

### 5.3 AFlow 的局限（本项目要解决）

1. 原生更偏“代码工作流优化”，对我们需要的“runtime 解耦 + SDK 输出”需要额外工程化。
2. 收敛保障更多是经验性的，需要额外停止准则与泛化验证。
3. 对图数据库任务的 tool/topology 细粒度建模仍可继续深化。

---

## 6. 对 GraphAgentAutomated 的设计启发

1. **架构原则**：优化器与 runtime 完全解耦，chat2graph 仅作为 adapter 插件。
2. **优化对象**：联合优化 prompt + toolset + topology，而不是只优化 prompt。
3. **评估对象**：从 reward 信号切换为 LLM-based rubric judge + reflection 闭环。
4. **收敛策略**：采用“目标函数 + 早停 + 交叉验证 + 回退”四件套，避免无穷搜索。

---

## 7. 关键参考资料

1. ISO/IEC 39075:2024 GQL: https://www.iso.org/standard/76120.html
2. Neo4j Vector Indexes: https://neo4j.com/docs/cypher-manual/5/indexes/semantic-indexes/vector-indexes/
3. AWS Neptune Analytics: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html
4. Microsoft GraphRAG: https://github.com/microsoft/graphrag
5. AFlow 论文: https://arxiv.org/abs/2410.10762
6. AFlow 代码仓库: https://github.com/FoundationAgents/AFlow
7. Self-Instruct: https://arxiv.org/abs/2212.10560
8. WizardLM / Evol-Instruct: https://arxiv.org/abs/2304.12244
9. SPIN (Self-Play Fine-Tuning): https://arxiv.org/abs/2401.01335
10. Self-Rewarding LMs: https://arxiv.org/abs/2401.10020
11. NVIDIA NeMo Curator（合成数据）: https://docs.nvidia.com/nemo/curator/0.25.7/about/concepts/text/data-generation-concepts.html
12. G-Eval: https://arxiv.org/abs/2303.16634
13. Prometheus 2: https://arxiv.org/abs/2405.01535
14. RAGAS: https://arxiv.org/abs/2309.15217
15. RAGAS Faithfulness 指标: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
16. OpenAI Evaluation Best Practices: https://platform.openai.com/docs/guides/evaluation-best-practices
17. OpenAI Evals API: https://platform.openai.com/docs/api-reference/evals/getRuns
