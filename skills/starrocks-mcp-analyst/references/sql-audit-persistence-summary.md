# SQL 审计落盘要求（汇总）

## 目标
确保每条实际运行 SQL 都有本地可审计证据，支持人工复核与升级处理。

## 必须执行
1. 会话目录必须存在：
```text
audit/<session_id>/
  sql.md
  sql/
```
2. 每条执行 SQL 必须落盘到：
```text
audit/<session_id>/sql/<query_id>.sql
```
3. 每条执行 SQL 必须追加登记到：
```text
audit/<session_id>/sql.md
```

## sql.md 最低字段
- `query_id`
- `状态`
- `执行时间`
- `耗时(ms)`
- `返回行数`
- `参数`
- `SQL文件路径`
- 完整 SQL 文本

## 门禁规则
- SQL 执行成功但未落盘：`sql_audit=FAIL`
- 未生成 `sql.md`：`sql_audit=FAIL`
- 报告引用了未落盘 query：`report_audit=FAIL`

## 语言规则
- 审计叙述默认中文（`zh-CN`）
- SQL 原文保持原样
