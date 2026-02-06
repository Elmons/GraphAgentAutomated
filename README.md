# GraphAgentAutomated

独立的智能体自动生成系统：动态数据合成 + prompt/tool/topology 联合优化 + LLM 评估闭环。

`chat2graph` 仅作为外部 runtime 使用，不修改其内部实现。

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

## 开发（uv）

```bash
uv sync --all-extras
uv run pytest
uv run python scripts/run_experiment_matrix.py --base-url http://127.0.0.1:8008 --seeds 3
```

## 配置

使用 `pydantic_settings` 统一管理环境变量，见 `.env.example`。
