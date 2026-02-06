# Phase 2: Method Blueprint

版本：v1.0  
日期：2026-02-07

## 1. 状态与目标

定义候选工作流状态：

`x = (W, P, T, G)`

- `W`: workflow blueprint（actions + experts + operators）
- `P`: 核心 operator prompt（可多版本）
- `T`: 已选工具子集
- `G`: 拓扑模式（linear / planner-worker-reviewer / router-parallel）

训练目标（用于树搜索回传）：

`J_train(x) = S + λ_conf*C - λ_lat*L - λ_cost*K - λ_cmp*Comp`

- `S`: mean judge score
- `C`: mean confidence
- `L`: mean latency
- `K`: mean token cost
- `Comp`: 工作流复杂度项

模型选择目标（用于部署选择）：

`x* = argmax_x J_val(x)`，最终仅在 `D_test` 做一次保留评估。

## 2. 算法流程（AFlowX-v2）

1. 动态合成 `D = {D_train, D_val, D_test}`。
2. 基于 tool policy 构造 root blueprint。
3. 迭代 `round`：
   - Selection: UCB + novelty
   - Expansion: 三种 mutation（prompt/tool/topology）
   - Evaluation: train + val 双评估
   - Backprop: 仅回传 train objective
   - Model Selection: 基于 val objective 更新 best
   - Logging: round trace（improvement/regret）
4. Early Stop: `min_improvement + patience`。
5. Final Test: 对 best-val 候选在 `D_test` 评估。

## 3. 伪代码

```text
Input: task u, runtime R, budgets B
D <- Synthesize(u, R.schema, B.dataset) split into train/val/test
x0 <- BuildInitialBlueprint(u, ToolRank(u, R.tools))
Init tree with node(x0)
Eval x0 on train,val
for r in [1..Rounds]:
  n <- SelectByUCB(tree)
  for e in [1..Expansions]:
    x' <- Mutate(n, mode in {prompt, tool, topology})
    y_train <- Evaluate(x', D_train)
    y_val <- Evaluate(x', D_val)
    Backprop(tree, n->x', J_train(y_train))
    UpdateBestByVal(x', y_val)
    UpdateToolGain(mutation, delta_train)
    LogRoundTrace(..., regret)
  if no val improvement >= eps for patience rounds:
    break
y_test <- Evaluate(best_val, D_test)
Return best_val, y_train(best), y_val(best), y_test, traces, artifacts
```

## 4. 复杂度与工程预算

- 记 `R` 为 rounds，`E` 为 expansions_per_round，`C` 为每次评估样本数。
- 主要成本：`O(R * E * C * ExecCost)`。
- 工程策略：
  - 小样本动态集（6~30）
  - split budget（train/val/test）
  - 早停
  - prompt 候选数上限

## 5. 不确定性处理

- Judge-level：多裁判投票 + agreement/confidence。
- Search-level：记录 regret，偏好低 regret 路径。
- Deployment-level：优先 val 最优而非 train 最优。

## 6. 与论文相关的可消融点

1. 去掉 val/test holdout。  
2. 去掉 ensemble judge。  
3. 去掉 tool historical gain。  
4. 去掉 hard-negative synthesis。  
5. 去掉 topology mutation。

## 7. Phase 2 Gate

- 有明确目标函数、伪代码、复杂度、可消融入口。  
Gate 结论：`PASS`。
