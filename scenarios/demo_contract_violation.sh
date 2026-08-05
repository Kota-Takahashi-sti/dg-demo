#!/usr/bin/env bash
# シナリオ D-3: データ違反の検知(異常系)
#   クリーンデータ投入後、mart.daily_sales に契約違反(重複日付・負の売上・NULL)を
#   意図的に注入し、D-2 と同じ契約でテストして違反が検知されることを確認する。
#   検知に成功したら非0(exit 1)で終了する。検知できなければ exit 2(デモ失敗)。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-violation.log"

ensure_base
seed_data clean

echo
echo "--- 契約違反を注入(contracts/sql/inject_violation.sql)---"
echo "    違反1: 重複日付 / 違反2: 負の売上合計 / 違反3: NULL の注文数"
$COMPOSE exec -T postgres-demo psql -U "${DEMO_DB_USER:-demo}" -d "${DEMO_DB_NAME:-demo}" \
    -v ON_ERROR_STOP=1 < contracts/sql/inject_violation.sql

echo
echo "=== D-2 と同じ契約でテスト(違反を検知するはず)==="
if $DC_RUN test contracts/daily_sales.yaml --server local \
        --output verification/phase4/test-results-violation.json --output-format json; then
    echo "エラー: 契約違反を検知できなかった(デモ失敗)" >&2
    exit 2
fi
echo "[証跡] verification/phase4/test-results-violation.json(テスト結果の JSON)"

echo
echo "datacontract 結果: 契約違反を検知(exit 1)"
echo "(mart.daily_sales は汚染されたままです。復旧するには make seed を実行してください)"
exit 1
