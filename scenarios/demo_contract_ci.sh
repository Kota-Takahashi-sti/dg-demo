#!/usr/bin/env bash
# シナリオ D-5: CI 構成の検証
#   GitHub Actions は本デモの開発環境から実行できない(CLAUDE.md「環境上の既知の制約」)。
#   そのため .github/workflows/contract.yml を次の 2 段で検証する(正常系・exit 0):
#     (a) actionlint 1.7.12 によるワークフロー YAML の静的検証
#     (b) ワークフローの各ステップと同一コマンドのローカル実行
#         (正常な PR 相当は exit 0、破壊的変更の PR 相当は非0 = ブロック動作を確認)
#   (c) act によるローカル実行の結果は docs/guides/contract.md と build-log.md に記載。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-ci.log"

WORKFLOW=.github/workflows/contract.yml

echo
echo "=== (a) ワークフロー YAML の静的検証(actionlint 1.7.12)==="
docker run --rm -v "$REPO_ROOT":/repo -w /repo rhysd/actionlint:1.7.12 "$WORKFLOW"
echo "actionlint: 問題は検出されませんでした(exit 0)"

echo
echo "=== (b) ワークフローと同一コマンドのローカル実行 ==="
ensure_base
seed_data clean

echo
echo "--- job: contract-gate / step: 契約の構文検証(lint)---"
$DC_RUN lint contracts/daily_sales.yaml

echo
echo "--- job: contract-gate / step: 破壊的変更の判定(正常な PR 相当: 契約変更なし)---"
$DC_PYTHON_RUN contracts/check_breaking.py contracts/daily_sales.yaml contracts/daily_sales.yaml
echo "→ exit 0(このジョブは成功し、PR はブロックされない)"

echo
echo "--- job: contract-gate / step: 破壊的変更の判定(破壊的変更を含む PR 相当: v1 → v2)---"
if $DC_PYTHON_RUN contracts/check_breaking.py contracts/daily_sales.yaml contracts/daily_sales.v2-breaking.yaml; then
    echo "エラー: 破壊的変更を検知できなかった(CI ゲートが機能していない)" >&2
    exit 2
fi
echo "→ 期待どおり非0 終了(このジョブは fail し、PR がブロックされる)"

echo
echo "--- job: contract-test / step: 契約テスト(datacontract ci)---"
$DC_RUN ci contracts/daily_sales.yaml --server local

echo
echo "CI 検証結果: (a) 静的検証 OK、(b) ローカル等価実行 OK(exit 0)"
