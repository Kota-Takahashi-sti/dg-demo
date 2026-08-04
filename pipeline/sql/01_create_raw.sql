-- raw 層: seed CSV をそのまま載せる層(品質チェックの対象)
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

-- mart.customer_summary(ビュー)は raw.customers に依存するため、
-- 再シード時は先にビューを削除する(依存エラー回避)
DROP VIEW IF EXISTS mart.customer_summary;

DROP TABLE IF EXISTS raw.order_items;
DROP TABLE IF EXISTS raw.orders;
DROP TABLE IF EXISTS raw.products;
DROP TABLE IF EXISTS raw.customers;

-- 品質違反(NULL・重複)を「投入できてしまう」ことがデモの前提のため、
-- raw 層には PRIMARY KEY / NOT NULL 制約を意図的に付けない。
CREATE TABLE raw.customers (
    customer_id integer,
    name        varchar(100),
    email       varchar(255),
    prefecture  varchar(10),
    created_at  timestamp
);

CREATE TABLE raw.products (
    product_id integer,
    name       varchar(200),
    category   varchar(50),
    price      numeric(10, 2)
);

CREATE TABLE raw.orders (
    order_id    integer,
    customer_id integer,
    order_date  date,
    status      varchar(20)
);

CREATE TABLE raw.order_items (
    order_item_id integer,
    order_id      integer,
    product_id    integer,
    quantity      integer,
    unit_price    numeric(10, 2)
);
