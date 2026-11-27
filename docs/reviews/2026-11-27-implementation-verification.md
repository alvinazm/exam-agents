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

真实 Harness 测试未自动执行。运行前必须设置 `DEEPSEEK_API_KEY`，并显式启用真实测试标记。该限制避免普通测试消耗 API 配额，也避免未经确认访问外部服务。

## 结果

验证结果：

- `uv sync --extra dev`：成功
- `uv run pytest -q`：37 passed
- `uv run exam-agents --help`：成功显示六个命令
- `python3 -m compileall -q src scripts`：通过
- JSON 配置和 Schema 解析：通过
- `git diff --check`：通过

真实 DeepSeek API 调用未执行，因此当前结果证明控制层、权限配置、Mock 编排和 Git 隔离逻辑可用，不证明外部模型在实际题目上的表现。
