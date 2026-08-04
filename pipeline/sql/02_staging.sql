-- staging 層: 注文明細を結合・クレンジングした中間テーブル
-- (フェーズ2 のリネージュデモで raw → staging → mart の中間ノードになる)
DROP TABLE IF EXISTS staging.stg_orders;

CREATE TABLE staging.stg_orders AS
SELECT
    oi.order_item_id,
    o.order_id,
    o.customer_id,
    o.order_date,
    o.status,
    oi.product_id,
    p.name          AS product_name,
    p.category,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS amount
FROM raw.orders o
JOIN raw.order_items oi ON oi.order_id = o.order_id
JOIN raw.products p     ON p.product_id = oi.product_id
WHERE o.status <> 'cancelled';
