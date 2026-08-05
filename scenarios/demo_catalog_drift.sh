#!/usr/bin/env bash
# シナリオ C-4: スキーマ変更の検知(異常系・非0 終了)
# raw.customers から列を削除して再取り込みし、カタログのバージョン履歴に
# 破壊的変更(列削除)が記録されることを確認する。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase3/demo-catalog-drift.log"

ensure_base
seed_data clean
ensure_catalog

echo
echo "=== 前提: ベースラインの取り込み(prefecture 列がある状態)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/ingest.yaml
save_om_api verification/phase3/api-drift-versions-before.json versions demo_postgres.demo.raw.customers

echo
echo "=== スキーマ変更: raw.customers.prefecture 列を削除 ==="
$COMPOSE exec -T postgres-demo \
    psql -U "${DEMO_DB_USER:-demo}" -d "${DEMO_DB_NAME:-demo}" \
    -c "ALTER TABLE raw.customers DROP COLUMN prefecture;"

echo
echo "=== 再取り込み(変更後のスキーマをカタログへ反映)==="
$TOOLS_RUN $PYTHON_CATALOG catalog/run_ingestion.py ingest catalog/ingest.yaml

echo
echo "=== カタログ上の差分を検査(バージョン履歴の changeDescription)==="
save_om_api verification/phase3/api-drift-versions-after.json versions demo_postgres.demo.raw.customers
if $TOOLS_RUN $PYTHON_CATALOG catalog/om_api.py drift-check demo_postgres.demo.raw.customers prefecture; then
    echo
    echo "スキーマ変更(列削除)がカタログのバージョン履歴に記録されました。"
    echo "UI: raw.customers を開き、ヘッダのバージョン番号 → バージョン履歴で差分を確認できます。"
    echo "データを元に戻すには: make seed(prefecture 列を含む状態で再作成後、"
    echo "make demo-catalog-ingest で再取り込み)"
    echo "スキーマ変更検知デモ結果: 破壊的変更を検知(非0 終了)"
    exit 1
else
    echo "エラー: 列削除がカタログのバージョン履歴に記録されていません(デモ失敗)" >&2
    exit 2
fi
