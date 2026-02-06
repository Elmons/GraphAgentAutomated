# Phase 12: Top-conference Idea Drop (RCDS)

版本：v1.0  
日期：2026-02-07

## 1. Idea 名称

`RCDS` (Reliability-Calibrated Dynamic Search for Graph Agent Automation)

一句话：  
在图智能体自动生成中，把“可证伪实验矩阵”直接编码进优化系统，并在搜索目标中联合惩罚
`judge 不确定性` 与 `train/val 泛化间隙`，降低虚高候选被部署的概率。

## 2. 对顶会价值的核心点

1. 方法创新：不是只调 prompt，而是对 `prompt + tool + topology + judge reliability` 做联合搜索。  
2. 可信评估：把评估可靠性信号直接进入目标函数，而非仅做离线分析。  
3. 可证伪与可复现：baseline/ablation 通过 `profile` 进入同一 API 路径，避免“论文矩阵与系统实现脱节”。  
4. 工程闭环：从生成、搜索、评估、持久化到实验脚本全部打通。

## 3. 已实现的关键机制

1. `profile` 控制矩阵（baseline + ablation）  
   - 代码：`src/graph_agent_automated/domain/enums.py`、`src/graph_agent_automated/application/profiles.py`
2. 可靠性校准搜索目标  
   - 不确定性惩罚：`uncertainty = (1 - judge_agreement) + score_std`  
   - 泛化间隙惩罚：`max(0, train_score - val_score)`  
   - 代码：`src/graph_agent_automated/infrastructure/optimization/search_engine.py`
3. 可开关的数据合成策略  
   - `dynamic/static`、`hard-negative`、`paraphrase`  
   - 代码：`src/graph_agent_automated/infrastructure/synthesis/dynamic_synthesizer.py`
4. judge 体系可切换（ensemble/single）  
   - 代码：`src/graph_agent_automated/infrastructure/evaluation/judges.py`
5. 实验脚本真实生效  
   - 每个 arm 传递 `profile + seed`  
   - 代码：`scripts/run_experiment_matrix.py`

## 4. 运行入口

1. 启动 API：`uv run uvicorn graph_agent_automated.main:app --reload --port 8008`
2. 跑 baseline：`uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --seeds 3`
3. 跑 baseline + ablation：  
   `uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --seeds 5 --include-ablations`

## 5. 投稿叙事建议

1. 主张：RCDS 在同等预算下提高 holdout/test 稳定性，并降低方差与 regret。  
2. 证据：主结果表 + ablation 表 + judge agreement / gap 相关性分析。  
3. 风险披露：mock 与真实 runtime 结果分布差异需显式报告。
