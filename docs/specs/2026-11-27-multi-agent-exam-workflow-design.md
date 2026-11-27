# 多 Agent 出题协作工作流设计

日期：2026-11-27

## 1. 目标

本系统负责一次推进一道营销增长 Rubrics 题目的完整生命周期：难度设计、数据真实性设计、input 与题目要求生成、材料核查、参考答案与 Rubrics 生成、模型产物评分、最终审批和提交。

系统必须达到以下结果：

- 任何阶段都不能只凭 Agent 自述通过，必须有文件化产物和脚本闸门。
- 主笔不能审查自己的产物，材料审查和考试质量审查使用独立上下文与只读快照。
- 输入冻结后，答案、Rubrics、模型产物和评分绑定同一个文件版本。
- 设计内故意设置的异常继续保留，材料缺陷和难度坑必须分类处理。
- 所有关键过程能通过 manifest、命令记录、文件哈希和审查 JSON 追溯。

## 2. 非目标

- 不支持多道题同时运行。
- 不在第一阶段实现 Web 管理界面。
- 不自动合并冲突，不自动决定审查冲突。
- 不让能力较弱的 Harness 子 Agent 直接承担 Git 合并、tag 或 push。
- 不依赖 DeepSeek Harness 的 Agent Teams 做文件隔离或文件锁。

## 3. 已验证的运行底座

基线为 `deepseek-ai/deepseek-harness` 的开发者预览版本：

- 核验提交：`4b399c39a6d1479cd84ca591b4d7c88e24d38a96`
- 核验版本：`0.2.3-alpha.2`
- 核验日期：2026-11-22

该版本提供 Shell、Python SDK、子 Agent、持久 session、权限预设和实验性 Git worktree。使用时必须考虑以下限制：

- 官方 Agent Teams 共享同一工作目录和文件系统，`writeScopes` 只是提示，不是锁。
- 面向模型的子 Agent 委派工具不接收目录参数；独立目录必须由 Host 显式传入 `cwd`，或使用独立 Harness 进程。
- Git worktree 属于实验能力；在 `workspace-write` 下直接执行 `git add`、`git commit` 需要额外授权 Git 管理目录。
- `sdk-minimal` 不包含子 Agent，并固定使用 `danger-full-access`，不用于本工作流。
- Harness 仍是开发者预览，不能作为不可信任务唯一安全边界。

因此本设计使用 Host 控制层启动独立 session 和独立 worktree，不依赖 Teams 的文件隔离能力。

## 4. 总体架构

系统由四个逻辑 Agent 和一个确定性控制层组成。

| 组件 | 是否写题目文件 | 职责 |
| --- | --- | --- |
| 总协调 Agent | 否 | 读取 manifest、生成任务包、请求人工审批、汇总结果 |
| 出题主笔 Agent | 是，仅 author worktree | 使用 `rubrics-growth-exam` 完成设计、input、Query、答案与 Rubrics |
| 材料审查 Agent | 否 | 独立核查矛盾、遗漏、时间顺序、业务常识、数据真实性、预留坑和材料问题 |
| 考试质量审查 Agent | 否 | 独立核查泄漏、题目精简度、格式、计算、正文一致性、Rubrics 和评分 |
| 控制层脚本 | 只在控制仓库和 Git 元数据中 | 创建 worktree、提交草稿、冻结哈希、调用 Harness、校验 schema、执行最终合并 |

控制层是状态的唯一权威。协调 Agent 可以提出下一步，但只有控制层脚本能推进状态。

## 5. 项目边界

控制仓库使用 `/Users/azm/MyProject/exam-agents`，题目项目作为被管理的独立 Git 仓库。

控制仓库建议结构：

```text
exam-agents/
├── AGENTS.md
├── agents/
│   ├── coordinator/
│   ├── author/
│   ├── material-reviewer/
│   └── quality-reviewer/
├── configs/
├── schemas/
├── scripts/
├── docs/
│   ├── specs/
│   └── reviews/
└── runs/
```

