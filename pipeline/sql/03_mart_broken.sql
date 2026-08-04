-- 「壊れた」mart 構築 SQL(異常系リネージュデモ専用。run_pipeline.py --simulate-failure で使用)
-- staging.stg_orders に存在しない列 amount_with_tax を参照するため、
-- 実行すると必ず UndefinedColumn エラーになる。
-- → パイプラインは FAIL の RunEvent を発行して非 0 終了し、
--   Marquez 上で run_pipeline.build_mart の Run が FAILED になる様子を確認する。
-- 実行はトランザクション内のためロールバックされ、既存の mart には影響しない。
DROP TABLE IF EXISTS mart.daily_sales;

CREATE TABLE mart.daily_sales AS
SELECT
    order_date              AS sales_date,
    count(DISTINCT order_id) AS order_count,
    sum(amount_with_tax)    AS total_amount   -- ← この列は存在しない(意図的なバグ)
FROM staging.stg_orders
GROUP BY order_date
ORDER BY order_date;
