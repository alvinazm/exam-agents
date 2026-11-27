# 第一版实施验证

## 验证范围

- Task、Result、Manifest JSON Schema
- 单活跃题目状态机
- 四 Agent 配置和权限
- Mock Harness 任务交接
- Git worktree 草稿隔离
- 输入冻结与失效
- DeepSeek Harness SDK adapter
- CLI 与 Mock 端到端流程

## 离线验证

执行：

```bash
uv sync --extra dev
uv run --with pytest pytest -q
uv run exam-agents --help
git diff --check
```

离线测试不访问 DeepSeek API。

## 真实 Harness

2026-11-27 已使用独立 Harness home 和最小请求完成真实 API smoke test：

- provider：`deepseek-official`
- model：`deepseek-v4-flash`
- profile：`sdk`
- SDK：`deepseek-harness-sdk 0.2.2rc2`
- `finish_reason`：`completed`
- 返回内容：`{"status":"ok","check":"deepseek-api"}`

普通自动测试仍不调用真实 API，避免每次测试消耗配额。session 日志保存在被 Git 忽略的 `runs/` 中，不提交凭据或会话内容。

## 结果

验证结果：

- `uv sync --extra dev`：成功
- `uv run pytest -q`：38 passed
- `uv run exam-agents --help`：成功显示六个命令
- `python3 -m compileall -q src scripts`：通过
- JSON 配置和 Schema 解析：通过
- `git diff --check`：通过

真实 API 已完成最小连通性和结构化返回验证。当前结果证明控制层、权限配置、Mock 编排、Git 隔离和 SDK 基础调用可用，但不证明四个真实 Agent 在完整题目上的协作质量。
