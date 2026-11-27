# 多 Agent 出题工作流 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个一次只推进一道题的四 Agent 控制层，能够创建隔离 worktree、分发 Harness 任务、校验结果、冻结输入、使过期结果失效，并在人工审批后发布。

**Architecture:** Python 控制层拥有 manifest、状态机、文件哈希和 Git 操作。四个 Agent 通过严格 JSON 任务与结果协议运行；材料审查与考试质量审查使用独立只读 worktree，主笔使用唯一可写 worktree。

**Tech Stack:** Python 3.11+、`jsonschema`、`pytest`、标准库 `subprocess`、DeepSeek Harness Python SDK、Git。

**Spec:** `docs/specs/2026-11-27-multi-agent-exam-workflow-design.md`

## Global Constraints

- 一次只能有一个活跃的 `question_id`。
- 四个逻辑 Agent：coordinator、author、material-reviewer、quality-reviewer。
- 只有 author 可写题目 worktree；两个 reviewer 使用只读 worktree。
- Git commit、tag、merge、push 只由控制层执行。
- 输入冻结后任何相关文件哈希变化都必须触发 `INPUT_INVALIDATED`。
- API Key 只从环境变量读取，不写入运行文件或 Git。
- 不依赖 DeepSeek Harness Agent Teams 提供文件隔离。
- 审查 Agent 返回一次非法 JSON 可重试一次，第二次失败进入 `BLOCKED`。
- 主笔最多自动修复三轮，之后进入人工处理。
- 所有文档写入 `docs/`；`runs/` 不提交 Git。

---

### Task 1: 项目包与测试基线

**Files:**
- Create: `pyproject.toml`
- Create: `src/exam_agents/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Produces: importable package `exam_agents`
- Produces: pytest root configuration

- [ ] **Step 1: 写包导入测试**

```python
from exam_agents import __version__


def test_version_is_defined():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_package.py -v`

Expected: FAIL，因为包尚不存在。

- [ ] **Step 3: 创建最小包和 pyproject**

```toml
[project]
name = "exam-agents"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "jsonschema>=4.23,<5",
  "deepseek-harness-sdk>=0.2.3a2",
]

