# GraphAgentAutomated 需求分析

## 1. 背景与问题

现有系统中，工作流自动生成能力已存在，但存在以下不足：

1. 缺少“按用户请求动态生成评估集”的能力。
2. 优化维度不够细化，prompt/tool/topology 的协同优化不足。
3. 评估过度依赖 reward/反馈信号，缺少 LLM 评估+反思闭环。
4. 与 chat2graph 耦合较深，不利于独立演进。

本项目目标：构建一个独立系统 `GraphAgentAutomated`，将 chat2graph 仅作为外部 runtime/SDK。

---

## 2. 目标与非目标

## 2.1 目标

1. 动态数据合成：基于用户任务与图 schema 生成小型评估集。
2. 自动生成与编排：联合优化 prompt、工具集合、智能体拓扑。
3. LLM 评估：使用 LLM Judge 与 Reflection 作为主反馈闭环。
4. Agent 管理：支持版本化、部署状态、回滚、审计。
5. 工程化可运维：FastAPI + SQLAlchemy + Alembic + Pydantic Settings。

## 2.2 非目标

1. 不修改 chat2graph 内核实现。
2. 不在首版支持多租户权限体系。
3. 不在首版支持在线训练/参数微调。

---

## 3. 用户与场景

## 3.1 主要用户

1. 算法/平台工程师：配置优化策略并发布 agent 版本。
2. 业务开发者：提交任务描述并获取最优工作流。
3. 运维/评估人员：查看版本、评估报告、回滚到稳定版本。

## 3.2 典型场景

1. 输入任务描述（如图查询+分析复合任务）。
2. 系统动态生成评估集。
3. 系统执行多轮搜索优化，输出最优 workflow。
4. 生成 chat2graph 可执行 yaml，注册为新版本。
5. 通过 API 将版本发布为 deployed，并支持回滚。

---

## 4. 功能需求（FR）

### FR-1 动态数据合成

1. 根据任务描述识别任务意图（query/analytics/modeling/import/qa）。
2. 从 runtime 获取 schema 快照与工具目录。
3. 生成并过滤 6~30 条评估样本。
4. 保存样本 lineage（来源、模板、过滤标签）。

### FR-2 自动搜索优化

1. 支持 MCTS 风格多轮搜索。
2. 每轮可进行三类 mutation：
   - prompt 优化
   - 工具选取/裁剪
   - 拓扑切换（linear / planner-worker-reviewer / router-parallel）
3. 目标函数支持质量、时延、成本与复杂度联合权衡。

### FR-3 LLM 评估与反思

1. case-level 打分与解释。
2. aggregate-level 统计与目标函数评分。
3. reflection 反馈用于下一轮优化。

### FR-4 Agent 版本管理

1. 版本状态：draft/validated/deployed/archived。
2. 发布与回滚。
3. 历史版本查询与对比。
4. 评估明细可追溯。

### FR-5 Runtime 适配

1. `MockRuntimeAdapter`：无 key 场景可跑通全流程。
2. `Chat2GraphSDKRuntimeAdapter`：通过外部路径加载 chat2graph SDK。
3. 输出 chat2graph 兼容 yaml 配置。

### FR-6 Web API

1. `POST /v1/agents/optimize` 触发优化。
2. `GET /v1/agents/{name}/versions` 查看版本。
3. `POST /v1/agents/{name}/versions/{version}/deploy` 发布版本。
4. `POST /v1/agents/{name}/versions/{version}/rollback` 回滚版本。
5. `GET /healthz` 健康检查。

---

## 5. 非功能需求（NFR）

1. 可配置性：全部关键参数通过环境变量管理。
2. 可迁移性：数据库从 sqlite 平滑切到 PostgreSQL。
3. 可测试性：核心链路可在 mock 模式下全自动测试。
4. 可观测性：保留轮次日志、评分轨迹、产物路径。
5. 可维护性：模块解耦，遵循开闭原则，接口优先。

---

## 6. 风险与约束

1. LLM 评估存在偏差：需要 rubric 固定与抽样人工复核。
2. 搜索不保证全局最优：需早停、回退与 holdout 校验。
3. runtime 外部依赖不稳定：需 mock runtime 与降级策略。
4. 动态合成数据偏移：需引入 schema 约束与多样性采样。

---

## 7. 验收标准

1. 能在 mock runtime 下端到端生成并持久化 agent 版本。
2. 能输出 chat2graph 可加载的 workflow yaml。
3. API 能完成发布/回滚并正确更新状态。
4. pytest 覆盖：合成、优化、评估、仓储、API 全链路。
5. 文档完整：调研、需求、系统设计、测试设计齐备。
