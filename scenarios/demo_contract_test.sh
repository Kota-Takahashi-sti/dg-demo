#!/usr/bin/env bash
# シナリオ D-2: 契約テスト正常系
#   クリーンデータを投入し、ODCS 契約を実データベースに対して検証する。
#   スキーマ(列の存在・型)+ 品質(nullValues / duplicateValues / rowCount / SQL)+
#   SLA(retention)が 1 コマンドで検査される(正常系・exit 0)。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-test.log"

ensure_base
seed_data clean

echo
echo "=== datacontract test(契約を実 DB へ検証: スキーマ + 品質 + SLA)==="
$DC_RUN test contracts/daily_sales.yaml --server local \
    --output verification/phase4/test-results-clean.json --output-format json
echo "[証跡] verification/phase4/test-results-clean.json(テスト結果の JSON)"

echo
echo "datacontract 結果: 契約テスト成功(exit 0)"
