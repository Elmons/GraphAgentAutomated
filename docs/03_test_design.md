# GraphAgentAutomated 测试设计

## 1. 测试目标

1. 在无外部 key 条件下（mock）跑通端到端流程。
2. 核心模块可单测验证，避免回归。
3. API 与数据库行为可集成验证。
4. 为切换 chat2graph runtime 提供适配层契约测试。

---

## 2. 测试分层

## 2.1 单元测试（Unit）

### 合成模块

1. 给定 task_desc + schema，生成样本数量在范围内。
2. 覆盖意图识别、去重、模板改写逻辑。
3. 空 schema 时 fallback 行为正确。

### 优化模块

1. UCB 选择逻辑正常（访问次数、value 回传）。
2. prompt/tool/topology 三类 mutation 都会触发。
3. 目标函数会对 latency/cost 施加惩罚。
4. 早停策略（patience + min_improvement）按预期触发。

### 评估模块

1. judge 正常产出 score+rationale。
2. 聚合统计正确（均值、样本数）。
3. reflection 文本包含失败摘要。

### 持久化模块

1. 创建 agent/version 成功。
2. deploy 会将旧 deployed 版本降级为 validated。
3. rollback 能切换 active 版本。

## 2.2 集成测试（Integration）

1. FastAPI + sqlite 临时库。
2. 调 `POST /optimize` 完成生成并写库。
3. 调 deploy/rollback 与 `GET versions` 验证状态流转。

## 2.3 契约测试（Adapter Contract）

1. `RuntimeAdapter` 最低契约：
   - `fetch_schema_snapshot`
   - `fetch_tool_catalog`
   - `execute_case`
   - `materialize`
2. `MockRuntimeAdapter` 必须通过契约测试。
3. `Chat2GraphSDKRuntimeAdapter` 在有外部路径时执行冒烟测试。

---

## 3. Mock 策略

1. judge 使用 deterministic mock（避免随机波动）。
2. runtime 使用 mock 输出，保证 CI 可复现。
3. 对外部 chat2graph 仅做可选测试，不纳入默认 CI 必过集。

---

## 4. 覆盖率目标

1. 核心算法模块（synthesis/optimization/evaluation）>= 85%。
2. 仓储与 API 模块 >= 80%。
3. 关键失败路径（runtime error、judge error、DB rollback）必须覆盖。

---

## 5. 测试执行命令（uv）

```bash
uv sync --all-extras
uv run pytest
uv run pytest --cov=src/graph_agent_automated --cov-report=term-missing
```

---

## 6. 验收用例（最小闭环）

1. 输入任务描述，触发优化成功。
2. 产生版本 1（validated）并写入评估明细。
3. 发布版本 1（deployed）。
4. 再优化产生版本 2，发布版本 2。
5. 回滚到版本 1，检查状态正确。