`runs/` 不进入 Git。每次运行使用以下结构：

```text
runs/<question_id>/
├── manifest.json
├── tasks/
├── reports/
├── gates/
├── logs/
├── homes/
└── worktrees/
    ├── author/
    ├── material-review/
    └── quality-review/
```

每个 Agent 使用独立 Harness home，避免共享 session、凭据和设置。Agent 通过任务文件和结果 JSON 交换信息，聊天内容不是交付物。

## 6. 阶段状态机

状态固定为：

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

异常状态：

- `CHANGES_REQUIRED`：审查有高危问题或未处理中危问题。
- `BLOCKED`：脚本不可运行、仓库损坏、连续两次 Agent 执行失败，或材料无法唯一判断。
- `INPUT_INVALIDATED`：冻结输入的文件哈希发生变化。
- `CONFLICT`：修改无法安全合并。
- `HUMAN_DECISION_REQUIRED`：两个审查 Agent 结论冲突，或需要业务取舍。

允许的推进条件：

1. 难度设计文档通过 `check_difficulty_design.py`。
2. 数据真实性设计文档通过 `check_data_realism_design.py`。
3. input 审查与质量审查均为 `passed`，且没有高危或未处理中危问题。
4. 人工确认 input 冻结。
5. 答案和 Rubrics 通过全部结构、计算、泄漏、文风和评分检查。
6. 人工确认最终发布。

## 7. Agent 契约

统一任务包字段：

```json
{
  "task_id": "string",
  "question_id": "string",
  "stage": "design|input|material_review|output_build|quality_review|scoring",
  "base_commit": "string",
  "skill_ref": "rubrics-growth-exam@revision",
  "input_manifest_hash": "string",
  "required_files": [],
  "instructions": "string",
  "output_schema": "string"
}
```

统一结果字段：

```json
{
  "task_id": "string",
  "status": "passed|changes_required|blocked",
  "checked_items": [],
  "findings": [],
  "commands_run": [],
  "artifacts_written": [],
  "output_hashes": {}
}
```

`findings` 必须包含：

- `id`
- `severity`
- `classification`
- `file`
- `field`
- `evidence`
- `required_action`

`classification` 只允许：

- `material_defect`
- `specification_gap`
- `intentional_anomaly`
- `model_error`

审查 Agent 输出 `intentional_anomaly` 时，只能说明它应被保留并验证处理规则，不能要求删除该异常。

## 8. 出题主笔

主笔必须读取并使用 `rubrics-growth-exam`。顺序固定：

1. 难度设计。
2. 数据真实性设计。
3. input 与 Query、题目说明。
4. 参考答案与 Rubrics。
5. 根据审查意见修复并重新生成所有依赖产物。

主笔只能修改 `worktrees/author/`。不得执行最终 merge、tag 或 push。

## 9. 材料审查

材料审查只读。检查范围：

- 跨表主键、日期、公式、单位、状态和汇总。
- 时间顺序，包括支付、导出、退款、截止日和计划期。
- 业务常识与数据真实性。
- 题目要求、题目说明和 input 是否一致。
- 设计内预留坑是否仍存在且可唯一处理。
- `answer4.csv` 的每个材料问题是否真实、准确、无遗漏，且没有把普通建议当成材料问题。
- 材料问题与故意难度是否被正确区分。

## 10. 考试质量审查

考试质量审查只读。检查范围：

- Query 是否只有 `Query`、`Query_Guided`、`Query_Deliverable`。
- Query 是否无独立数字、附件名泄漏、步骤式提示和答案泄漏。
- 题目说明是否符合业务负责人派活语气。
- 所有模型可见 Markdown 的 AI 文风风险。
- output 文件名、表头、枚举、分隔符、精度、空值和对象覆盖。
- 正文、CSV、Rubrics 和评分之间是否一致。
- Rubrics 条数、等级、描述长度、事实来源和覆盖范围。
- 参考答案是否满足当前 Rubrics，并独立复算关键数字。

## 11. Worktree、提交与冻结

每个运行从同一个基准 commit 创建：

