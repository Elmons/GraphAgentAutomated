# Phase 9: Mock-first Strong Validation

版本：v1.0  
日期：2026-02-07

## 1. 验证目标

在无真实模型 key 条件下，验证系统机制正确性、稳定性与失败路径可控。

## 2. 验证范围

1. 单元测试：synthesis/search/evaluator/repository/prompt/tool policy。  
2. 集成测试：FastAPI optimize/version/deploy/rollback 全链路。  
3. 迁移测试：Alembic upgrade/downgrade。  
4. 机制测试：属性测试、变形测试、对抗测试。

## 3. 关键命令与结果

```bash
uv run ruff check src tests --fix
uv run pytest -q
uv run pytest --cov=src/graph_agent_automated --cov-report=term-missing
DATABASE_URL=sqlite:///./alembic_test.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./alembic_test.db uv run alembic downgrade base
```

结果摘要（本轮）：

1. `pytest`: 15 passed
2. 覆盖率：90%
3. 迁移：upgrade/downgrade 成功

## 4. 机制级测试证据

新增测试：`tests/unit/test_mock_validation.py`

1. 属性测试：dataset size 边界与 split 求和不变量。  
2. 变形测试：task 描述噪声不改变 intent profile。  
3. 对抗测试：hard-negative case 对 runtime score/confidence 产生可预期惩罚。

## 5. 残余风险

1. chat2graph SDK 真机路径未覆盖（当前以 mock 为主）。
2. OpenAI judge 在真实流量下的稳定性需后续验证。
3. 统计显著性尚未在真实数据上运行。

## 6. Phase 9 Gate

- mock-first 条件下关键机制可运行、可回归、可解释。  
Gate 结论：`PASS`。
