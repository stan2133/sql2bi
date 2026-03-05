# Report Storage Specification (Theme + Version)

## 目的
将报告按主题和版本落盘，便于复盘、对比、审计与人工升级。

## 根目录
```text
reports/
  <theme>/
    <version>/
      report.md
      report.json
      analysis_trace.md
      evidence_index.json
      metadata.json
```

## 命名规则
### theme
- 使用小写短横线 slug，例如：
  - `growth-acquisition`
  - `fraud-chargeback`
  - `finance-margin-variance`
  - `supply-chain-otif`
- 主题应反映“业务域 + 核心问题”

### version
- 默认格式：`vYYYYMMDD.NNN`
- 示例：`v20260305.001`
- 同一 `theme` 同一天多次产出，序号递增

## session 关联规则
每个报告版本必须绑定一个 `session_id`，并在 `metadata.json` 中记录：
- `session_id`
- `audit_sql_md_path`（`audit/<session_id>/sql.md`）
- `audit_sql_dir_path`（`audit/<session_id>/sql/`）
- `sql_audit_report_path`
- `report_audit_report_path`

## 必备文件说明
1. `report.md`
   - 面向业务读者的中文报告正文
2. `report.json`
   - 结构化报告，便于程序读取
3. `analysis_trace.md`
   - 分析思路链（问题->假设->证据->结论）
4. `evidence_index.json`
   - `finding_id` 到 `query_id` 的映射表
5. `metadata.json`
   - 版本、时间、作者、session、审计路径、状态

## evidence_index.json 模板
```json
{
  "session_id": "",
  "theme": "",
  "version": "",
  "mappings": [
    {
      "finding_id": "F1",
      "query_ids": ["Q_H1_EVIDENCE", "Q_H1_RECON"],
      "sql_files": [
        "audit/<session_id>/sql/Q_H1_EVIDENCE.sql",
        "audit/<session_id>/sql/Q_H1_RECON.sql"
      ]
    }
  ]
}
```

## metadata.json 模板
```json
{
  "theme": "",
  "version": "",
  "session_id": "",
  "language": "zh-CN",
  "created_at": "",
  "updated_at": "",
  "sql_audit": "PASS|WARN|FAIL",
  "report_audit": "PASS|WARN|FAIL",
  "artifacts": {
    "report_md_path": "reports/<theme>/<version>/report.md",
    "report_json_path": "reports/<theme>/<version>/report.json",
    "analysis_trace_path": "reports/<theme>/<version>/analysis_trace.md",
    "evidence_index_path": "reports/<theme>/<version>/evidence_index.json",
    "audit_sql_md_path": "audit/<session_id>/sql.md",
    "audit_sql_dir_path": "audit/<session_id>/sql",
    "sql_audit_report_path": "audit/<session_id>/sql_audit_report.json",
    "report_audit_report_path": "audit/<session_id>/report_audit_report.json"
  }
}
```

## 落盘流程
1. 生成 `theme` 和 `version`
2. 创建 `reports/<theme>/<version>/`
3. 写入 `report.md`、`report.json`、`analysis_trace.md`
4. 生成 `evidence_index.json` 与 `metadata.json`
5. 校验所有 `query_id` 都能在 `audit/<session_id>/sql.md` 找到

## 校验规则
- 若 `report.md` 缺失 -> `FAIL`
- 若 `analysis_trace.md` 缺失 -> `WARN`（可升级为 FAIL，按团队要求）
- 若 `evidence_index.json` 无法映射到 SQL -> `FAIL`
- 若 `theme` 或 `version` 为空 -> `FAIL`

## 推荐附加文件（可选）
- `diff-from-previous.md`：同主题版本对比
- `charts/`：导出图表
