# SQL2BI 规范化 Prompt 模板

这份模板用于让团队成员稳定地产出“可运行的 BI”，避免口头描述过于模糊。

## 1. 使用说明

1. 复制下面的“主模板 Prompt”。
2. 按字段填空（尤其是数据表结构和业务口径）。
3. 直接发给支持该项目技能的 AI 助手执行。

## 2. 主模板 Prompt（推荐）

```text
你现在是 SQL2BI 的 BI 构建助手。请基于我提供的信息，生成可直接在 sql2bi 项目中运行的 BI 方案。

【目标】
把业务问题转为可执行的 sql.md，并确保可导入 sql2bi 后端生成 dashboard。

【我的输入】
1) 业务目标：
{{business_goal}}

2) 核心指标（名称 + 计算口径）：
{{metrics_definition}}

3) 分析范围（时间、区域、渠道、人群）：
{{scope}}

4) 可用数据表与字段（必须给出）：
{{schema_details}}

5) 希望展示的图表/看板偏好（可选）：
{{chart_preferences}}

6) 过滤器偏好（可选）：
{{filter_preferences}}

【强约束】
1. 输出必须包含一个完整 `sql.md`，每个卡片一个 SQL fenced block。
2. 每个 SQL block 前必须有元数据：
   - id
   - datasource
   - refresh
   - chart（auto/line/bar/grouped_bar/kpi/table）
   - filters（逗号分隔）
3. SQL 禁止 `SELECT *`，关键字段必须显式 `AS` 别名。
4. 如涉及时间分析，必须给出清晰时间字段与时间过滤条件。
5. 信息缺失时先列出“默认假设”，不要编造不存在的表字段。

【输出格式（严格按顺序）】
1) assumptions：列出你使用的默认假设
2) sql_md：输出完整 sql.md 内容（可直接保存）
3) run_commands：给出导入与运行命令
4) validation_checklist：给出 5 条校验项（口径、粒度、过滤器、图表匹配、可解释性）

【运行命令格式要求】
命令默认基于仓库根目录执行，使用：
- bash services/start_backend.sh
- bash services/start_frontend.sh
- curl POST /api/v1/import/sql-md 导入 sql.md 绝对路径

现在开始生成。
```

## 3. 场景模板 A：我已经有 SQL

适用：你已经写好 SQL，只想快速变成 BI。

```text
请使用 SQL2BI 的 sql-to-bi-builder 方式，把下面 SQL 集合整理成可执行 sql.md，并给出运行命令。

要求：
1) 每条 SQL 生成一个卡片，补齐元数据（id/datasource/refresh/chart/filters）
2) 图表类型优先按 SQL 语义选择（时间序列=line，单指标聚合=kpi，维度聚合=bar/grouped_bar）
3) 输出严格包含：assumptions、sql_md、run_commands、validation_checklist

SQL 如下：
{{your_sql_blocks}}
```

## 4. 场景模板 B：我只有业务需求

适用：你还没有 SQL，需要助手先设计 SQL 再生成 BI。

```text
请基于以下业务需求，先设计分析卡片，再生成可执行 sql.md：

业务需求：
{{business_need}}

数据表结构：
{{schema_details}}

指标口径：
{{metrics_definition}}

要求：
1) 至少输出 4 个卡片（趋势、结构、效率、明细）
2) 每个卡片给出 SQL，禁止 SELECT *
3) 每个 SQL block 附元数据（id/datasource/refresh/chart/filters）
4) 输出严格包含：assumptions、sql_md、run_commands、validation_checklist
```

## 5. 建议的填空规范（避免歧义）

- `business_goal`：写“决策问题”，不要写“做个看板看看”。
- `metrics_definition`：写公式，例如 `GMV = sum(paid_amount)`。
- `scope`：明确日期范围与粒度，例如“2026-01-01~2026-03-31，按日”。
- `schema_details`：至少包含表名、关键字段、时间字段、关联键。
- `chart_preferences`：可写“趋势用 line，占比用 grouped_bar，总览用 kpi”。
- `filter_preferences`：例如“region, channel, biz_date”。

## 6. 最小示例（可直接复制）

```text
你现在是 SQL2BI 的 BI 构建助手。请基于我提供的信息，生成可直接在 sql2bi 项目中运行的 BI 方案。

【我的输入】
1) 业务目标：
判断华东区 2026Q1 销售下滑主要来自流量、转化率还是客单价。

2) 核心指标：
GMV=sum(pay_amount), CVR=paid_orders/visit_uv, AOV=GMV/paid_orders

3) 分析范围：
2026-01-01 到 2026-03-31，按 day，region=华东

4) 可用数据表与字段：
fact_orders(order_id, user_id, pay_time, pay_amount, region, channel, pay_status)
fact_traffic(dt, region, channel, visit_uv)

5) 图表偏好：
趋势=line，结构=grouped_bar，总览=kpi

6) 过滤器偏好：
region, channel, dt

请按以下顺序输出：
1) assumptions
2) sql_md
3) run_commands
4) validation_checklist
```
