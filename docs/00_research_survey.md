# GraphAgentAutomated 调研报告（更新版）

版本：v2.0  
日期：2026-02-07

## 1. 调研方法

## 1.1 目标

围绕四个核心问题建立一手证据链：

1. 图数据库领域最新进展（标准、产品、Graph+AI）
2. 数据合成方法与工程路线
3. LLM-as-a-Judge 的可行性与可靠性
4. AFlow 的核心机制与可迁移空间

## 1.2 来源选择标准

优先级：

1. 官方标准/官方文档/官方仓库
2. 顶会或高质量论文（arXiv/OpenReview）
3. 与工程实现直接相关的文档（SDK、框架文档）

---

## 2. 图数据库领域进展

## 2.1 标准层：GQL 进入国际标准阶段

- ISO 页面显示 `ISO/IEC 39075:2024`（GQL）已发布，并处于“90.92 confirmed（review date: 2029-03）”状态。
- 含义：属性图查询语义标准化趋势明确，跨产品迁移与抽象层设计更可行。

对本系统影响：

1. 数据合成样本应尽量靠近“属性图语义”而非绑定单库语法。
2. tool/prompt 设计要保留跨库移植空间。

## 2.2 产品层：Graph + Vector + Analytics 融合加速

- Neo4j Cypher 手册：向量索引在 5.11 引入，5.13 GA。
- Neo4j release notes：当前文档展示的 release line 为 `2026.01`（当前 patch `2026.01.3`）。
- AWS Neptune Analytics 官方文档强调“分析 + 查询 + 低延迟 + 内存优化”，并与 Neptune Database 协同。
- Memgraph changelog 显示 `Memgraph 3.5.2` 为最新 stable，且产品强调 Cypher/openCypher 兼容。

对本系统影响：

1. 工具策略不能只把“查询”当唯一动作，必须覆盖 analytics/retrieval/import/modeling。
2. agent 拓扑编排要允许“查询分支 + 分析分支 + 合并审阅”结构。

## 2.3 GraphRAG 进入工程化阶段

- `microsoft/graphrag` 仓库活跃（40k+ stars 级别），并明确提供 indexing/query/prompt tuning 的系统化组件。
- GraphRAG 论文强调在“全局问题”场景下，图结构索引比纯向量检索更有优势。

对本系统影响：

1. 自动生成系统应把“索引/结构化中间层/推理编排”视为一体化问题。
2. topology mutation 具备现实必要性，而不只是研究噱头。

---

## 3. 数据合成方法与路线

## 3.1 经典路线

1. Self-Instruct：模型自生成指令+过滤，低成本扩展。  
2. Evol-Instruct（WizardLM）：通过进化改写增加复杂度。  
3. 任务生成前沿：TaskCraft（ICLR 2026 提交）提出可扩展且可验证的 agentic task generation。

局限：

- 通常面向通用指令，不天然满足图任务的 schema-grounded 可答性。

## 3.2 工程化路线

- RAGAS 文档提供 `TestsetGenerator`，显式支持 query distribution 控制与知识图辅助样本生成。
- 这类路线更适合评估集动态构造，而不是一次性离线大语料蒸馏。

## 3.3 我们采用的路线

`Schema-grounded Dynamic Synthesis`：

1. 拉取 runtime schema snapshot。  
2. 识别任务 intents。  
3. 模板生成 + 改写 + hard-negative 注入。  
4. lineage + report + split（train/val/test）。

落地位置：`dynamic_synthesizer.py`。

---

## 4. LLM-based 评估与可靠性

## 4.1 可行性证据

- MT-Bench 论文报告 GPT-4 judge 与人类/Chatbot Arena 在对话评估上有较高一致性。
- G-Eval 论文显示“LLM + CoT + form-filling”评估在多项生成任务上优于传统参考指标。

## 4.2 风险证据

- JudgeBench（ICLR 2025）系统性指出 LLM judges 的偏置、鲁棒性与可操纵性问题。
- 结论：LLM judge 可用，但必须做 reliability engineering。

## 4.3 工程实践线索

