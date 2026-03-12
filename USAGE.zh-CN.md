# SQL2BI 使用文档（重点：两个 Skills 的实操）

## 1. 这是什么项目

`sql2bi` 是一个把 `sql.md`（Markdown 中多个 SQL 块）转换为可运行 BI 原型的工作区，核心能力分两部分：

1. `sql-to-bi-builder`：把 SQL 自动变成仪表盘规格、UI 和服务骨架。
2. `starrocks-mcp-analyst`：通过 StarRocks MCP 做“可审计”的业务分析与结论输出。

建议把它理解为：
- `sql-to-bi-builder` 负责“搭建 BI 页面与服务”。
- `starrocks-mcp-analyst` 负责“做严谨分析并产出业务结论”。

规范化 Prompt 模板见：
- [PROMPT-TEMPLATE.zh-CN.md](./PROMPT-TEMPLATE.zh-CN.md)

## 2. 克隆项目

```bash
git clone https://github.com/stan2133/sql2bi.git
cd sql2bi
```

## 3. 环境准备

### 3.1 标准环境（推荐）

- Python `3.11.x`
- Node.js + npm（只在你要跑 React 前端时需要）

项目约束：
- `.python-version` 固定为 `3.11`
- `pyproject.toml` 要求 `>=3.11,<3.12`

### 3.2 快速体验环境（无需装 Node，也可缺少后端重依赖）

项目启动脚本有自动降级能力：

1. 后端：
- 若检测到 `fastapi/uvicorn/duckdb/polars/pandas`，走 full 模式。
- 否则自动走 lite 模式（`services/backend/app_lite.py`）。

2. 前端：
- 若 `services/frontend/node_modules` 存在，走 React/Vite 模式。
- 否则自动走 lite 前端（`services/frontend-lite`）。

## 4. 一次跑通（最快路径）

### 4.1 启动服务

```bash
bash services/start_backend.sh
bash services/start_frontend.sh
```

默认地址：
- 后端：`http://127.0.0.1:18000`
- 前端：`http://127.0.0.1:15173`

可通过环境变量改端口：
- `BACKEND_HOST` / `BACKEND_PORT`
- `FRONTEND_HOST` / `FRONTEND_PORT`

### 4.2 导入 SQL 文件

```bash
curl -X POST http://127.0.0.1:18000/api/v1/import/sql-md \
  -H 'Content-Type: application/json' \
  -d '{"sql_md_path":"/绝对路径/sql.md"}'
```

示例（仓库内 demo）：

```bash
curl -X POST http://127.0.0.1:18000/api/v1/import/sql-md \
  -H 'Content-Type: application/json' \
  -d '{"sql_md_path":"/Users/bamboo/sql2bi/testdata/sql/demo.sql.md"}'
```

导入成功后，后端会自动产出：
- `services/backend/data/artifacts/query_catalog.json`
- `services/backend/data/artifacts/semantic_catalog.json`
- `services/backend/data/artifacts/chart_plan.json`
- `services/backend/data/artifacts/dashboard.json`

### 4.3 自定义更好看的 BI 页面（Theme Studio）

前端右侧 `Theme Studio` 支持：
- 主题预设（Use Dashboard Theme / Sunset Glow / Mint Pulse / Graphite Lab / Midnight Ops）
- 主色、文本色、页面背景、面板背景
- 圆角（Roundness）
- 卡片阴影（Shadow）
- 图表调色板（5 色）

说明：
- 调整结果会保存在浏览器 `localStorage`（键：`sql2bi_ui_overrides_v1`）。
- 点击 `Reset Local Theme` 可清空本地主题覆盖，回到默认。
- 当 `dashboard.json` 包含 `ui.theme` 与 `ui.chart_palette` 时，会作为“看板默认风格”自动加载。

### 4.4 新版 UI 升级点（2026-03）

为了让展示差异更明显，这一版新增：

1. 顶部 KPI 汇总条（自动从每个 Widget 的 summary 提取主指标）
- 支持最多展示 6 个 KPI 卡片
- 点击 KPI 卡可直接聚焦到对应图表

2. 布局模式切换（Toolbar）
- `Classic`：原始多图布局
- `Focus`：单图聚焦展示（适合会议演示）

3. 深色运营风格预设
- 新增 `Midnight Ops` 主题预设，夜间/大屏演示观感更明显

4. 可视层级优化
- KPI 卡、选中态、焦点态、背景层次做了强化
- 图表卡 hover/active 反馈更清晰

## 5. Skill 1：`sql-to-bi-builder` 实操

### 5.1 输入文件格式（sql.md）

每个 SQL 用一个 fenced block，建议每块前加元数据：

````md
## card: Daily GMV
- id: daily_gmv
- datasource: mysql_prod
- refresh: 5m
- chart: auto
- filters: date, region

```sql
SELECT DATE(pay_time) AS dt, SUM(amount) AS gmv
FROM orders
WHERE pay_status = 'paid'
GROUP BY 1
ORDER BY 1;
```
````

建议：
- 一条逻辑查询一个 SQL block。
- 必填稳定 `id`。
- 字段尽量显式 `AS 别名`，否则语义推断可能得到 `col_01` 之类的回退名。

### 5.2 一键 Pipeline（要求 Python 3.11）

```bash
python3.11 skills/sql-to-bi-builder/scripts/run_pipeline.py \
  --input /绝对路径/sql.md \
  --out /绝对路径/out \
  --with-services
```

