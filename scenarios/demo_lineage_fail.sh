#!/usr/bin/env bash
# シナリオ B-2: パイプライン失敗の追跡(異常系・FAIL イベント検知で非0 終了)
# build_mart を意図的に失敗させ(壊れた SQL)、Marquez 上で Run が FAILED になることを確認する。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase2/demo-lineage-fail.log"

ensure_base
ensure_lineage

echo
echo "=== パイプライン実行(--simulate-failure: build_mart が壊れた SQL で失敗する)==="
if $TOOLS_RUN $PYTHON_LINEAGE pipeline/run_pipeline.py \
        --data-dir data/seed/csv --openlineage --simulate-failure; then
    echo "エラー: 失敗するはずのパイプラインが成功しました(シナリオ不成立)"
    exit 1
fi
echo "(パイプラインは想定どおり build_mart で失敗し、FAIL イベントを発行しました)"

echo
echo "=== 証跡: build_mart の Run 履歴を Marquez API から取得 ==="
save_marquez_api verification/phase2/api-runs-build-mart.json runs run_pipeline.build_mart

echo
echo "=== 検知結果: 最新 Run の状態 ==="
if grep -m1 '"state": "FAILED"' verification/phase2/api-runs-build-mart.json; then
    echo "Marquez 上で run_pipeline.build_mart の Run が FAILED として記録されています。"
    echo "UI: http://localhost:${MARQUEZ_WEB_HOST_PORT:-3000} の Jobs → run_pipeline.build_mart でも確認できます。"
    echo "リネージュ異常系デモ結果: 失敗 Run を検知(exit 1)"
    exit 1
else
    echo "エラー: FAILED の Run が Marquez に記録されていません(シナリオ不成立)"
    exit 2
fi
