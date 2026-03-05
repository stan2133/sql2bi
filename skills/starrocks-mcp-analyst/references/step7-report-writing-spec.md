# Step 7 Supplement: Report Writing And Analysis Reasoning Specification

## 目的
把分析结果写成可决策、可复核、可升级的业务报告。
该规范补充 Step 7，强调“分析思路显式化”与“报告写作质量”。

## 输入
- `insight_package`（Step 7 主流程）
- `hypothesis_test_plan`（Step 4）
- `sql_audit_report`（Step 6）
- `report_audit_report`（Step 8，可在发布前回填）
- `audit/<session_id>/sql.md`

## 输出
- 面向业务的 `report.md`（中文）
- 面向系统的 `report.json`
- `analysis_trace.md`（分析思路链路）

## 语言要求
- 默认中文（`zh-CN`）
- 专有名词保留英文可接受
- SQL 保持原文

## 分析思路链（必选）
必须把“如何得到结论”写清楚，至少包含：
1. 问题定义：业务决策问题与目标指标
2. 假设列表：H1/H2/... 的提出依据
3. 验证过程：每个假设对应的查询证据、反证、对账
4. 结论归因：哪些假设被支持，贡献度多少
5. 不确定性：哪些假设未证实、哪些风险未解除

推荐输出到 `analysis_trace.md` 的结构：
- `问题 -> 假设 -> 证据 -> 反证 -> 结论 -> 行动`

## 报告结构（report.md）
按固定章节顺序写作：
1. 执行摘要（3-7行）
2. 分析范围与口径
3. 关键发现（按影响度排序）
4. 影响测算（含区间）
5. 行动建议（P0/P1/P2）
6. 风险与限制
7. 附录（query_id 索引、审计路径）

每条关键发现必须包含：
- `finding_id`
- 一句话结论（事实）
- 证据摘要（query_id + 数字）
- 业务解释（明确“可能/已验证”）
- 影响值与置信度

## 写作质量规则
- 先事实后解释，禁止先下结论再补证据
- 每段关键判断至少绑定一个 `query_id`
- 避免空泛形容词（如“明显”“大幅”），必须给数值
- 使用一致时间口径（例如“2026-02-01 至 2026-02-28”）
- 对 `provisional` 指标必须加醒目标记

## 因果表述规则
- `correlation` 仅用“相关/伴随/同向变化”措辞
- 仅 `causal_candidate` 且证据充分时使用“可能导致”
- 没有实验或准实验证据，禁止“确定导致”

## 影响测算写法
每个 finding 的影响段至少包含：
- `基准值`、`当前值`、`变化值`、`变化率`
- `解释贡献度`（例如 44%）
- `影响区间`（低/中/高）
- 区间来源（容差、数据风险、延迟）

## 行动建议写法
每条行动建议必须具备：
- `owner_role`
- `action_statement`
- `time_horizon`
- `expected_impact`
- `trigger_metric`（后续跟踪指标）

## report.json 建议结构
```json
{
  "language": "zh-CN",
  "theme": "",
  "version": "",
  "session_id": "",
  "decision_summary": "",
  "scope": {
    "time_window": "",
    "filters": []
  },
  "findings": [],
  "actions": [],
  "risks": [],
  "artifacts": {
    "report_md_path": "",
    "analysis_trace_path": "",
    "sql_md_path": ""
  }
}
```

## 发布前自检清单
1. 报告是否完整覆盖执行摘要到附录
2. 每条 finding 是否有 query_id
3. 结论是否与 Step 6/8 审计状态一致
4. 是否明确保存了本地路径（theme + version）
