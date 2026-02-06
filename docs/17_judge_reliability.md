# Phase 7: Judge Reliability

版本：v1.0  
日期：2026-02-07

## 1. 目标

评估阶段不依赖手工 reward，而使用 LLM 评估 + 反思反馈，并显式度量可靠性。

## 2. 背景证据

- MT-Bench 显示 GPT-4 judge 与人类/Chatbot Arena 在对话评估中一致性较高（论文报告 >80%）。
- JudgeBench 指出 LLM judges 在偏置、鲁棒性方面仍有明显弱点。
- 因此系统需要“可用且可校准”的 judge 机制，而非单 judge 黑盒。

## 3. 可靠性架构

`EnsembleJudge = rule + heuristic (+ openai)`

输出：

1. 聚合分数 `score`
2. `last_votes`（逐 judge rationale）
3. `last_agreement`
4. `last_confidence`

聚合逻辑：

- 加权均值得分
- 基于分数方差 + 与均值接近度计算 agreement
- `confidence = 0.5 * score + 0.5 * agreement`

## 4. 实现映射

- `src/graph_agent_automated/infrastructure/evaluation/judges.py`
- `src/graph_agent_automated/infrastructure/evaluation/workflow_evaluator.py`

`ReflectionWorkflowEvaluator` 会把 votes/confidence/agreement 写入 `CaseExecution` 与 `EvaluationSummary`。

## 5. 可靠性监控与阈值

建议阈值：

1. `judge_agreement < 0.55`：触发人工 spot-check。  
2. `confidence` 长期下降：触发 prompt/tool policy 诊断。  
3. 同一 case judge 分歧大：进入对抗样本池。

## 6. 风险与缓解

1. Self-confirmation bias：引入异构 judge（rule + model）。
2. Prompt leakage：固定 judge rubric 版本，禁止被优化器修改。
3. Cost overhead：默认仅在关键阶段启用昂贵模型 judge。

## 7. Phase 7 Gate

- 已有 multi-judge、agreement、confidence、反思闭环。  
Gate 结论：`PASS`。
