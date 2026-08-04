-- mart 層: 集計テーブル(CTAS)とビュー
-- daily_sales はフェーズ4 のデータコントラクト(ODCS)の対象テーブル
DROP TABLE IF EXISTS mart.daily_sales;

CREATE TABLE mart.daily_sales AS
SELECT
    order_date              AS sales_date,
    count(DISTINCT order_id) AS order_count,
    sum(amount)             AS total_amount
FROM staging.stg_orders
GROUP BY order_date
ORDER BY order_date;

-- customer_summary はあえて「ビュー」として定義する
-- (フェーズ3 で OpenMetadata がビュー定義 SQL を解析してリネージュを
--  自動生成する様子を見せるため。plan.md §3.1)
CREATE OR REPLACE VIEW mart.customer_summary AS
SELECT
    c.customer_id,
    count(DISTINCT s.order_id) AS total_orders,
    coalesce(sum(s.amount), 0) AS total_amount,
    max(s.order_date)          AS last_order_date
FROM raw.customers c
LEFT JOIN staging.stg_orders s ON s.customer_id = c.customer_id
GROUP BY c.customer_id;
