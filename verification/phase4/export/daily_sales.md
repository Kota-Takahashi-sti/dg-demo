# dgd-demo-mart-daily-sales
## Info
*日次の売上金額と注文数を BI ダッシュボード・経営レポートに提供する。 生産者はデータエンジニアリングチーム、想定消費者は経営企画チーム(いずれもデモ用の架空チーム)。*
- **name:** daily_sales
- **version:** 1.0.0
- **status:** active
- **team:** data-engineering

## Terms of Use
### Usage
日次売上・注文数の推移の可視化。sales_date 単位の集計値としてそのまま利用できる。

### Purpose
日次の売上金額と注文数を BI ダッシュボード・経営レポートに提供する。 生産者はデータエンジニアリングチーム、想定消費者は経営企画チーム(いずれもデモ用の架空チーム)。

### Limitations
キャンセル済み注文(raw.orders.status = 'cancelled')は集計に含まない。 金額は円建て想定の合成データであり、実在の取引を含まない。

## Servers
| Name | Type | Attributes |
| ---- | ---- | ---------- |
| local | postgres | *デモ環境(compose の base profile)。資格情報は契約に書かず、 環境変数 DATACONTRACT_POSTGRES_USERNAME / _PASSWORD で渡す(公式仕様)。*<br />• **database:** demo<br />• **host:** postgres-demo<br />• **port:** 5432<br />• **schema_:** mart |

## Schema
### daily_sales
*日次売上集計(staging.stg_orders を order_date で集計した CTAS テーブル)*

| Field | Type | Attributes |
| ----- | ---- | ---------- |
|  sales_date | date | *集計対象日(注文日)。1 日 1 行。*<br />• `primaryKey`<br />• **primaryKeyPosition:** 1<br />• `required`<br />• `unique`<br />• **quality:** [{'id': 'sales_date_no_nulls', 'description': '集計日が NULL の行は存在しないこと', 'metric': 'nullValues', 'mustBe': 0}, {'id': 'sales_date_no_duplicates', 'description': '同じ日付の行が重複しないこと(1 日 1 行の合意)', 'metric': 'duplicateValues', 'mustBe': 0}] |
|  order_count | integer | *その日の注文数(order_id の distinct カウント)*<br />• `required`<br />• **quality:** [{'id': 'order_count_no_nulls', 'description': '注文数が NULL の行は存在しないこと', 'metric': 'nullValues', 'mustBe': 0}] |
|  total_amount | number | *その日の売上合計(quantity × unit_price の合計)*<br />• `required`<br />• **quality:** [{'id': 'total_amount_no_nulls', 'description': '売上合計が NULL の行は存在しないこと', 'metric': 'nullValues', 'mustBe': 0}, {'id': 'total_amount_not_negative', 'description': '売上合計が負の日は存在しないこと(消費者向けの業務的な保証)', 'type': 'sql', 'mustBe': 0, 'query': 'SELECT COUNT(*) FROM {object} WHERE total_amount < 0'}] |

## SLA Properties
| Property | Value | Unit |
| -------- | ----- | ---- |
| frequency | 1 | d |
| retention | 3 | y |