- OpenAI 官方建议 eval-driven 开发（先定义任务、指标、数据，再持续迭代）。
- OpenAI docs 提供评估 prompt 优化与 graders 的工程化接口思路。

## 4.4 我们采用的评估策略

1. 多裁判（rule + heuristic + optional openai）加权。  
2. 产出 agreement/confidence，并写入 case-level 元数据。  
3. 用 reflection 驱动下一轮 prompt/tool/topology mutation。

落地位置：`judges.py` + `workflow_evaluator.py`。

---

## 5. AFlow 调研结论

## 5.1 AFlow 原始主张

- AFlow（OpenReview / arXiv）把 agent workflow 优化视作“代码工作流搜索问题”，使用 MCTS 在 workflow space 迭代，报告多任务收益。
- 官方仓库公开了 benchmark、收敛检查与配置化优化入口。

## 5.2 与本项目关系

继承：

1. workflow search 核心思想
2. MCTS 风格 select-expand-evaluate-backprop
3. 迭代式改进而非一次性 prompt 调参

增强（面向图数据库与工程可复现）：

1. 动态评估集合成（请求级）
2. split-aware 选择（train 回传 + val 选模 + test 终评）
3. judge reliability 信号
4. run-level DB 追踪与 artifact 体系

## 5.3 本地 chat2graph aflowx 对照

- `chat2graph/app/aflowx/optimizer.py`：已有基础 AFlowX 搜索框架。
- `chat2graph/app/aflowx/evaluator.py`：单 judge 反思评估。
- `chat2graph/app/core/sdk/chat2graph.yml`：给出可映射的工具全集。

我们新项目（GraphAgentAutomated）在父目录独立实现，chat2graph 仅作为 runtime adapter 调用。

---

## 6. 研究-工程差距与决策

## 6.1 差距

1. 纯搜索论文缺少工程可回放追踪。  
2. 纯 LLM judge 缺少可靠性量化。  
3. 纯模板数据合成缺少硬样本与分割机制。

## 6.2 决策

1. 引入 `optimization_runs` / `optimization_round_traces`。  
2. 引入 `judge_agreement` / `confidence`。  
3. 引入 hard-negative + lineage + split synthesis。

---

## 7. 对后续论文的直接贡献点

1. 方法贡献：joint optimization + holdout-guided convergence + reliability-aware judge。
2. 系统贡献：runtime-decoupled Graph AgentOps，具备 run-level reproducibility。
3. 实证贡献：mock-first 强验证到真实实验 protocol 的可迁移链路。

---

## 8. 参考资料（本轮使用）

1. ISO GQL: https://www.iso.org/standard/76120.html  
2. Neo4j Vector Index docs: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/  
3. Neo4j release notes: https://neo4j.com/docs/operations-manual/current/changes-deprecations-removals/  
4. AWS Neptune Analytics: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html  
5. Memgraph changelog: https://memgraph.com/docs/release-notes/changelogs  
6. Memgraph overview: https://memgraph.com/docs/fundamentals/overview  
7. GraphRAG repo: https://github.com/microsoft/graphrag  
8. GraphRAG paper: https://arxiv.org/abs/2404.16130  
9. Self-Instruct: https://arxiv.org/abs/2212.10560  
10. WizardLM / Evol-Instruct: https://arxiv.org/abs/2304.12244  
11. TaskCraft (ICLR 2026 submission): https://openreview.net/forum?id=0B2TMMf4M8  
12. RAGAS testset docs: https://docs.ragas.io/en/latest/getstarted/rag_testset_generation/  
13. G-Eval: https://arxiv.org/abs/2303.16634  
14. MT-Bench / LLM-as-a-judge: https://arxiv.org/abs/2306.05685  
15. JudgeBench: https://arxiv.org/abs/2410.12784  
16. OpenAI eval-driven guidance: https://developers.openai.com/resources/  
17. OpenAI prompt optimization cookbook: https://cookbook.openai.com/examples/optimize_prompts  
18. DSPy MIPROv2 docs: https://dspy.ai/tutorials/optimizers/  
19. AFlow OpenReview: https://openreview.net/forum?id=z5uVAKwmjf  
20. AFlow repo: https://github.com/FoundationAgents/AFlow
