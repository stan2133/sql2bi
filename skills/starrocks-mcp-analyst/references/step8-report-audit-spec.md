# Step 8 Reference: Report Audit Specification

## 目的
在发布最终结论前，对洞察报告做可追溯性、表述合规性和可执行性审计。
Step 8 是发布闸门，不是可选步骤。

## 输入
- `insight_package`（Step 7）
- `sql_audit_report`（Step 6）
- `audit/<session_id>/sql.md`
- `audit/<session_id>/sql/*.sql`
- `reports/<theme>/<version>/report.md`
- `reports/<theme>/<version>/analysis_trace.md`
- `reports/<theme>/<version>/report.json`
- `reports/<theme>/<version>/evidence_index.json`
- `reports/<theme>/<version>/metadata.json`

## 输出
- `report_audit_report`
- `report_audit`: `PASS|WARN|FAIL`

## 语言要求（必选）
审计内容默认中文（`zh-CN`）：
- 审计结论、问题描述、修复建议、剩余风险均使用中文
- SQL 原文保持原样，不做翻译

## 审计维度
1. 证据可追溯审计
2. 因果表述审计
3. 口径与假设披露审计
4. 建议动作一致性审计
5. 风险与不确定性审计
6. 审计产物完整性审计
7. 报告版本与主题归档审计

## 1) 证据可追溯审计
必检项：
- 每条 finding 都有 `supporting_query_ids`
- 每个 `query_id` 在 `sql_audit_report.query_audits` 中可找到
- 每个 `query_id` 在 `audit/<session_id>/sql.md` 和 `sql/<query_id>.sql` 中可找到
- 关键数字（baseline/current/delta）可与查询结果对上

失败条件：
- 任一核心结论无法追溯到 SQL -> `critical`

## 2) 因果表述审计
必检项：
- `type=correlation` 的假设不得写成因果结论
- 因果措辞（例如“导致/因为/造成”）仅可用于 `causal_candidate` 且有设计证据
- 报告中必须区分“事实”和“解释”

失败条件：
- 将相关性当因果发布 -> `critical`

## 3) 口径与假设披露审计
必检项：
- 指标定义、时间窗口、范围、过滤条件明确
- `provisional` 定义必须在正文或风险区显式标注
- 样本限制、延迟、缺失字段等必须披露

失败条件：
- 核心口径缺失或误导 -> `high`

## 4) 建议动作一致性审计
必检项：
- 每个行动项有对应 finding
- 行动优先级（P0/P1/P2）与影响和紧急度一致
- 行动 owner 与时间窗明确

失败条件：
- 行动与证据链断裂 -> `high`

## 5) 风险与不确定性审计
必检项：
- 输出 `residual_risks`
- 置信度与 Step 6 风险一致（存在高风险未解决时不得给 `high`）
- 风险对决策影响被描述

失败条件：
- 高风险被隐藏或置信度虚高 -> `high`

## 6) 审计产物完整性审计
目录必须存在：
```text
audit/<session_id>/
  sql.md
  sql/
  sql_audit_report.json
```

`sql.md` 必须包含：
- 全部执行过的 `query_id`
- 每条 SQL 的完整文本
- 参数、状态、耗时、行数

失败条件：
- `sql.md` 不存在或缺少完整 SQL -> `critical`
- 报告引用的任一 `query_id` 未落盘 -> `critical`

## 7) 报告版本与主题归档审计
必检项：
- 报告已保存到 `reports/<theme>/<version>/`
- `theme` 不为空且符合 slug 规则（小写+短横线）
- `version` 不为空且符合 `vYYYYMMDD.NNN`
- `metadata.json` 中 `session_id` 与审计目录一致
- `evidence_index.json` 中 `finding_id -> query_id` 可映射到 `audit/<session_id>/sql.md`

失败条件：
- 未按 `theme + version` 落盘 -> `critical`
- 映射关系不完整 -> `high`

