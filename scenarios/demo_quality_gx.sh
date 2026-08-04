#!/usr/bin/env bash
# シナリオ A-3 / A-4: Great Expectations によるデータ品質チェック
#   引数: clean(正常系・exit 0)| ng(異常系・違反検知で非0)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

MODE="${1:-clean}"
SUFFIX=""; [ "$MODE" = "ng" ] && SUFFIX="-ng"
setup_log "verification/phase1/demo-quality-gx${SUFFIX}.log"

ensure_base
seed_data "$MODE"

echo
echo "=== Great Expectations 1.19.1: checkpoint 実行(4チェック)==="
if $TOOLS_RUN $PYTHON_QUALITY quality/gx/run_checks.py; then
    echo "GX 結果: 全チェック成功(exit 0)"
    exit 0
else
    echo "GX 結果: 品質違反を検知(exit 1)"
    exit 1
fi
