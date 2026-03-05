# 审计 SQL Markdown 模板

使用此模板生成 `audit/<session_id>/sql.md`。
该文件用于人工审计与升级，必须包含完整执行 SQL。

## 会话元信息
- `session_id`: `<session_id>`
- `生成时间`: `<ISO-8601 timestamp>`
- `sql_audit`: `PASS|WARN|FAIL`
- `查询总数`: `<int>`
- `备注`: `<optional>`

---

## 查询: `<query_id>`
- `hypothesis_id`: `<H1|optional>`
- `状态`: `PASS|WARN|FAIL`
- `耗时_ms`: `<int>`
- `返回行数`: `<int>`
- `执行时间`: `<ISO-8601 timestamp>`
- `参数`: `<json>`
- `sql文件`: `audit/<session_id>/sql/<query_id>.sql`

```sql
-- full executed SQL (rendered with effective parameters or clearly marked placeholders)
SELECT ...
```

---

## 查询: `<query_id>`
- `hypothesis_id`: `<H2|optional>`
- `状态`: `PASS|WARN|FAIL`
- `耗时_ms`: `<int>`
- `返回行数`: `<int>`
- `执行时间`: `<ISO-8601 timestamp>`
- `参数`: `<json>`
- `sql文件`: `audit/<session_id>/sql/<query_id>.sql`

```sql
SELECT ...
```

## 会话结束汇总
- `成功查询数`: `<int>`
- `告警查询数`: `<int>`
- `失败查询数`: `<int>`
- `剩余风险`: `<list>`
