#!/usr/bin/env bash
# 各デモシナリオ共通の関数群。scenarios/*.sh から source される。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# .env(compose と同じ設定値)をシェルにも読み込む。
# シナリオ内のメッセージ(ポート番号等)を compose の実際の設定と一致させるため。
if [ -f .env ]; then
    set -a; source .env; set +a
fi

COMPOSE="docker compose"
# tools は常駐させず都度実行する(plan.md §3.4)
TOOLS_RUN="$COMPOSE --profile tools run --rm -T tools"
PYTHON_QUALITY="/opt/venv/quality/bin/python"
PYTHON_LINEAGE="/opt/venv/lineage/bin/python"
PYTHON_CATALOG="/opt/venv/catalog/bin/python"
SODA="/opt/venv/quality/bin/soda"
# contract は datacontract-cli 公式イメージを都度実行する(plan.md §3.4、フェーズ4)
DC_RUN="$COMPOSE --profile contract run --rm -T datacontract"
# 判定スクリプト等はイメージ同梱の Python(pyyaml あり)で実行する(tools の再ビルド不要)
DC_PYTHON_RUN="$COMPOSE --profile contract run --rm -T --entrypoint python datacontract"

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

ensure_lineage() {
    echo "--- Marquez 一式(profile: lineage)を起動 ---"
    $COMPOSE --profile lineage up -d --wait
    echo "--- Marquez API の起動を待機 ---"
    $TOOLS_RUN $PYTHON_LINEAGE lineage/marquez_api.py wait
}

# Marquez API レスポンスを証跡として保存する
# 使い方: save_marquez_api <保存先ファイル> <marquez_api.py のサブコマンド...>
save_marquez_api() {
    local out="$1"; shift
    mkdir -p "$(dirname "$out")"
    $TOOLS_RUN $PYTHON_LINEAGE lineage/marquez_api.py "$@" > "$out"
    echo "[証跡] $out(marquez_api.py $*)"
}

ensure_catalog() {
    echo "--- OpenMetadata 一式(profile: catalog)を起動 ---"
    local start=$SECONDS
    # om-migrate は成功時に終了するワンショットのため、podman-compose の
    # `up --wait` では完了待ちにならない。REST API の応答で起動完了を判定する。
    $COMPOSE --profile catalog up -d
    echo "--- OpenMetadata サーバの起動を待機 ---"
    $TOOLS_RUN $PYTHON_CATALOG catalog/om_api.py wait
    echo "(起動所要: $((SECONDS - start)) 秒。初回はイメージ展開と DB 移行でさらにかかる)"
}

# OpenMetadata API レスポンスを証跡として保存する
# 使い方: save_om_api <保存先ファイル> <om_api.py のサブコマンド...>
save_om_api() {
    local out="$1"; shift
    mkdir -p "$(dirname "$out")"
    $TOOLS_RUN $PYTHON_CATALOG catalog/om_api.py "$@" > "$out"
    echo "[証跡] $out(om_api.py $*)"
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
