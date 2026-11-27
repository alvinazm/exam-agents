# 真实多 Agent 工作流试跑记录

## 运行信息

- 日期：2026-11-27
- question_id：`smoke-20261127`
- 题目源：`/Users/azm/MyProject/rubrics-test3` 的一次性本地副本
- 源提交：`0c6c188`
- Agent：coordinator、author、material-reviewer、quality-reviewer
- 模型：`deepseek-v4-flash`
- Harness profile：`sdk`
- 结果阶段：`CHANGES_REQUIRED`
- 修复轮次：1
- 原题目仓库未被修改

## 已验证的链路

1. coordinator 以只读权限检查 manifest、worktree、单活跃锁和阶段顺序，返回 `passed`。
2. author 实际读取 `rubrics-growth-exam`，执行难度、数据真实性、Query 和文风校验。
3. author 修改难度设计、数据真实性设计、经营规则、题目要求和题目说明，并生成 draft commit。
4. 控制层从 input draft commit 创建两个独立审查 worktree。
5. material-reviewer 与 quality-reviewer 并行运行。
6. 两个审查 worktree 均未出现文件修改，只读边界生效。
7. 两名 reviewer 返回 `changes_required` 后，控制层把运行状态改为 `CHANGES_REQUIRED`，没有冻结输入或生成 output。

## 材料审查问题

| ID | 严重度 | 分类 | 问题 |
| --- | --- | --- | --- |
| F-01 | 高 | 模型错误 | answer2 的计划试用量和主推排期超过相关 SKU 可用库存，未写明补货或受阻对象 |
| F-02 | 中 | 模型错误 | 待上市商品的 108 件库存早于上市日到期，answer4 未登记，answer3 未说明上市时仅 41 件可用 |
| F-03 | 中 | 规格缺口 | 零历史销量 SKU 的库存覆盖与补货规则未定义 |
| F-04 | 中 | 规格缺口 | answer2 的 `campaign_offer` 没有合法枚举，也未定义与 answer1 `offer_type` 的关系 |
| F-05 | 中 | 模型错误 | 多条活动计划未引用主推 SKU 库存依据，部分计划试用量超过可用库存 |

## 考试质量审查问题

| ID | 严重度 | 分类 | 问题 |
| --- | --- | --- | --- |
| QR-01 | 高 | 模型错误 | answer2 使用了未定义的 `复购管理`，与 answer1 和规则中的订阅首单不一致 |
| QR-02 | 高 | 材料缺陷 | 生成器仍保留旧规则文本和硬编码，重新生成会回退已修复内容 |
| QR-03 | 高 | 规格缺口 | 没有三模型产物和评分分布，无法判断实测难度门槛 |
| QR-04 | 中 | 模型错误 | answer4 有 5 条 `impact_if_resolved` 填 `NA`，不符合补齐后影响说明 |
| QR-05 | 中 | 规格缺口 | C-22 声称检查旧评审与现行审批，但材料中没有具体旧评审记录 |
| QR-06 | 中 | 规格缺口 | C-18 声称简单平均会翻转目标结论，但三种算法均低于 20%，只会改变数值 |
| QR-07 | 中 | 规格缺口 | `campaign_offer` 未在交付契约中定义，校验器和 Rubrics 也未覆盖 |

## 结论

真实 API、skill 加载、四 Agent 配置、并发审查、draft commit 和问题回退链路均已跑通。当前失败来自题目内容质量门槛，不是基础设施故障。

这次试跑使用的是已经出完的 `rubrics-test3` 副本，因此只能验证工作流集成，不能证明系统可以从零生产一道新题。
