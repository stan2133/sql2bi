PRAGMA threads=4;

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS users;

CREATE TABLE users AS
SELECT
  100000 + i AS user_id,
  CASE i % 5
    WHEN 0 THEN 'north'
    WHEN 1 THEN 'east'
    WHEN 2 THEN 'south'
    WHEN 3 THEN 'west'
    ELSE 'central'
  END AS region,
  CASE i % 3
    WHEN 0 THEN 'pro'
    WHEN 1 THEN 'basic'
    ELSE 'enterprise'
  END AS plan,
  TIMESTAMP '2023-01-01' + (i % 365) * INTERVAL 1 DAY AS signup_time
FROM generate_series(0, 3999) g(i);

CREATE TABLE orders AS
WITH base AS (
  SELECT row_number() OVER () - 1 AS g, ts
  FROM generate_series(TIMESTAMP '2024-01-01 00:00:00', TIMESTAMP '2024-03-31 18:00:00', INTERVAL 6 HOUR) t(ts)
)
SELECT
  g + 1 AS order_id,
  100000 + (g % 4000) AS user_id,
  ts AS pay_time,
  CAST(strftime(ts, '%Y%m%d') AS INTEGER) AS biz_date,
  CASE g % 5
    WHEN 0 THEN 'north'
    WHEN 1 THEN 'east'
    WHEN 2 THEN 'south'
    WHEN 3 THEN 'west'
    ELSE 'central'
  END AS region,
  CASE g % 4
    WHEN 0 THEN 'app'
    WHEN 1 THEN 'web'
    WHEN 2 THEN 'partner'
    ELSE 'offline'
  END AS channel,
  ROUND(20 + (g % 17) * 3.7 + (g % 9) * 1.2, 2) AS amount,
  CASE
    WHEN g % 11 = 0 THEN 'failed'
    WHEN g % 9 = 0 THEN 'refund'
    ELSE 'paid'
  END AS pay_status
FROM base;

CREATE TABLE events AS
WITH base AS (
  SELECT row_number() OVER () - 1 AS g, ts
  FROM generate_series(TIMESTAMP '2024-01-01 00:00:00', TIMESTAMP '2024-03-31 23:00:00', INTERVAL 3 HOUR) t(ts)
)
SELECT
  g + 1 AS event_id,
  100000 + (g % 4000) AS user_id,
  ts AS event_time,
  CASE g % 6
    WHEN 0 THEN 'visit'
    WHEN 1 THEN 'search'
    WHEN 2 THEN 'add_to_cart'
    WHEN 3 THEN 'checkout'
    WHEN 4 THEN 'payment'
    ELSE 'support'
  END AS event_name,
  CASE g % 5
    WHEN 0 THEN 'north'
    WHEN 1 THEN 'east'
    WHEN 2 THEN 'south'
    WHEN 3 THEN 'west'
    ELSE 'central'
  END AS region,
  CASE g % 4
    WHEN 0 THEN 'ios'
    WHEN 1 THEN 'android'
    WHEN 2 THEN 'web'
    ELSE 'mini_program'
  END AS device,
  ROUND(5 + (g % 13) * 2.3, 2) AS revenue
FROM base;

CREATE INDEX idx_orders_pay_time ON orders(pay_time);
CREATE INDEX idx_orders_biz_date ON orders(biz_date);
CREATE INDEX idx_events_event_time ON events(event_time);
