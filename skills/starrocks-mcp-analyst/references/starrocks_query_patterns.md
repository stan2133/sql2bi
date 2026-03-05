# StarRocks Query Patterns

Use these templates as starting points and adapt field/table names to real schema.

## 1) Time Trend

```sql
WITH base AS (
  SELECT
    event_time,
    amount
  FROM fact_orders
  WHERE event_time >= :start_time
    AND event_time < :end_time
),
agg AS (
  SELECT
    DATE_TRUNC('day', event_time) AS dt,
    SUM(amount) AS gmv
  FROM base
  GROUP BY 1
)
SELECT dt, gmv
FROM agg
ORDER BY dt;
```

## 2) Top-N Contribution

```sql
WITH agg AS (
  SELECT
    region,
    SUM(amount) AS gmv
  FROM fact_orders
  WHERE event_time >= :start_time
    AND event_time < :end_time
  GROUP BY 1
),
ranked AS (
  SELECT
    region,
    gmv,
    ROW_NUMBER() OVER (ORDER BY gmv DESC) AS rn
  FROM agg
)
SELECT region, gmv
FROM ranked
WHERE rn <= :top_n
ORDER BY gmv DESC;
```

## 3) Period-Over-Period

```sql
WITH curr AS (
  SELECT SUM(amount) AS value_curr
  FROM fact_orders
  WHERE event_time >= :curr_start
    AND event_time < :curr_end
),
prev AS (
  SELECT SUM(amount) AS value_prev
  FROM fact_orders
  WHERE event_time >= :prev_start
    AND event_time < :prev_end
)
SELECT
  value_curr,
  value_prev,
  (value_curr - value_prev) AS delta,
  CASE WHEN value_prev = 0 THEN NULL
       ELSE (value_curr - value_prev) / value_prev
  END AS delta_rate
FROM curr CROSS JOIN prev;
```

## 4) Funnel Conversion

```sql
WITH steps AS (
  SELECT user_id, step_name
  FROM fact_funnel_events
  WHERE event_time >= :start_time
    AND event_time < :end_time
),
agg AS (
  SELECT
    step_name,
    COUNT(DISTINCT user_id) AS users
  FROM steps
  GROUP BY 1
)
SELECT step_name, users
FROM agg
ORDER BY users DESC;
```

## 5) Join Safety Pattern

```sql
WITH base AS (
  SELECT
    f.order_id,
    f.user_id,
    f.amount,
    d.region
  FROM fact_orders f
  LEFT JOIN dim_users d
    ON f.user_id = d.user_id
  WHERE f.event_time >= :start_time
    AND f.event_time < :end_time
)
SELECT
  region,
  SUM(amount) AS gmv
FROM base
GROUP BY 1
ORDER BY gmv DESC;
```

Checks:
- Validate key cardinality before joining.
- Verify post-join row count is within expected range.
