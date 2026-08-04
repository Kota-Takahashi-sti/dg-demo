#!/usr/bin/env python3
"""共通パイプライン(plan.md §3.2)。素の Python + psycopg2 で SQL を実行する。

ステップ:
    seed          : スキーマ・raw テーブル作成 + CSV を COPY で投入
    build_staging : staging.stg_orders を再作成
    build_mart    : mart.daily_sales(テーブル)と mart.customer_summary(ビュー)を再作成

フェーズ2: `--openlineage` を付けると、ステップごとに OpenLineage の RunEvent
(START / COMPLETE / FAIL)を発行する。transport 設定は環境変数 OPENLINEAGE_CONFIG が
指す lineage/openlineage.yml(HTTP → marquez-api)から読まれる。
オーケストレータは使わず、公式クライアント openlineage-python を直接呼ぶ(plan.md §3.3)。

使い方:
    python pipeline/run_pipeline.py --data-dir data/seed/csv                # 全ステップ(OL 発行なし)
    python pipeline/run_pipeline.py --data-dir data/seed/csv --openlineage  # OL イベント発行あり
    python pipeline/run_pipeline.py --openlineage --simulate-failure        # build_mart を意図的に失敗させる
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

SQL_DIR = Path(__file__).parent / "sql"
RAW_TABLES = ["customers", "products", "orders", "order_items"]
ALL_STEPS = ["seed", "build_staging", "build_mart"]

# --- OpenLineage 用の定数(フェーズ2)---
# producer はイベントを生成したコードを指す URI(スペック要件)
PRODUCER = "file:///workspace/pipeline/run_pipeline.py"
# ジョブの namespace(Marquez UI 上でジョブがこの名前空間に並ぶ)
JOB_NAMESPACE = "demo_pipeline"

# データセットの schema facet に載せる列定義(01_create_raw.sql / 02_staging.sql / 03_mart.sql と対応)
TABLE_COLUMNS = {
    ("raw", "customers"): [
        ("customer_id", "integer"), ("name", "varchar"), ("email", "varchar"),
        ("prefecture", "varchar"), ("created_at", "timestamp"),
    ],
    ("raw", "products"): [
        ("product_id", "integer"), ("name", "varchar"),
        ("category", "varchar"), ("price", "numeric"),
    ],
    ("raw", "orders"): [
        ("order_id", "integer"), ("customer_id", "integer"),
        ("order_date", "date"), ("status", "varchar"),
    ],
    ("raw", "order_items"): [
        ("order_item_id", "integer"), ("order_id", "integer"),
        ("product_id", "integer"), ("quantity", "integer"), ("unit_price", "numeric"),
    ],
    ("staging", "stg_orders"): [
        ("order_item_id", "integer"), ("order_id", "integer"), ("customer_id", "integer"),
        ("order_date", "date"), ("status", "varchar"), ("product_id", "integer"),
        ("product_name", "varchar"), ("category", "varchar"), ("quantity", "integer"),
        ("unit_price", "numeric"), ("amount", "numeric"),
    ],
    ("mart", "daily_sales"): [
        ("sales_date", "date"), ("order_count", "bigint"), ("total_amount", "numeric"),
    ],
    ("mart", "customer_summary"): [
        ("customer_id", "integer"), ("total_orders", "bigint"),
        ("total_amount", "numeric"), ("last_order_date", "date"),
    ],
}


def db_config():
    return {
        "host": os.environ.get("DEMO_DB_HOST", "postgres-demo"),
        "port": int(os.environ.get("DEMO_DB_PORT", "5432")),
        "user": os.environ.get("DEMO_DB_USER", "demo"),
        "password": os.environ.get("DEMO_DB_PASSWORD", "demo_password"),
        "dbname": os.environ.get("DEMO_DB_NAME", "demo"),
    }


def connect():
    return psycopg2.connect(**db_config())


class LineageEmitter:
    """OpenLineage イベントの構築と発行をこのクラスに集約する。

    quality venv には openlineage-python が入っていないため、
    import は有効時(--openlineage)のみ行う。
    """

    def __init__(self, enabled: bool, data_dir: Path):
        self.enabled = enabled
        if not enabled:
            return
        from openlineage.client import OpenLineageClient
        from openlineage.client import event_v2
        from openlineage.client.facet_v2 import (
            column_lineage_dataset, error_message_run, schema_dataset, sql_job,
        )
        from openlineage.client.uuid import generate_new_uuid

        self.ev = event_v2
        self.schema_dataset = schema_dataset
        self.column_lineage = column_lineage_dataset
        self.error_message = error_message_run
        self.sql_job = sql_job
        self.new_uuid = generate_new_uuid
        # 設定は OPENLINEAGE_CONFIG(lineage/openlineage.yml)から読まれる
        self.client = OpenLineageClient()
        self.data_dir = data_dir
        cfg = db_config()
        # OpenLineage の命名規約: postgres の namespace は postgres://{host}:{port}、
        # データセット名は {database}.{schema}.{table}
        self.db_ns = f"postgres://{cfg['host']}:{cfg['port']}"
        self.db_name = cfg["dbname"]

    # --- データセット構築 ---
    def _table(self, schema: str, table: str, extra_facets=None):
        facets = {
            "schema": self.schema_dataset.SchemaDatasetFacet(fields=[
                self.schema_dataset.SchemaDatasetFacetFields(name=n, type=t)
                for n, t in TABLE_COLUMNS[(schema, table)]
            ])
        }
        facets.update(extra_facets or {})
        return self.ev.Dataset(
            namespace=self.db_ns, name=f"{self.db_name}.{schema}.{table}", facets=facets)

    def _csv_datasets(self):
        # seed の入力 = CSV ファイル(命名規約: namespace は file、名前はパス)
        return [self.ev.Dataset(namespace="file", name=str(self.data_dir / f"{t}.csv"))
                for t in RAW_TABLES]

    def _daily_sales_column_lineage(self):
        """mart.daily_sales のカラムレベルリネージュ facet(spec 1-2-0)。

        03_mart.sql の SELECT と 1:1 対応:
            sales_date   <- stg_orders.order_date(そのまま)
            order_count  <- count(DISTINCT stg_orders.order_id)
            total_amount <- sum(stg_orders.amount)
        GROUP BY order_date の影響は INDIRECT / GROUP_BY として表現する。
        """
        cl = self.column_lineage
        stg = f"{self.db_name}.staging.stg_orders"

        def input_field(field, ttype, subtype, description):
            return cl.InputField(
                namespace=self.db_ns, name=stg, field=field,
                transformations=[cl.Transformation(
                    type=ttype, subtype=subtype, description=description, masking=False)])

        return cl.ColumnLineageDatasetFacet(fields={
            "sales_date": cl.Fields(
                inputFields=[input_field(
                    "order_date", "DIRECT", "IDENTITY", "order_date をそのまま採用")],
                transformationDescription="order_date をそのまま採用",
                transformationType="IDENTITY"),
            "order_count": cl.Fields(
                inputFields=[
                    input_field("order_id", "DIRECT", "AGGREGATION",
                                "count(DISTINCT order_id)"),
                    input_field("order_date", "INDIRECT", "GROUP_BY",
                                "GROUP BY order_date"),
                ],
                transformationDescription="count(DISTINCT order_id)",
                transformationType="AGGREGATION"),
            "total_amount": cl.Fields(
                inputFields=[
                    input_field("amount", "DIRECT", "AGGREGATION", "sum(amount)"),
                    input_field("order_date", "INDIRECT", "GROUP_BY",
                                "GROUP BY order_date"),
                ],
                transformationDescription="sum(amount)",
                transformationType="AGGREGATION"),
        })

    def _step_io(self, step: str):
        """ステップごとの入出力データセット(SQL の実装と 1:1 対応)"""
        if step == "seed":
            return (self._csv_datasets(),
                    [self._table("raw", t) for t in RAW_TABLES])
        if step == "build_staging":
            return ([self._table("raw", t) for t in ("orders", "order_items", "products")],
                    [self._table("staging", "stg_orders")])
        if step == "build_mart":
            return ([self._table("staging", "stg_orders"), self._table("raw", "customers")],
                    [self._table("mart", "daily_sales",
                                 {"columnLineage": self._daily_sales_column_lineage()}),
                     self._table("mart", "customer_summary")])
        raise ValueError(step)

    def _job(self, step: str, sql_text: str | None):
        facets = {}
        if sql_text:
            facets["sql"] = self.sql_job.SQLJobFacet(query=sql_text)
        return self.ev.Job(namespace=JOB_NAMESPACE, name=f"run_pipeline.{step}", facets=facets)

    def _emit(self, state, step, run, sql_text, with_outputs: bool, run_facets=None):
        inputs, outputs = self._step_io(step)
        run = self.ev.Run(runId=run.runId, facets=run_facets or {})
        self.client.emit(self.ev.RunEvent(
            eventType=state,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=run,
            job=self._job(step, sql_text),
            producer=PRODUCER,
            inputs=inputs,
            outputs=outputs if with_outputs else [],
        ))

    # --- 各ステップから呼ぶ 3 メソッド ---
    def start(self, step: str, sql_text: str | None):
        if not self.enabled:
            return None
        run = self.ev.Run(runId=str(self.new_uuid()))
        self._emit(self.ev.RunState.START, step, run, sql_text, with_outputs=False)
        print(f"[openlineage] START    run_pipeline.{step} (runId={run.runId})")
        return run

    def complete(self, step: str, run, sql_text: str | None):
        if not self.enabled:
            return
        self._emit(self.ev.RunState.COMPLETE, step, run, sql_text, with_outputs=True)
        print(f"[openlineage] COMPLETE run_pipeline.{step}")

    def fail(self, step: str, run, sql_text: str | None, error: Exception):
        if not self.enabled:
            return
        facets = {"errorMessage": self.error_message.ErrorMessageRunFacet(
            message=str(error), programmingLanguage="python")}
        self._emit(self.ev.RunState.FAIL, step, run, sql_text, with_outputs=False,
                   run_facets=facets)
        print(f"[openlineage] FAIL     run_pipeline.{step}")


def run_sql_file(cur, path: Path):
    print(f"[sql] {path.name} を実行")
    cur.execute(path.read_text(encoding="utf-8"))


def step_seed(conn, data_dir: Path):
    with conn.cursor() as cur:
        run_sql_file(cur, SQL_DIR / "01_create_raw.sql")
        for table in RAW_TABLES:
            csv_path = data_dir / f"{table}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"{csv_path} がありません。先に data/seed/generate.py を実行してください")
            with csv_path.open("r", encoding="utf-8") as f:
                # 空文字列は NULL として投入する(email NULL 混入デモのため)
                cur.copy_expert(
                    f"COPY raw.{table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", f)
            cur.execute(f"SELECT count(*) FROM raw.{table}")
            print(f"[seed] raw.{table}: {cur.fetchone()[0]} 行")
    conn.commit()


def step_build_staging(conn):
    with conn.cursor() as cur:
        run_sql_file(cur, SQL_DIR / "02_staging.sql")
        cur.execute("SELECT count(*) FROM staging.stg_orders")
        print(f"[build_staging] staging.stg_orders: {cur.fetchone()[0]} 行")
    conn.commit()


def step_build_mart(conn, simulate_failure: bool):
    # --simulate-failure 時は存在しない列を参照する「壊れた」SQL を実行し、
    # SQL エラー → FAIL イベント発行のデモにする(03_mart_broken.sql)
    sql_name = "03_mart_broken.sql" if simulate_failure else "03_mart.sql"
    with conn.cursor() as cur:
        run_sql_file(cur, SQL_DIR / sql_name)
        cur.execute("SELECT count(*) FROM mart.daily_sales")
        print(f"[build_mart] mart.daily_sales: {cur.fetchone()[0]} 行")
        cur.execute("SELECT count(*) FROM mart.customer_summary")
        print(f"[build_mart] mart.customer_summary(ビュー): {cur.fetchone()[0]} 行")
    conn.commit()


def mart_sql_path(simulate_failure: bool) -> Path:
    return SQL_DIR / ("03_mart_broken.sql" if simulate_failure else "03_mart.sql")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/seed/csv",
                        help="投入する CSV のディレクトリ(既定: data/seed/csv)")
    parser.add_argument("--steps", default=",".join(ALL_STEPS),
                        help=f"実行ステップ(カンマ区切り。既定: {','.join(ALL_STEPS)})")
    parser.add_argument("--openlineage", action="store_true",
                        help="OpenLineage イベントを発行する(lineage venv で実行すること)")
    parser.add_argument("--simulate-failure", action="store_true",
                        help="build_mart を意図的に失敗させる(異常系リネージュデモ用)")
    args = parser.parse_args()

    steps = args.steps.split(",")
    unknown = set(steps) - set(ALL_STEPS)
    if unknown:
        print(f"エラー: 未知のステップ {sorted(unknown)}", file=sys.stderr)
        return 2

    emitter = LineageEmitter(args.openlineage, Path(args.data_dir))
    # ステップごとの SQL ファイル(sql job facet 用。seed は COPY 主体のため DDL のみ)
    step_sql = {
        "seed": SQL_DIR / "01_create_raw.sql",
        "build_staging": SQL_DIR / "02_staging.sql",
        "build_mart": mart_sql_path(args.simulate_failure),
    }

    conn = connect()
    try:
        for step in steps:
            print(f"=== step: {step} ===")
            sql_text = step_sql[step].read_text(encoding="utf-8")
            run = emitter.start(step, sql_text)
            try:
                if step == "seed":
                    step_seed(conn, Path(args.data_dir))
                elif step == "build_staging":
                    step_build_staging(conn)
                elif step == "build_mart":
                    step_build_mart(conn, args.simulate_failure)
            except Exception as e:
                conn.rollback()
                emitter.fail(step, run, sql_text, e)
                print(f"エラー: step {step} が失敗しました: {e}", file=sys.stderr)
                return 1
            emitter.complete(step, run, sql_text)
        print("パイプライン完了")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
