#!/usr/bin/env bash
# シナリオ D-4: 破壊的変更の検知(異常系)
#   契約 v1 → v2(列削除・型変更を含む)の差分を datacontract changelog で表示し、
#   自作判定スクリプト contracts/check_breaking.py で破壊的変更と判定して非0 で終了する。
#   (datacontract-cli には breaking 判定コマンドがなく、changelog は常に exit 0。
#    設計判断は docs/build-log.md 参照。DB は使わないため base 起動は不要)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-breaking.log"

V1=contracts/daily_sales.yaml
V2=contracts/daily_sales.v2-breaking.yaml

echo
echo "=== 1) 両契約の構文検証(lint)— どちらも ODCS としては正しい ==="
$DC_RUN lint "$V1"
$DC_RUN lint "$V2"

echo
echo "=== 2) datacontract changelog による差分表示(参考表示・常に exit 0)==="
$DC_RUN changelog "$V1" "$V2" | tee verification/phase4/changelog-v1-v2.txt
echo "[証跡] verification/phase4/changelog-v1-v2.txt"

echo
echo "=== 3) 自作判定スクリプトによる破壊的変更の判定 ==="
if $DC_PYTHON_RUN contracts/check_breaking.py "$V1" "$V2"; then
    echo "エラー: 破壊的変更を検知できなかった(デモ失敗)" >&2
    exit 2
fi

echo
echo "datacontract 結果: 破壊的変更を検知(exit 1)"
exit 1
