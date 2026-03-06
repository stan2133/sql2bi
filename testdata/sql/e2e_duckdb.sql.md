# E2E Dashboard

## card: Paid Orders By Region
- id: paid_orders_by_region
- datasource: duckdb_demo
- chart: table
- filters: region

```sql
SELECT region, COUNT(*) AS paid_orders
FROM orders
WHERE pay_status = 'paid'
GROUP BY 1
ORDER BY 2 DESC;
```
