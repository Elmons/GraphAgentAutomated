# Phase 8: Search & Convergence

版本：v1.0  
日期：2026-02-07

## 1. 目标

在无解析收敛保证的 workflow 搜索中，建立工程可控的收敛证据与漂移抑制机制。

## 2. 机制

1. Train objective 用于树回传（探索效率）。
2. Validation objective 用于模型选择（泛化控制）。
3. Test 仅在最终 best-val 上执行（防信息泄露）。
4. `min_improvement + patience` 控制早停。
5. `regret` 逐轮记录，识别“高估节点”。

## 3. 记录结构

每个 `SearchRoundTrace` 包含：

- selected node/blueprint
- mutation
- train/val objective
- best_train/best_val objective
- improvement
- regret

## 4. 当前实现

文件：`src/graph_agent_automated/infrastructure/optimization/search_engine.py`

关键点：

1. split-aware evaluate（train/val/test）
2. confidence-aware objective
3. historical tool gain 更新
4. prompt variant 收集

## 5. 漂移诊断规则

1. `train↑` 但 `val↓`：过拟合候选，降权相似 mutation。  
2. `regret` 持续偏高：收紧探索系数或提前停止。  
3. `judge_agreement` 低：暂停大步拓扑变更。

## 6. 理论边界

- 该系统属于近似搜索，不提供全局最优保证。
- 通过 holdout + early stop + trace 实现“可解释收敛”，而非数学完备收敛。

## 7. Phase 8 Gate

- round-wise trace 与早停机制完备，可回放。  
Gate 结论：`PASS`。