[project.optional-dependencies]
dev = ["pytest>=8.3,<9"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pip install -e '.[dev]'`，随后 `pytest tests/test_package.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/exam_agents/__init__.py tests/conftest.py tests/test_package.py
git commit -m "chore: initialize exam agent control plane"
```

---

### Task 2: JSON Schema 与校验器

**Files:**
- Create: `schemas/task.schema.json`
- Create: `schemas/result.schema.json`
- Create: `schemas/manifest.schema.json`
- Create: `src/exam_agents/schema.py`
- Create: `tests/test_schema.py`

**Interfaces:**
- Produces: `validate_task(data: dict) -> None`
- Produces: `validate_result(data: dict) -> None`
- Produces: `validate_manifest(data: dict) -> None`
- Raises: `SchemaValidationError(message: str)`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from exam_agents.schema import SchemaValidationError, validate_result


def test_rejects_unknown_result_status():
    with pytest.raises(SchemaValidationError):
        validate_result(
            {
                "task_id": "task-1",
                "status": "probably_ok",
                "checked_items": [],
                "findings": [],
                "commands_run": [],
                "artifacts_written": [],
                "output_hashes": {},
            }
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_schema.py -v`

Expected: FAIL，因为校验器不存在。

- [ ] **Step 3: 定义三个 schema**

`result.schema.json` 必须要求统一结果字段；`status` 枚举为 `passed|changes_required|blocked`；finding 的 `severity` 为 `high|medium|low`；`classification` 为 `material_defect|specification_gap|intentional_anomaly|model_error`。

`task.schema.json` 必须要求 `task_id`、`question_id`、`stage`、`base_commit`、`skill_ref`、`input_manifest_hash`、`required_files`、`instructions`、`output_schema`。

`manifest.schema.json` 必须要求 `question_id`、`project_root`、`stage`、`base_commit`、`artifact_hashes`、`reviews`、`approvals`、`repair_rounds`、`active`。

- [ ] **Step 4: 实现 schema 加载与错误包装**

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator


class SchemaValidationError(ValueError):
    pass


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _validate(name: str, data: dict) -> None:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        raise SchemaValidationError(errors[0].message)
```

- [ ] **Step 5: 补全合法与非法测试并运行**

Run: `pytest tests/test_schema.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add schemas src/exam_agents/schema.py tests/test_schema.py
git commit -m "feat: add task result and manifest schemas"
```

---

### Task 3: Manifest 状态机

**Files:**
- Create: `src/exam_agents/state.py`
- Create: `src/exam_agents/run_store.py`
- Create: `tests/test_state.py`
- Create: `tests/test_run_store.py`

**Interfaces:**
- Produces: `Stage` enum with all spec states
- Produces: `transition(current: Stage, event: str) -> Stage`
- Produces: `RunStore.create(question_id: str, project_root: Path, base_commit: str) -> dict`
- Produces: `RunStore.load(question_id: str) -> dict`
- Produces: `RunStore.save(manifest: dict) -> None`
- Produces: `RunStore.active_question() -> str | None`

- [ ] **Step 1: 为非法状态跳转写失败测试**

```python
import pytest

from exam_agents.state import Stage, TransitionError, transition


def test_cannot_skip_input_freeze():
    with pytest.raises(TransitionError):
        transition(Stage.INPUT_DRAFT, "output_started")
```

- [ ] **Step 2: 实现状态枚举和显式转移表**

只允许设计文档中的主路径、`CHANGES_REQUIRED` 回退、`BLOCKED`、`INPUT_INVALIDATED`、`CONFLICT` 和 `HUMAN_DECISION_REQUIRED`。

- [ ] **Step 3: 写单活跃题目和原子保存测试**

```python
def test_only_one_active_question(tmp_path):
    store = RunStore(tmp_path)
    store.create("q1", tmp_path / "q1", "abc")
    with pytest.raises(RuntimeError):
        store.create("q2", tmp_path / "q2", "def")
```

- [ ] **Step 4: 实现原子写入**

先写同目录临时文件，调用 `os.replace`；使用 `fcntl.flock` 锁住 `runs/.active.lock`，保证单进程和跨进程互斥。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_state.py tests/test_run_store.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/exam_agents/state.py src/exam_agents/run_store.py tests/test_state.py tests/test_run_store.py
git commit -m "feat: add manifest state machine"
```

---

### Task 4: Harness 抽象与 Mock Driver

**Files:**
- Create: `src/exam_agents/harness.py`
- Create: `src/exam_agents/mock_harness.py`
- Create: `tests/test_mock_harness.py`

**Interfaces:**
- Produces: `HarnessRunner` Protocol with `run(task: dict, workspace: Path, home: Path, timeout_seconds: int) -> dict`
- Produces: `MockHarnessRunner(responses: dict[str, dict])`
- Mock 根据 `task["stage"]` 返回对应 result，并记录调用。

- [ ] **Step 1: 写 mock 返回结构测试**

```python
def test_mock_returns_stage_result(tmp_path):
    runner = MockHarnessRunner({"design": RESULT})
    assert runner.run(TASK, tmp_path, tmp_path / "home", 10) == RESULT
```

- [ ] **Step 2: 实现 Protocol 和 deterministic mock**

Mock 必须复制响应后再返回，不允许调用方修改内部配置。

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_mock_harness.py -v`

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add src/exam_agents/harness.py src/exam_agents/mock_harness.py tests/test_mock_harness.py
git commit -m "feat: add harness abstraction and mock driver"
```

---

### Task 5: 任务分发与结果提交

**Files:**
- Create: `src/exam_agents/dispatch.py`
- Create: `src/exam_agents/submit.py`
- Create: `tests/test_dispatch.py`
- Create: `tests/test_submit.py`

**Interfaces:**
- Produces: `dispatch_stage(run_dir: Path, agent: str, stage: str, instructions: str, required_files: list[str]) -> Path`
- Produces: `submit_result(run_dir: Path, expected_task_id: str, result: dict) -> dict`
- `submit_result` validates schema, task id, allowed reviewer/author permissions, and persists to `reports/<agent>/<task_id>.json`.

- [ ] **Step 1: 写任务包字段测试**

验证生成任务包含 spec 中全部必填字段，且输出路径为 `runs/<qid>/tasks/<task_id>.json`。

- [ ] **Step 2: 写非法结果拒绝测试**

覆盖结果 status 非法、task_id 不匹配、reviewer 返回 `artifacts_written` 非空。

- [ ] **Step 3: 实现 dispatch 和 submit**

任务 ID 使用 `task-<stage>-<uuid4().hex[:12]>`。写入 JSON 时使用原子替换。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_dispatch.py tests/test_submit.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/exam_agents/dispatch.py src/exam_agents/submit.py tests/test_dispatch.py tests/test_submit.py
git commit -m "feat: add task dispatch and result submission"
```

---

### Task 6: Git worktree 与草稿提交

**Files:**
- Create: `src/exam_agents/gitops.py`
- Create: `tests/test_gitops.py`

**Interfaces:**
- Produces: `GitRepo(root: Path)`
- Produces: `.commit_all(message: str) -> str`
- Produces: `.create_worktree(name: str, target: Path, ref: str = "HEAD") -> Path`
- Produces: `.remove_worktree(target: Path) -> None`
- Produces: `.tag(name: str, ref: str) -> None`
- Produces: `.merge_ff_only(ref: str) -> None`

- [ ] **Step 1: 用临时 Git 仓库写失败测试**

验证：

- 从 commit 创建两个 worktree。
- 两个 worktree 初始文件相同。
- 修改 author 后提交，review worktree 不自动变化。
- 非 fast-forward merge 被拒绝。

- [ ] **Step 2: 实现受控 git subprocess**

所有命令使用参数列表，不拼接 shell 字符串；设置 `GIT_TERMINAL_PROMPT=0`；失败时抛出包含命令类型的 `GitOperationError`，不记录凭据。

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_gitops.py -v`

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add src/exam_agents/gitops.py tests/test_gitops.py
git commit -m "feat: add controlled git worktree operations"
```

---

### Task 7: 输入哈希、冻结和失效

**Files:**
- Create: `src/exam_agents/freeze.py`
- Create: `tests/test_freeze.py`

**Interfaces:**
- Produces: `hash_paths(root: Path, paths: list[str]) -> dict[str, str]`
- Produces: `freeze_inputs(run_dir: Path, workspace: Path, manifest: dict) -> dict`
- Produces: `verify_hashes(run_dir: Path, workspace: Path, manifest: dict) -> bool`
- Produces: `invalidate_if_changed(...) -> Stage`

- [ ] **Step 1: 写哈希稳定性测试**

同一内容哈希相同；文件变化后哈希变化；删除文件后 verify 返回 `False`。

- [ ] **Step 2: 冻结文件范围**

冻结范围固定为：

```text
input/**
docs/reviews/1-题目说明.md
docs/reviews/2-题目要求.md
docs/reviews/难度设计检查.md
docs/reviews/数据真实性设计检查.md
```

- [ ] **Step 3: 写入 manifest 并生成冻结记录**

`freeze_inputs` 只写 `runs/<qid>/gates/input-freeze.json` 和 manifest 哈希，不修改题目文件。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_freeze.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/exam_agents/freeze.py tests/test_freeze.py
git commit -m "feat: freeze inputs and invalidate stale results"
```

---

### Task 8: DeepSeek Harness SDK Adapter

**Files:**
- Create: `src/exam_agents/deepseek_runner.py`
- Create: `tests/test_deepseek_runner.py`
- Create: `configs/deepseek.example.json`

**Interfaces:**
- Produces: `DeepSeekRunner(config: DeepSeekConfig)`
- Implements: `HarnessRunner.run(...)`
- Lazily imports `deepseek_harness.DeepSeekHarness`
- Reads API key from `DEEPSEEK_API_KEY`

- [ ] **Step 1: 用 fake SDK 写 adapter 测试**

通过注入 `sdk_factory` 模拟 `DeepSeekHarness`，验证：

- 每个 Agent 使用传入的 workspace 和独立 `dsh_home`。
- profile 默认使用 `sdk`，不使用 `sdk-minimal`。
- 最终响应必须是 JSON object，否则抛 `InvalidAgentOutputError`。
- API Key 缺失时立即失败，不启动 Harness。

- [ ] **Step 2: 实现 adapter**

默认配置：

```json
{
  "profile": "sdk",
  "provider": "deepseek-official",
  "model": "deepseek-v4-flash",
  "max_tokens": 49152,
  "patches": [],
  "timeout_seconds": 1800
}
```

- [ ] **Step 3: 运行离线测试**

Run: `pytest tests/test_deepseek_runner.py -v`

Expected: PASS，不访问网络。

- [ ] **Step 4: 增加不自动运行的真实 SDK smoke test**

测试标记 `@pytest.mark.real_harness`，默认跳过，只有显式设置 `RUN_REAL_HARNESS=1` 才运行。

- [ ] **Step 5: 提交**

```bash
git add src/exam_agents/deepseek_runner.py tests/test_deepseek_runner.py configs/deepseek.example.json
git commit -m "feat: add DeepSeek Harness runner adapter"
```

---

### Task 9: CLI 命令

**Files:**
- Create: `src/exam_agents/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces CLI: `exam-agents init-run`
- Produces CLI: `exam-agents dispatch-stage`
- Produces CLI: `exam-agents submit-result`
- Produces CLI: `exam-agents freeze-inputs`
- Produces CLI: `exam-agents verify-hashes`
- Produces CLI: `exam-agents status`

- [ ] **Step 1: 写 CLI exit code 测试**

成功操作返回 0；schema 错误、状态跳转错误和单活跃冲突返回非 0，并输出结构化 JSON 错误。

- [ ] **Step 2: 实现 argparse 子命令**

每个命令只调用对应模块，不复制业务逻辑。`status` 只读。

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_cli.py -v`

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add src/exam_agents/cli.py pyproject.toml tests/test_cli.py
git commit -m "feat: expose exam agent control commands"
```

---

### Task 10: Mock End-to-End 工作流

**Files:**
- Create: `tests/test_workflow.py`
- Create: `src/exam_agents/workflow.py`

**Interfaces:**
- Produces: `run_mock_workflow(project_root: Path, question_id: str) -> dict`
- Uses only local Git and `MockHarnessRunner`

- [ ] **Step 1: 写完整成功路径测试**

流程覆盖：

```text
INIT
→ DESIGN_DRAFT
→ DESIGN_PASSED
→ INPUT_DRAFT
→ INPUT_REVIEW
→ INPUT_FROZEN
→ OUTPUT_DRAFT
→ OUTPUT_REVIEW
→ OUTPUT_PASSED
→ HUMAN_REVIEW
→ RELEASED
```

- [ ] **Step 2: 写失败分支测试**

覆盖：

- 材料审查返回 high finding 后回到 `CHANGES_REQUIRED`。
- 修改输入后 `verify_hashes` 返回失败并进入 `INPUT_INVALIDATED`。
- reviewer 返回 `blocked` 两次后进入 `BLOCKED`。
- 缺少人工审批时 `release` 拒绝。

- [ ] **Step 3: 实现编排服务**

编排只负责调用状态机、dispatch、runner、submit、freeze 和 Git，不包含领域出题逻辑。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_workflow.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/exam_agents/workflow.py tests/test_workflow.py
git commit -m "test: cover end-to-end multi-agent workflow"
```

---

### Task 11: 运行文档与最终验证

**Files:**
- Create: `docs/reviews/2026-11-27-implementation-verification.md`
- Create: `docs/运行说明.md`

- [ ] **Step 1: 写运行说明**

说明安装、环境变量、初始化一次运行、四个 Agent 的任务目录、冻结、恢复和发布命令；明确不能使用 `sdk-minimal`，以及开发者预览风险。

- [ ] **Step 2: 运行完整验证**

```bash
python -m pip install -e '.[dev]'
pytest -q
python -m exam_agents.cli --help
git diff --check
```

Expected: 所有测试通过，无空白错误。

- [ ] **Step 3: 记录验证结果**

在 `docs/reviews/2026-11-27-implementation-verification.md` 记录测试数量、通过结果、未运行的真实 Harness 测试和原因。

- [ ] **Step 4: 提交**

```bash
git add docs
git commit -m "docs: add workflow operation and verification guide"
```