- `author`：可写，用于主笔。
- `material-review`：只读，由控制层从最新 draft commit 创建。
- `quality-review`：只读，由控制层从同一 draft commit 创建。

主笔完成一个阶段后，由控制层在题目仓库中提交 `draft-N`。审查 worktree 必须从对应 `draft-N` 创建；主笔的未提交修改不得进入审查快照。

审查发现问题后：

1. 主笔在 author worktree 修复。
2. 控制层提交 `draft-N+1`。
3. 旧审查 worktree、旧报告和旧哈希全部失效。
4. 重新创建两个审查 worktree 并并行审查。

材料审查和质量审查通过且人工批准后，控制层创建 `exam/<question_id>/input-frozen` tag。答案与 Rubrics 只允许在冻结 tag 之上生成。

如果冻结后的 input、Query、题目说明、经营规则、审批记录、Rubrics 依赖文件或生成器发生变化，控制层必须把状态改为 `INPUT_INVALIDATED`，并使旧答案、旧模型结果和旧评分失效。

## 12. 并发与重试

- 同一时间只允许一个活跃 `question_id`。
- 主笔只有一个实例。
- 材料审查和考试质量审查各一个实例，可并行。
- 审查 Agent 超时或返回非法 JSON 时，可在同一快照上重试一次。
- 第二次失败进入 `BLOCKED`。
- 主笔收到审查问题后最多自动修复三轮；第三轮仍有高危问题时停止并请求人工介入。
- 审查结论冲突时进入 `HUMAN_DECISION_REQUIRED`，不自动投票。

## 13. 安全

- DeepSeek API Key 只通过环境变量注入。
- 每个 Agent 使用独立 `dsh_home`。
- 默认禁止网络；外部资料访问必须显式授权。
- 审查 Agent 使用只读沙箱。
- 控制层不把完整用户主目录暴露给 Harness。
- 运行日志不记录凭据、Cookie 或敏感环境变量。
- 最终 Git 操作由控制层在人工审批后执行。

## 14. 测试策略

实现阶段必须覆盖：

- 正常完整流程。
- 难度设计未通过时阻止生成 input。
- 数据真实性设计未通过时阻止生成 input。
- 材料审查发现问题后退回主笔。
- 修复后生成新 draft 并使旧审查失效。
- 两个审查 Agent 并行执行且结果可稳定汇总。
- 非法 Agent JSON 被拒绝。
- 审查 Agent 写题目文件被阻止。
- 输入哈希变化触发 `INPUT_INVALIDATED`。
- 同一时间启动第二道题被拒绝。
- 缺少人工审批时禁止 tag、merge 和 push。
- 冲突审查结论进入 `HUMAN_DECISION_REQUIRED`。

在接入真实 DeepSeek API 前，控制层必须使用 mock harness 完成状态机、权限、退避、超时和失败恢复测试。

## 15. 第一版交付范围

第一版只实现：

- 四个 Agent 的配置和职责说明。
- task、result、manifest 三个 JSON Schema。
- `init_run.py`、`dispatch_stage.py`、`freeze_inputs.py`、`verify_hashes.py`、`submit_result.py`。
- 一个 mock harness 驱动。
- DeepSeek Harness SDK 适配器。
- 正常流程、输入失效、非法结果和审查冲突测试。
- 控制层 git commit、tag、merge 和 push 的服务封装。

Web 界面、多题并发、自动业务裁决和自动降低审查标准不在第一版范围。

## 16. 验收标准

- 一个示例题目可以从 `INIT` 走完到 `RELEASED`。
- 任一脚本闸门失败都不能推进状态。
- 任一审查高危问题都能阻止 input 冻结或最终发布。
- 输入文件任何变化都能触发下游失效。
- 两个审查 Agent 均不能修改题目 worktree。
- Task 和 Result 100% 通过 JSON Schema。
- 所有提交、tag、merge 和 push 都有对应审批记录。
- 最终运行记录能够追溯输入文件哈希、Agent 版本、模型、命令和审查结果。
