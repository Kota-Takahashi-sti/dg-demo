#!/usr/bin/env bash
# シナリオ C-2: プロファイリング(行数・欠損率・分布)+ サンプルデータ格納(正常系・exit 0)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase3/demo-catalog-profile.log"

ensure_base
seed_data clean
ensure_catalog

echo
echo "=== 前提: メタデータ取り込み(C-1 未実行でも単体で動くよう再実行)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/ingest.yaml

echo
echo "=== C-2a: プロファイラ(metadata profile / 行数・欠損率などの統計)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py profile catalog/profiler.yaml

echo
echo "=== C-2b: 自動分類 + サンプルデータ格納(metadata classify)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py classify catalog/classify.yaml

echo
echo "=== 証跡: プロファイル結果を API から保存 ==="
save_om_api verification/phase3/api-profile-customers.json profile demo_postgres.demo.raw.customers
save_om_api verification/phase3/api-profile-daily-sales.json profile demo_postgres.demo.mart.daily_sales

echo
echo "OpenMetadata UI: 各テーブルの Profiler & Data Quality タブと Sample Data タブで"
echo "行数・欠損率・分布とサンプル行を確認できます。"
echo "プロファイリングデモ結果: 成功(exit 0)"
