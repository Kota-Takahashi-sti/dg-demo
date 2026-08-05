#!/usr/bin/env bash
# シナリオ C-3: リネージュ(比較軸3: Marquez との思想の違い)(正常系・exit 0)
# - mart.customer_summary(ビュー): DatabaseLineage ワークフローが定義 SQL を解析して
#   自動でリネージュを導出する(実行イベント不要 = メタデータ駆動)
# - mart.daily_sales(CTAS テーブル): 定義 SQL が DB に残らないため自動導出できず、
#   Lineage API で手動登録する(手段の違いもデモの一部)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase3/demo-catalog-lineage.log"

ensure_base
seed_data clean
ensure_catalog

echo
echo "=== 前提: メタデータ取り込み(ビュー定義 SQL もこの段階で取り込まれる)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/ingest.yaml

echo
echo "=== C-3a: ビュー定義の SQL 解析による自動リネージュ(DatabaseLineage)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/lineage.yaml

echo
echo "=== C-3b: CTAS テーブルのリネージュを Lineage API で手動登録 ==="
$TOOLS_RUN $PYTHON_CATALOG catalog/om_api.py register-lineage

echo
echo "=== 証跡: リネージュグラフを API から保存 ==="
save_om_api verification/phase3/api-lineage-customer-summary.json lineage demo_postgres.demo.mart.customer_summary
save_om_api verification/phase3/api-lineage-daily-sales.json lineage demo_postgres.demo.mart.daily_sales

echo
echo "OpenMetadata UI: 各テーブルの Lineage タブでグラフを確認できます。"
echo "Marquez(フェーズ2)との違い: パイプラインを一度も実行せずにリネージュが得られる一方、"
echo "Run(実行履歴・成功/失敗)の概念はありません。詳細は docs/guides/catalog.md 参照。"
echo "リネージュデモ結果: 成功(exit 0)"
