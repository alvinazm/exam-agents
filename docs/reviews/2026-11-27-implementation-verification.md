# 第一版实施验证

## 验证范围

- Task、Result、Manifest JSON Schema
- 单活跃题目状态机
- 四 Agent 配置和权限
- Mock Harness 任务交接
- Git worktree 草稿隔离
- 输入冻结与失效
- DeepSeek Harness SDK adapter
- 真实四 Agent runner 装配与技能目录注入
- Agent 完整 Result Schema 注入与单次修复重试
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

## 真实多 Agent 试跑

2026-11-27 使用 `rubrics-test3` 的一次性副本完成一次真实四 Agent 试跑。coordinator、author 和两个并行 reviewer 均实际调用成功；由于两名 reviewer 返回共 12 条材料或规格问题，流程正确停在 `CHANGES_REQUIRED`，没有冻结输入或继续生成 output。

详细记录见 `docs/reviews/2026-11-27-real-workflow-smoke.md`。

## 结果

验证结果：

- `uv sync --extra dev`：成功
- `uv run pytest -q`：47 passed
- `uv run exam-agents --help`：成功显示八个命令
- `python3 -m compileall -q src scripts`：通过
- JSON 配置和 Schema 解析：通过
- `git diff --check`：通过

真实 API 和四 Agent 编排已完成一次试跑。当前结果证明控制层、权限配置、Mock 编排、Git 隔离、SDK 调用、skill 加载和问题回退链路可用；试跑使用的是已有题目的副本，因此不证明从零生产新题的协作质量。
