#!/usr/bin/env python3
"""共通パイプライン(plan.md §3.2)。素の Python + psycopg2 で SQL を実行する。

ステップ:
    seed          : スキーマ・raw テーブル作成 + CSV を COPY で投入
    build_staging : staging.stg_orders を再作成
    build_mart    : mart.daily_sales(テーブル)と mart.customer_summary(ビュー)を再作成

フェーズ1 時点では OpenLineage イベントは発行しない(フェーズ2 で追加する)。

使い方:
    python pipeline/run_pipeline.py --data-dir data/seed/csv                # 全ステップ
    python pipeline/run_pipeline.py --data-dir data/seed/csv --steps seed   # seed のみ
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg2

SQL_DIR = Path(__file__).parent / "sql"
RAW_TABLES = ["customers", "products", "orders", "order_items"]
ALL_STEPS = ["seed", "build_staging", "build_mart"]


def connect():
    return psycopg2.connect(
        host=os.environ.get("DEMO_DB_HOST", "postgres-demo"),
        port=int(os.environ.get("DEMO_DB_PORT", "5432")),
        user=os.environ.get("DEMO_DB_USER", "demo"),
        password=os.environ.get("DEMO_DB_PASSWORD", "demo_password"),
        dbname=os.environ.get("DEMO_DB_NAME", "demo"),
    )


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


def step_build_mart(conn):
    with conn.cursor() as cur:
        run_sql_file(cur, SQL_DIR / "03_mart.sql")
        cur.execute("SELECT count(*) FROM mart.daily_sales")
        print(f"[build_mart] mart.daily_sales: {cur.fetchone()[0]} 行")
        cur.execute("SELECT count(*) FROM mart.customer_summary")
        print(f"[build_mart] mart.customer_summary(ビュー): {cur.fetchone()[0]} 行")
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/seed/csv",
                        help="投入する CSV のディレクトリ(既定: data/seed/csv)")
    parser.add_argument("--steps", default=",".join(ALL_STEPS),
                        help=f"実行ステップ(カンマ区切り。既定: {','.join(ALL_STEPS)})")
    args = parser.parse_args()

    steps = args.steps.split(",")
    unknown = set(steps) - set(ALL_STEPS)
    if unknown:
        print(f"エラー: 未知のステップ {sorted(unknown)}", file=sys.stderr)
        return 2

    conn = connect()
    try:
        for step in steps:
            print(f"=== step: {step} ===")
            if step == "seed":
                step_seed(conn, Path(args.data_dir))
            elif step == "build_staging":
                step_build_staging(conn)
            elif step == "build_mart":
                step_build_mart(conn)
        print("パイプライン完了")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
