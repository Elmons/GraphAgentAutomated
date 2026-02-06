# GraphAgentAutomated Local Agent Rules

所有新会话的 Codex 在开始任何代码修改前，必须先完成：

1. 阅读 `docs/09_execution_todo.md`（主 TODO，目标与状态基准）。  
2. 阅读 `docs/24_codex_session_guide.md`（会话执行与交接规则）。  
3. 运行最小检查：`git status --short`、`./.venv/bin/pytest -q`。  
4. 在首条工作回复中明确：当前目标、已完成、未完成、下一步。

补充约束：

1. 未完成 `docs/09_execution_todo.md` 中 Production DoD 前，不得宣称“生产级完成”。  
2. 若发现 TODO 与代码不一致，先更新 TODO 再继续开发。  
3. 会话结束必须更新 TODO 的进度与下一步。
