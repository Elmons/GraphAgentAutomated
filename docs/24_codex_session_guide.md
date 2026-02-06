# Codex Session Guide (Mandatory)

最后更新：2026-02-06

本文件是给“新会话 Codex”的强制操作指南。  
目标：避免重复犯错、避免误判“已生产化”。

## 1. 会话启动顺序（必须按顺序）

1. 阅读 `docs/09_execution_todo.md`。  
2. 阅读 `README.md` 中最新接口与脚本入口。  
3. 检查工作区：`git status --short`。  
4. 快速健康检查：`./.venv/bin/pytest -q`。  
5. 向用户确认你理解的当前状态（已完成/未完成/下一步）。

## 2. 开发原则

1. 不允许把 mock 结果当作生产结论。  
2. 不允许跳过 P0 阻塞项直接宣称“生产级”。  
3. 任何“目标变化/优先级变化”先更新 `docs/09_execution_todo.md`。  
4. 每次改动必须可复现（命令、输出、工件路径清晰）。

## 3. 当前任务优先级（摘自 TODO）

1. P0：安全/事务/一致性/runtime 可靠性修复。  
2. P1：鉴权、队列、幂等、观测。  
3. P2：真实 runtime + 真实 judge + parity 达标验证。

## 4. 每次交付最少内容

1. 改了哪些文件。  
2. 运行了哪些验证命令。  
3. 结果是什么。  
4. 下一会话第一步是什么。  
5. TODO 哪些条目标记变更。
6. 本次 commit hash 与 commit message。  
7. push 结果（目标分支与是否成功）。

## 5. 禁止语句

在满足 Production DoD 前，禁止输出以下判断：

1. “已经生产级”  
2. “接近 100% 把握可用”  
3. “真实效果已证明”

## 6. 推荐命令模板

```bash
git status --short
./.venv/bin/pytest -q
./.venv/bin/ruff check src tests scripts
./.venv/bin/alembic upgrade head
git add -A
git commit -m "<scope>: <summary>"
git push origin master
```
