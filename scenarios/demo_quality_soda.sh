#!/usr/bin/env bash
# シナリオ A-1 / A-2: Soda Core によるデータ品質チェック
#   引数: clean(正常系・exit 0)| ng(異常系・違反検知で非0)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

MODE="${1:-clean}"
SUFFIX=""; [ "$MODE" = "ng" ] && SUFFIX="-ng"
setup_log "verification/phase1/demo-quality-soda${SUFFIX}.log"

ensure_base
seed_data "$MODE"

echo
echo "=== Soda Core 4.19.0: contract verify(4チェック / 3 contract)==="
FAILED=0
for contract in quality/soda/contracts/raw_customers.yaml \
                quality/soda/contracts/raw_orders.yaml \
                quality/soda/contracts/raw_order_items.yaml; do
    echo
    echo "--- $contract ---"
    if ! $TOOLS_RUN $SODA contract verify \
            --data-source quality/soda/ds_config.yml \
            --contract "$contract"; then
        FAILED=1
    fi
done

echo
if [ "$FAILED" -eq 0 ]; then
    echo "Soda 結果: 全 contract 成功(exit 0)"
else
    echo "Soda 結果: 品質違反を検知(exit 1)"
fi
exit "$FAILED"
