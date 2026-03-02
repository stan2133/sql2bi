# SQL2BI Demo Dashboard

## card: Daily GMV
- id: daily_gmv
- datasource: duckdb_demo
- chart: line
- refresh: 15m
- filters: region, channel

```sql
SELECT DATE(pay_time) AS dt, SUM(amount) AS gmv
FROM orders
WHERE pay_status = 'paid'
  AND pay_time BETWEEN {{start_date}} AND {{end_date}}
GROUP BY 1
ORDER BY 1;
```

## card: Region Revenue Mix
- id: region_revenue_mix
- datasource: duckdb_demo
- chart: grouped_bar
- filters: region

```sql
SELECT region, SUM(amount) AS gmv, COUNT(*) AS order_cnt
FROM orders
WHERE pay_status IN ('paid', 'refund')
  AND channel IN ('app', 'web', 'partner')
GROUP BY 1
ORDER BY gmv DESC;
```

## card: Paid Orders by BizDate
- id: paid_orders_bizdate
- datasource: duckdb_demo
- chart: bar
- filters: biz_date

```sql
SELECT biz_date, COUNT(*) AS paid_orders
FROM orders
WHERE pay_status = 'paid'
  AND biz_date >= 20240101
  AND biz_date <= 20240331
GROUP BY 1
ORDER BY 1;
```

## card: Event Device Table
- id: event_device_table
- datasource: duckdb_demo
- chart: table
- filters: event_name, device

```sql
SELECT event_name, device, COUNT(*) AS event_cnt, SUM(revenue) AS total_revenue
FROM events
WHERE event_time >= '2024-01-01 00:00:00'
  AND event_time < '2024-04-01 00:00:00'
  AND region = :region
GROUP BY 1,2
ORDER BY event_cnt DESC;
```
