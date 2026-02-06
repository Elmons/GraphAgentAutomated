# Phase 13: Production Readiness Plan

版本：v1.0  
日期：2026-02-07

## 1. 目标

把 GraphAgentAutomated 从研究原型推进到可上线系统，满足：

1. 自然语言生成图数据库智能体。  
2. 自动方案可与人工设计方案做同条件对标。  
3. 服务具备基础可运维、可回放、可审计能力。

## 2. 已具备能力

1. Profile 驱动的 baseline/ablation 实验矩阵。  
2. Run 级 artifact（dataset/trace/prompt variants/summary）。  
3. Manual parity 接口：自动生成 vs 人工蓝图同 split 对比。  
4. 数据库版本化与 agent lifecycle（validated/deployed/rollback）。

## 3. 上线前必须补齐

1. 鉴权与多租户隔离（API key / JWT / RBAC）。  
2. 请求幂等键与任务队列（防止长任务重复触发）。  
3. 超时、重试与熔断（runtime/judge/tool 调用链）。  
4. 结构化日志与指标（P95 延迟、失败率、成本、parity 达成率）。  
5. 数据与 artifact retention 策略（清理与归档）。  
6. PostgreSQL + Alembic 标准化迁移流程。  
7. CI gate：测试、lint、migration check、API contract check。

## 4. 与人工水平对齐策略

1. 固定任务簇与种子，跑 `manual parity` 报告。  
2. 设定上线门槛：`parity_achieved rate >= 70%`（可按业务调参）。  
3. 对未达标任务进入 error bucket，自动触发 profile/knob 重跑。  
4. 每周审计人工与自动差异案例，更新 hard-negative 与 prompt policy。

推荐脚本：

`scripts/run_manual_parity_matrix.py --manual-blueprint-path <path> --seeds 3`

## 5. 建议里程碑

1. M1（1 周）：补齐鉴权 + 任务队列 + 可观测性。  
2. M2（2 周）：接入真实 runtime 大规模压力测试。  
3. M3（3 周）：以 parity rate 作为发布门槛进入灰度。
