# GraphAgentAutomated

独立的智能体自动生成系统：动态数据合成 + prompt/tool/topology 联合优化 + LLM 评估闭环。

`chat2graph` 仅作为外部 runtime 使用，不修改其内部实现。

新增：支持 `profile` 驱动的 baseline/ablation 实验矩阵，所有 arm 会真实影响
数据合成、judge、mutation 空间与搜索目标（不再是“同配置换名字”）。

## 文档

1. `docs/00_research_survey.md` 调研
2. `docs/01_requirements.md` 需求分析
3. `docs/02_system_design.md` 系统设计
4. `docs/03_test_design.md` 测试设计
5. `docs/04_implementation.md` 实现说明
6. `docs/09_execution_todo.md` 执行清单
7. `docs/10_research_charter.md` 研究章程
8. `docs/11_problem_and_claims.md` 问题与贡献声明
9. `docs/12_method_blueprint.md` 算法蓝图
10. `docs/13_system_arch_v2.md` 系统架构 v2
11. `docs/14_synthesis_protocol.md` 数据合成协议
12. `docs/15_prompt_optimization_protocol.md` Prompt 优化协议
13. `docs/16_tool_mapping_and_policy.md` 工具映射与策略
14. `docs/17_judge_reliability.md` Judge 可靠性
15. `docs/18_search_and_convergence.md` 搜索与收敛
16. `docs/19_mock_validation_report.md` Mock 验证报告
17. `docs/20_real_experiment_plan.md` 真实实验计划
18. `docs/21_paper_package.md` 投稿材料包
19. `docs/22_top_conf_idea_rcds.md` 顶会 idea 与落地实现
20. `docs/23_production_readiness.md` 生产化路线与门槛
21. `docs/24_codex_session_guide.md` 新会话 Codex 强制指引

新会话入口：先读 `docs/09_execution_todo.md` 与 `docs/24_codex_session_guide.md`。

## 开发（uv）

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run pytest
uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --seeds 3
uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --seeds 5 --include-ablations
uv run python scripts/run_manual_parity_matrix.py --base-url http://127.0.0.1:8008 --manual-blueprint-path /abs/path/to/artifacts/manual_blueprints/manual_workflow.yml --seeds 3
# 如需走代理：追加 --trust-env
```

## API 示例

`POST /v1/agents/optimize`

```json
{
  "agent_name": "fraud-agent",
  "task_desc": "Find risky transfer chains with graph query and explain evidence",
  "dataset_size": 12,
  "profile": "full_system",
  "seed": 7
}
```

当 `AUTH_ENABLED=true` 时，请在请求头中携带以下任一凭证：

- `X-API-Key: <key>`
- `Authorization: Bearer <jwt>`

所有写请求（`optimize` / `manual-parity` 及其 async 接口）支持 `Idempotency-Key` 请求头，用于重试去重。

可选 `profile`：

- `baseline_static_prompt_only`
- `dynamic_prompt_only`
- `dynamic_prompt_tool`
- `full_system`
- `ablation_no_holdout`
- `ablation_single_judge`
- `ablation_no_hard_negative`
- `ablation_no_tool_gain`
- `ablation_no_topology_mutation`

## 人工对标评测

可将人工设计的 `workflow.yml`（或内部 `blueprint.json`）与自动生成 agent 在同一 run 数据集上对比：

`POST /v1/agents/benchmark/manual-parity`

```json
{
  "agent_name": "fraud-agent-parity",
  "task_desc": "Find risky transfer chains with graph query and explain evidence",
  "manual_blueprint_path": "/abs/path/to/artifacts/manual_blueprints/manual_workflow.yml",
  "dataset_size": 12,
  "profile": "full_system",
  "seed": 7,
  "parity_margin": 0.03
}
```

返回 `parity_achieved=true` 表示自动方案在容差 `parity_margin` 内达到人工设计水平。
`manual_blueprint_path` 必须位于 `MANUAL_BLUEPRINTS_DIR`（默认 `./artifacts/manual_blueprints`）目录下。

## 异步任务接口

为避免同步请求阻塞，支持异步提交与轮询：

- `POST /v1/agents/optimize/async`
- `POST /v1/agents/benchmark/manual-parity/async`
- `GET /v1/agents/jobs/{job_id}`

提交接口返回 `202` 和 `job_id`，状态查询返回 `queued/running/succeeded/failed`。
异步提交接口同样支持 `Idempotency-Key`，重复提交会返回同一 `job_id`。

## 配置

使用 `pydantic_settings` 统一管理环境变量，见 `.env.example`。

鉴权与租户隔离（API key/JWT + RBAC）：

- `AUTH_ENABLED=true` 开启鉴权（默认 `false`）。
- `AUTH_API_KEYS_JSON` 使用 JSON 对象配置 API key，例如：

```json
{
  "tenant-a-admin-key": {"tenant_id": "tenant-a", "role": "admin"},
  "tenant-a-viewer-key": {"tenant_id": "tenant-a", "role": "viewer"},
  "tenant-b-operator-key": {"tenant_id": "tenant-b", "role": "operator"}
}
```

不同 `tenant_id` 的请求会自动进行 agent 数据隔离（同名 agent 互不干扰）。

JWT 配置（支持密钥轮换）：

- `AUTH_JWT_KEYS_JSON` 使用 `kid -> secret` 的 JSON 对象，例如：

```json
{
  "kid-2026-01": "old-secret",
  "kid-2026-02": "new-secret"
}
```

- `AUTH_JWT_ISSUER` / `AUTH_JWT_AUDIENCE` 可选开启 `iss`/`aud` 校验。
- token 需包含 `tenant_id`、`role`、`exp` claims；当配置了多个 key 时，JWT header 必须带 `kid`。