输出目录：
- `out/query_catalog.json`
- `out/semantic_catalog.json`（含 `dsl_filters`）
- `out/chart_plan.json`
- `out/dashboard.json`（含 `global_filters`）
- `out/ui/`
- `out/services/`（`--with-services` 时生成）

### 5.3 分步调试（推荐排错时使用）

```bash
python3 skills/sql-to-bi-builder/scripts/parse_sql_md.py --input /绝对路径/sql.md --output /tmp/out/query_catalog.json
python3 skills/sql-to-bi-builder/scripts/infer_semantics.py --input /tmp/out/query_catalog.json --output /tmp/out/semantic_catalog.json
python3 skills/sql-to-bi-builder/scripts/recommend_chart.py --input /tmp/out/semantic_catalog.json --query-catalog /tmp/out/query_catalog.json --output /tmp/out/chart_plan.json
python3 skills/sql-to-bi-builder/scripts/build_dashboard_spec.py --queries /tmp/out/query_catalog.json --semantics /tmp/out/semantic_catalog.json --charts /tmp/out/chart_plan.json --output /tmp/out/dashboard.json
```

### 5.4 过滤器参数语法（前后端共用）

查询接口：`GET /api/v1/queries/{query_id}/data`

支持三种过滤写法：
- 等值：`field=value`
- 集合：`field=a,b,c`
- 范围：`field=from..to`

示例：

```bash
curl "http://127.0.0.1:18000/api/v1/queries/daily_gmv/data?include_filters=true&region=华东,华南&dt=2024-01-01..2024-01-07"
```

## 6. Skill 2：`starrocks-mcp-analyst` 实操

这个 skill 不是“画图工具”，而是“带审计门禁的业务分析流程”。

### 6.1 使用前提

1. 已配置可用的 StarRocks MCP 服务（至少有元数据查询、SQL 执行能力）。
2. 有可写本地目录用于审计落盘。

### 6.2 必须遵守的审计门禁

每条执行 SQL 都必须同时满足：

1. 落盘 SQL 文件：
- `audit/<session_id>/sql/<query_id>.sql`

2. 追加登记：
- `audit/<session_id>/sql.md`

3. `sql.md` 必备字段：
- `query_id`
- `状态`
- `执行时间`
- `耗时(ms)`
- `返回行数`
- `参数`
- `SQL文件路径`
- 完整 SQL 文本

4. 失败门禁：
- SQL 执行成功但未落盘 => `sql_audit=FAIL`，禁止发布最终结论（Step 7/8）。

### 6.3 推荐操作顺序（按 skill 设计）

1. 建立 Decision Card（问题、指标、时间窗、对比方式、范围）。
2. 明确业务语义合同（指标公式、粒度、允许维度、禁用 join）。
3. 探测 MCP 能力并建立最小数据地图（事实表、维表、join key）。
4. 建立假设树与验证计划（证据 SQL + 反证 SQL + 对账 SQL）。
5. 生成成套 SQL 包（不要只写单条 SQL）。
6. 执行 SQL 审计（口径、粒度、对账、质量、性能）。
7. 输出洞察与影响评估（事实/解释/建议分离）。
8. 执行报告审计并发布。

### 6.4 首次可直接复用的提问模板

```text
请使用 starrocks-mcp-analyst skill 分析：
1) 决策问题：是否应在下月增加 US 区域 paid social 预算？
2) 目标指标：incremental_gmv
3) 分析窗口：2026-02-01 到 2026-02-28，按 day
4) 对比方式：period_over_period
5) 范围：channel=paid_social, region=US, segment=new_users

要求：
- 严格执行 8 步流程
- 每条 SQL 必须落盘到 audit/<session_id>/sql/ 并登记 audit/<session_id>/sql.md
- 审计叙述使用中文
- 输出 sql_audit 与 report_audit
```

## 7. 两个 Skills 如何配合

推荐组合流程：

1. 用 `starrocks-mcp-analyst` 产出高质量、可复核 SQL 包（带审计记录）。
2. 把稳定 SQL 汇总成 `sql.md`。
3. 用 `sql-to-bi-builder` 生成 dashboard + 服务 + UI。
4. 前端演示，后端接口联调，形成“可解释 + 可展示”的分析交付。

## 8. 常见问题

### 8.1 `python3.11 not found in PATH`

这是最常见问题。可先走 lite 模式快速体验，或安装 3.11 后再跑标准 pipeline。

### 8.2 前端打开后提示 Backend unavailable

检查：
1. 后端是否已启动。
2. 前端中的 backend 地址是否是 `http://127.0.0.1:18000`（或你自定义端口）。
3. `Import sql.md` 的路径是否为绝对路径且文件存在。

### 8.3 为什么图里字段名变成 `col_01`

SQL 列缺少显式别名时会发生。请把关键字段改成 `AS xxx`。

### 8.4 导入成功但想看可用过滤器

调用：

```bash
curl http://127.0.0.1:18000/api/v1/filters
```

## 9. 你可以直接执行的最小命令清单

```bash
# 1) 启动后端
bash services/start_backend.sh

# 2) 启动前端
bash services/start_frontend.sh

# 3) 导入示例 SQL
curl -X POST http://127.0.0.1:18000/api/v1/import/sql-md \
  -H 'Content-Type: application/json' \
  -d '{"sql_md_path":"/Users/bamboo/sql2bi/testdata/sql/demo.sql.md"}'

# 4) 查看当前 dashboard
curl http://127.0.0.1:18000/api/v1/dashboard/current
```
