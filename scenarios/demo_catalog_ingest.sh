#!/usr/bin/env bash
# シナリオ C-1: メタデータ取り込み → カタログ閲覧(正常系・exit 0)
# raw/staging/mart のテーブル・ビューを OpenMetadata に取り込み、
# 説明・オーナー・タグ・用語集を API で付与してカタログらしい状態を作る。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase3/demo-catalog-ingest.log"

ensure_base
seed_data clean
ensure_catalog

echo
echo "=== C-1: メタデータ取り込み(metadata ingest / Postgres コネクタ)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/ingest.yaml

echo
echo "=== 手入力メタデータの付与(説明・オーナー・タグ・用語集。API 経由)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/om_api.py enrich

echo
echo "=== 証跡: OpenMetadata API レスポンスを保存 ==="
save_om_api verification/phase3/api-tables.json tables
save_om_api verification/phase3/api-table-daily-sales.json table demo_postgres.demo.mart.daily_sales
save_om_api verification/phase3/api-table-customers.json table demo_postgres.demo.raw.customers

echo
echo "OpenMetadata UI: http://localhost:${OM_SERVER_HOST_PORT:-8585} に"
echo "admin@open-metadata.org / admin でログインし、Explore からテーブルを検索できます。"
echo "カタログ取り込みデモ結果: 成功(exit 0)"