## 严重性与门禁规则
严重性分级：
- `critical`
- `high`
- `medium`
- `low`

门禁规则：
- 任一 `critical` -> `report_audit = FAIL`
- 无 `critical` 且 `high` >= 2 -> `report_audit = WARN`
- 其余 -> `report_audit = PASS`

## 失败处理规则
当 `report_audit = FAIL`：
- 禁止发布“最终结论版”报告
- 仅允许发布“部分可验证事实”
- 返回修复项清单（按优先级）

当 `report_audit = WARN`：
- 可发布，但必须带风险声明和置信度降级

## 输出模板
```json
{
  "report_audit_report": {
    "language": "zh-CN",
    "session_id": "",
    "sql_audit": "PASS|WARN|FAIL",
    "report_audit": "PASS|WARN|FAIL",
    "checks": {
      "traceability": "PASS|WARN|FAIL",
      "causality": "PASS|WARN|FAIL",
      "disclosure": "PASS|WARN|FAIL",
      "action_alignment": "PASS|WARN|FAIL",
      "risk_alignment": "PASS|WARN|FAIL",
      "artifact_completeness": "PASS|WARN|FAIL",
      "theme_version_storage": "PASS|WARN|FAIL"
    },
    "violations": [
      {
        "severity": "critical|high|medium|low",
        "category": "traceability|causality|disclosure|action_alignment|risk_alignment|artifact",
        "finding_id": "",
        "query_id": "",
        "message": "",
        "remediation_hint": ""
      }
    ],
    "artifacts": {
      "sql_md_path": "audit/<session_id>/sql.md",
      "sql_dir_path": "audit/<session_id>/sql",
      "sql_audit_report_path": "audit/<session_id>/sql_audit_report.json",
      "report_root": "reports/<theme>/<version>",
      "report_md_path": "reports/<theme>/<version>/report.md",
      "analysis_trace_path": "reports/<theme>/<version>/analysis_trace.md",
      "report_json_path": "reports/<theme>/<version>/report.json",
      "evidence_index_path": "reports/<theme>/<version>/evidence_index.json",
      "metadata_path": "reports/<theme>/<version>/metadata.json"
    },
    "residual_risks": [],
    "publish_policy": "block_final|allow_with_warning|allow"
  }
}
```

## 示例
```json
{
  "report_audit_report": {
    "language": "zh-CN",
    "session_id": "session_20260305_001",
    "sql_audit": "WARN",
    "report_audit": "WARN",
    "checks": {
      "traceability": "PASS",
      "causality": "PASS",
      "disclosure": "WARN",
      "action_alignment": "PASS",
      "risk_alignment": "WARN",
      "artifact_completeness": "PASS",
      "theme_version_storage": "PASS"
    },
    "violations": [
      {
        "severity": "high",
        "category": "disclosure",
        "finding_id": "F2",
        "query_id": "Q_H2_EVIDENCE",
        "message": "报告未显式说明该指标定义为 provisional。",
        "remediation_hint": "在结论段和风险段补充 provisional 标识及影响范围。"
      }
    ],
    "artifacts": {
      "sql_md_path": "audit/session_20260305_001/sql.md",
      "sql_dir_path": "audit/session_20260305_001/sql",
      "sql_audit_report_path": "audit/session_20260305_001/sql_audit_report.json",
      "report_root": "reports/growth-acquisition/v20260305.001",
      "report_md_path": "reports/growth-acquisition/v20260305.001/report.md",
      "analysis_trace_path": "reports/growth-acquisition/v20260305.001/analysis_trace.md",
      "report_json_path": "reports/growth-acquisition/v20260305.001/report.json",
      "evidence_index_path": "reports/growth-acquisition/v20260305.001/evidence_index.json",
      "metadata_path": "reports/growth-acquisition/v20260305.001/metadata.json"
    },
    "residual_risks": ["近24小时归因数据仍在回补，结论置信度上限为 medium"],
    "publish_policy": "allow_with_warning"
  }
}
```
