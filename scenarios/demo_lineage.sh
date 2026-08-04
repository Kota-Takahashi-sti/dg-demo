#!/usr/bin/env bash
# シナリオ B-1: パイプライン実行 → OpenLineage イベント発行 → Marquez で確認(正常系・exit 0)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase2/demo-lineage.log"

ensure_base
ensure_lineage

echo
echo "=== クリーンデータでパイプライン実行(OpenLineage イベント発行あり)==="
$TOOLS_RUN $PYTHON_LINEAGE pipeline/run_pipeline.py \
    --data-dir data/seed/csv --openlineage

echo
echo "=== 証跡: Marquez API レスポンスを保存 ==="
save_marquez_api verification/phase2/api-namespaces.json namespaces
save_marquez_api verification/phase2/api-jobs.json jobs
save_marquez_api verification/phase2/api-datasets.json datasets
save_marquez_api verification/phase2/api-dataset-daily-sales.json dataset demo.mart.daily_sales
save_marquez_api verification/phase2/api-lineage-daily-sales.json lineage demo.mart.daily_sales

echo
echo "Marquez UI: http://localhost:${MARQUEZ_WEB_HOST_PORT:-3000} で"
echo "ジョブ(demo_pipeline)とリネージュグラフ(raw → staging → mart)を確認できます。"
echo "リネージュデモ結果: 全ステップ COMPLETE(exit 0)"
