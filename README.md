# GraphAgentAutomated

独立的智能体自动生成系统：动态数据合成 + prompt/tool/topology 联合优化 + LLM 评估闭环。

`chat2graph` 仅作为外部 runtime 使用，不修改其内部实现。

## 文档

1. `docs/00_research_survey.md` 调研
2. `docs/01_requirements.md` 需求分析
3. `docs/02_system_design.md` 系统设计
4. `docs/03_test_design.md` 测试设计
5. `docs/04_implementation.md` 实现说明

## 开发（uv）

```bash
uv sync --all-extras
uv run pytest
```

## 配置

使用 `pydantic_settings` 统一管理环境变量，见 `.env.example`。
