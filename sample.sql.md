# Sales

## card: Daily GMV
- id: daily_gmv
- datasource: mysql_prod
- refresh: 5m
- chart: auto
- filters: date, region

```sql
SELECT DATE(pay_time) AS dt, SUM(amount) AS gmv
FROM orders
WHERE pay_status='paid'
GROUP BY 1
ORDER BY 1;
```

## card: Paid Orders
- id: paid_orders
- chart: auto

```sql
SELECT COUNT(*) AS paid_orders
FROM orders
WHERE pay_status='paid';
```
