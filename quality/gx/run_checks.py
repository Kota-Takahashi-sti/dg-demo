#!/usr/bin/env python3
"""Great Expectations 1.x によるデータ品質チェック(plan.md 領域A)。

Soda 版(quality/soda/contracts/*.yaml)と完全に同一の 4 チェックを実装する:
  (a) raw.customers.email の欠損 0 件      → ExpectColumnValuesToNotBeNull
  (b) raw.orders.order_id の一意性         → ExpectColumnValuesToBeUnique
  (c) raw.order_items.quantity >= 1、
      unit_price が 0〜100000 の範囲        → ExpectColumnValuesToBeBetween ×2
  (d) raw.orders のスキーマ(列と型)      → ExpectTableColumnsToMatchOrderedList
                                             + ExpectColumnValuesToBeOfType

参照(調査日 2026-08-04):
  docs.greatexpectations.io/docs/core/connect_to_data/sql_data
  docs.greatexpectations.io/docs/core/define_expectations/organize_expectation_suites
  docs.greatexpectations.io/docs/core/run_validations/create_a_validation_definition
  docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/create_a_checkpoint_with_actions

終了コード: 全チェック成功 = 0 / 1 つでも失敗 = 1
"""

import json
import os
import sys

import great_expectations as gx

DATA_DOCS_DIR = os.environ.get("GX_DATA_DOCS_DIR", "quality/gx/output/data_docs")


def connection_string() -> str:
    host = os.environ.get("DEMO_DB_HOST", "postgres-demo")
    port = os.environ.get("DEMO_DB_PORT", "5432")
    user = os.environ.get("DEMO_DB_USER", "demo")
    password = os.environ.get("DEMO_DB_PASSWORD", "demo_password")
    dbname = os.environ.get("DEMO_DB_NAME", "demo")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


def build_suites():
    """テーブルごとの ExpectationSuite 定義(Soda contract と 1:1 対応)。"""
    E = gx.expectations
    return {
        "customers": [
            # (a) email の欠損 0 件
            E.ExpectColumnValuesToNotBeNull(column="email"),
        ],
        "orders": [
            # (b) order_id の一意性
            E.ExpectColumnValuesToBeUnique(column="order_id"),
            # (d) スキーマ: 列の存在・順序
            E.ExpectTableColumnsToMatchOrderedList(
                column_list=["order_id", "customer_id", "order_date", "status"]),
            # (d) スキーマ: 型
            E.ExpectColumnValuesToBeOfType(column="order_id", type_="INTEGER"),
            E.ExpectColumnValuesToBeOfType(column="customer_id", type_="INTEGER"),
            E.ExpectColumnValuesToBeOfType(column="order_date", type_="DATE"),
            # 実測: SQLAlchemy 経由の観測値は長さ付きの "VARCHAR(20)" になる
            E.ExpectColumnValuesToBeOfType(column="status", type_="VARCHAR(20)"),
        ],
        "order_items": [
            # (c) quantity >= 1
            E.ExpectColumnValuesToBeBetween(column="quantity", min_value=1),
            # (c) unit_price の値域
            E.ExpectColumnValuesToBeBetween(
                column="unit_price", min_value=0, max_value=100000),
        ],
    }


def main() -> int:
    context = gx.get_context(mode="ephemeral")

    # メトリクス計算の進捗バーを無効化(生ログを汚さないため)
    from great_expectations.data_context.types.base import ProgressBarsConfig
    context.variables.progress_bars = ProgressBarsConfig(globally=False)

    # Data Docs(HTML レポート)をローカル出力する site を追加
    context.add_data_docs_site(
        site_name="demo_site",
        site_config={
            "class_name": "SiteBuilder",
            "store_backend": {
                "class_name": "TupleFilesystemStoreBackend",
                "base_directory": os.path.abspath(DATA_DOCS_DIR),
            },
            "site_index_builder": {"class_name": "DefaultSiteIndexBuilder"},
        },
    )

    data_source = context.data_sources.add_postgres(
        name="postgres_demo", connection_string=connection_string())

    validation_definitions = []
    for table, expectations in build_suites().items():
        asset = data_source.add_table_asset(
            table_name=table, schema_name="raw", name=f"raw.{table}")
        batch_definition = asset.add_batch_definition_whole_table(
            name=f"{table}_whole_table")

        suite = context.suites.add(gx.ExpectationSuite(name=f"raw_{table}_suite"))
        for expectation in expectations:
            suite.add_expectation(expectation)

        validation_definitions.append(
            context.validation_definitions.add(
                gx.ValidationDefinition(
                    name=f"raw_{table}_validation",
                    data=batch_definition,
                    suite=suite,
                )
            )
        )

    checkpoint = context.checkpoints.add(
        gx.Checkpoint(
            name="quality_checkpoint",
            validation_definitions=validation_definitions,
            actions=[
                gx.checkpoint.UpdateDataDocsAction(name="update_data_docs"),
            ],
            result_format={"result_format": "SUMMARY"},
        )
    )

    result = checkpoint.run()

    # 結果の全文(JSON)を表示・保存する。Soda の CLI 出力との情報量比較が
    # 比較軸2 の題材になる。
    print(result.describe())
    os.makedirs("quality/gx/output", exist_ok=True)
    with open("quality/gx/output/last_result.json", "w", encoding="utf-8") as f:
        f.write(result.describe())

    print()
    if result.success:
        print("GX チェック結果: 全チェック成功")
        return 0
    print("GX チェック結果: 品質違反を検知(詳細は上記 JSON)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
