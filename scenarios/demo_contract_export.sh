#!/usr/bin/env bash
# シナリオ D-1: データコントラクトの可視化(export)
#   ODCS 契約を lint で検証し、html / mermaid / markdown へ変換して証跡に保存する。
#   あわせて sodacl / great-expectations へ変換し、「契約から品質チェックを導出できる」
#   という領域A(データ品質)との概念的なつながりを示す(正常系・exit 0)。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-export.log"

OUT=verification/phase4/export
mkdir -p "$OUT"

echo
echo "=== datacontract-cli 1.1.0: 契約の構文検証(lint)==="
$DC_RUN lint contracts/daily_sales.yaml

echo
echo "=== 契約を利害関係者向けの形式に変換(export)==="
$DC_RUN export html contracts/daily_sales.yaml --output "$OUT/daily_sales.html"
echo "[証跡] $OUT/daily_sales.html(ブラウザで開ける契約仕様書)"
$DC_RUN export mermaid contracts/daily_sales.yaml --output "$OUT/daily_sales.mmd"
echo "[証跡] $OUT/daily_sales.mmd(ER 図。以下に内容を表示)"
cat "$OUT/daily_sales.mmd"
$DC_RUN export markdown contracts/daily_sales.yaml --output "$OUT/daily_sales.md"
echo "[証跡] $OUT/daily_sales.md(Markdown 形式の契約仕様書)"

echo
echo "=== 契約から品質チェック定義を導出(領域Aとのつながり)==="
$DC_RUN export sodacl contracts/daily_sales.yaml --output "$OUT/daily_sales.sodacl.yaml"
echo "[証跡] $OUT/daily_sales.sodacl.yaml(SodaCL 形式。Soda Core 3.x 系の記法)"
$DC_RUN export great-expectations contracts/daily_sales.yaml --output "$OUT/daily_sales.gx.json"
echo "[証跡] $OUT/daily_sales.gx.json(Great Expectations の Expectation Suite)"

echo
echo "datacontract 結果: 契約の可視化 5 形式を保存(exit 0)"
