# Phase 5: Prompt Optimization Protocol

版本：v1.0  
日期：2026-02-07

## 1. 目标

把 prompt 优化从单次“字符串拼接”升级为可搜索、可记录、可回滚的候选策略。

## 2. 候选生成

输入：`base prompt + failure cases + task desc`。

生成多个候选，覆盖：

1. Evidence discipline
2. Uncertainty handling
3. Output structure constraints
4. Failure recovery

## 3. 候选评分（启发式）

`Score(p) = base + keyword_coverage + failure_token_coverage - length_penalty`

并写入 `PromptVariantRegistry`：

- `variant_id`
- `source`
- `score`
- `metadata`

## 4. 实现映射

文件：`src/graph_agent_automated/infrastructure/optimization/prompt_optimizer.py`

核心组件：

- `CandidatePromptOptimizer`
- `PromptVariantRegistry`

## 5. 与外部方法对齐

- OpenAI Prompt Optimizer：强调“数据集 + grader +迭代优化”的闭环。
- DSPy MIPROv2：联合优化 instruction + few-shot，并用 Bayesian Optimization 选组合。
- OPRO：把 prompt 搜索显式建模为优化问题。

## 6. 当前边界与改进方向

边界：当前评分仍是轻量启发式。  
改进：

1. 引入 judge-in-the-loop pairwise ranker。  
2. 增加 grammar/constraint 检查器。  
3. 支持多目标 Pareto 选择（质量-成本）。

## 7. Phase 5 Gate

- prompt 候选可版本化、可解释、可回滚。  
Gate 结论：`PASS`。
