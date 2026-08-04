#!/usr/bin/env bash
# 各デモシナリオ共通の関数群。scenarios/*.sh から source される。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE="docker compose"
# tools は常駐させず都度実行する(plan.md §3.4)
TOOLS_RUN="$COMPOSE --profile tools run --rm -T tools"
PYTHON_QUALITY="/opt/venv/quality/bin/python"
SODA="/opt/venv/quality/bin/soda"

# ログ設定: 標準出力・標準エラーを加工せず verification/ に保存する(DoD)
setup_log() {
    local log_path="$1"
    mkdir -p "$(dirname "$log_path")"
    exec > >(tee "$log_path") 2>&1
    echo "# 実行日時: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "# コマンドログ: $log_path"
}

ensure_base() {
    echo "--- デモ用 DB(profile: base)を起動 ---"
    $COMPOSE --profile base up -d --wait postgres-demo
}

# $1: clean | ng
seed_data() {
    local mode="$1"
    if [ "$mode" = "ng" ]; then
        echo "--- 汚染データを生成(--inject all)して投入 ---"
        $TOOLS_RUN $PYTHON_QUALITY data/seed/generate.py \
            --out data/seed/csv-injected --inject all
        $TOOLS_RUN $PYTHON_QUALITY pipeline/run_pipeline.py \
            --data-dir data/seed/csv-injected
    else
        echo "--- クリーンデータ(コミット済み seed CSV)を投入 ---"
        $TOOLS_RUN $PYTHON_QUALITY pipeline/run_pipeline.py \
            --data-dir data/seed/csv
    fi
}
