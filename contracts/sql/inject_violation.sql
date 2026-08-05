-- D-3(demo-contract-violation)用: mart.daily_sales に契約違反を意図的に注入する。
-- 「パイプラインの不具合や手動修正で、提供テーブルが契約を破った状態」を再現するデモ専用 SQL。
-- 日付は合成データ(シード固定)の範囲 2025-07-01〜2026-06-30 に対する固定値で、結果は決定的。
-- 復旧するには `make seed`(クリーンデータで再構築)を実行する。

-- 違反1: 同じ日付の行を重複させる
--   → 契約の sales_date_no_duplicates(duplicateValues)と unique: true に違反
INSERT INTO mart.daily_sales (sales_date, order_count, total_amount)
SELECT sales_date, order_count, total_amount
FROM mart.daily_sales
WHERE sales_date = DATE '2025-07-01';

-- 違反2: 売上合計を負の値にする
--   → 契約の total_amount_not_negative(type: sql)に違反
UPDATE mart.daily_sales
SET total_amount = -50000
WHERE sales_date = DATE '2026-06-30';

-- 違反3: 注文数を NULL にする
--   → 契約の order_count_no_nulls(nullValues)と required: true に違反
UPDATE mart.daily_sales
SET order_count = NULL
WHERE sales_date = DATE '2026-01-15';
