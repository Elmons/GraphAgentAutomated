# GraphAgentAutomated 系统设计

## 1. 总体设计原则

1. **独立系统**：与 chat2graph 解耦，chat2graph 仅作为 runtime adapter。
2. **接口优先**：领域层用 Protocol 抽象，基础设施可插拔。
3. **闭环优化**：动态数据合成 -> 候选生成 -> LLM 评估 -> 反思反馈。
4. **工程可控**：用明确收敛准则控制搜索成本。

---

## 2. 分层架构

```text
FastAPI (API Layer)
  -> Application Service (Use Case Orchestration)
    -> Domain (models/protocols/optimization rules)
      -> Infrastructure
         - synthesis
         - optimization
         - evaluation
         - runtime adapters (mock/chat2graph)
         - persistence (SQLAlchemy/Alembic)
```

### 2.1 API 层

- 输入请求、参数校验、返回结构化响应。
- 不承载业务逻辑。

### 2.2 Application 层

- 编排完整用例：优化、发布、回滚、查询版本。
- 控制事务边界（UnitOfWork）。

### 2.3 Domain 层

- 核心模型：WorkflowBlueprint、SyntheticDataset、EvaluationSummary。
- 抽象协议：RuntimeAdapter、WorkflowEvaluator、ToolSelector 等。

### 2.4 Infrastructure 层

- 负责具体实现：MCTS 搜索、dynamic synthesis、LLM judge、SQLAlchemy 仓储、chat2graph 适配器。

---

## 3. 关键数据模型

1. `WorkflowBlueprint`：工作流候选（prompt/tool/topology 的统一表示）。
2. `SyntheticDataset`：动态评估集。
3. `EvaluationSummary`：候选在样本上的聚合评估。
4. `AgentVersion`（DB）：版本化管理与部署状态。

数据库模型：

- `agents`
- `agent_versions`
- `evaluation_cases`

通过 `AgentRepository` 管理版本生命周期。

---

## 4. 核心算法设计

## 4.1 动态数据合成（请求时执行）

输入：`task_desc + runtime schema/tool catalog`

流程：

1. 意图识别（关键词+规则，后续可替换为分类器）。
2. schema-grounded 模板生成。
3. 语义改写（轻量 paraphrase）。
4. 去重与可答性过滤。
5. 采样成固定规模评估集。

输出：`SyntheticDataset`。

## 4.2 联合搜索优化（AFlowX）

### 状态表示

搜索树节点 = 一个 `WorkflowBlueprint`。

### 动作空间（Mutation）

1. `prompt_mutation`：基于失败案例反思追加/重写约束。
2. `tool_mutation`：添加高相关工具，或裁剪低收益动作。
3. `topology_mutation`：在三种拓扑间切换。

### 选择策略

采用 UCB 风格：

`UCB = mean_value + c * sqrt(log(N)/n) + novelty_bonus`

其中 novelty_bonus 用于鼓励结构创新（拓扑变化/新工具组合）。

### 目标函数

`objective = quality - α*latency - β*cost - γ*complexity`

默认实现先用 quality/latency/cost，复杂度作为扩展项预留。

## 4.3 LLM 评估与反思

1. 逐 case 调 runtime，获取原始输出。
2. judge 打分（0~1）并生成 rationale。
3. 聚合统计，形成 reflection 文本。
4. reflection 回流到下一轮 mutation。

---

## 5. MCTS 收敛与有效性设计（重点）

你提到的核心担忧是正确的：LLM 场景下，MCTS 的 reward 非平稳、带噪声，**理论上不保证全局收敛**。

本项目采用“工程收敛”定义：

1. **改进阈值**：最佳目标函数提升小于 `min_improvement` 视作无有效改进。
2. **耐心轮次**：连续 `patience` 轮无有效改进则早停。
3. **预算约束**：`max_rounds * expansions_per_round` 作为硬预算。
4. **验证切分**：搜索集/验证集分离，最终在验证集选优，减少合成集过拟合。
5. **复杂度惩罚**：防止“为了分数无止境加工具/加链路”。
6. **回退策略**：如果新版本在验证集下降，回退到上一个稳定版本。

这套机制的哲学是：

- 不追求证明意义上的全局最优；
- 追求在固定预算内稳定得到“可部署且可回滚”的更优解。

---

## 6. Runtime 适配设计

### 6.1 MockRuntimeAdapter

- 无 LLM key、无外部依赖时可跑完整链路。
- 用确定性规则返回输出/耗时/成本，用于测试与 CI。

### 6.2 Chat2GraphSDKRuntimeAdapter

- 从 `CHAT2GRAPH_ROOT` 动态导入 `app.core.sdk.agentic_service.AgenticService`。
- 将 blueprint 渲染为 chat2graph yaml。
- 用 `AgenticService.load(yaml).execute(question)` 执行。

注意：只调用外部接口，不修改 chat2graph 源码。

---

## 7. API 设计

1. `POST /v1/agents/optimize`
2. `GET /v1/agents/{name}/versions`
3. `POST /v1/agents/{name}/versions/{version}/deploy`
4. `POST /v1/agents/{name}/versions/{version}/rollback`
5. `GET /healthz`

---

## 8. 配置与部署

- `pydantic_settings` 统一读取 `.env`。
- 数据库默认 sqlite，切 PostgreSQL 仅改 `DATABASE_URL`。
- Alembic 迁移管理结构变更。
- 使用 uv 管理依赖、启动服务与测试。

---

## 9. 扩展点

1. judge backend：mock -> openai -> prometheus2。
2. tool selector：规则 -> embedding 检索 -> 学习型 selector。
3. topology space：加入层次专家图、条件路由图。
4. multi-objective 搜索：引入 Pareto 前沿而非单标量目标。
