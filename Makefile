# データガバナンス OSS デモ環境 — 全デモの単一コマンド入口
# 実体は scenarios/*.sh に置き、Makefile は薄く保つ(plan.md §2)。
SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help setup build-tools up-base down clean-db seed \
        demo-quality-soda demo-quality-soda-ng demo-quality-gx demo-quality-gx-ng

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-24s %s\n", $$1, $$2}'

setup: ## 初回セットアップ(.env 作成 + tools イメージビルド)
	@test -f .env || (cp .env.example .env && echo ".env を作成しました(デモ用設定値)")
	$(COMPOSE) --profile tools build tools

build-tools: ## tools イメージを再ビルド
	$(COMPOSE) --profile tools build tools

up-base: ## デモ用 DB(profile: base)を起動
	$(COMPOSE) --profile base up -d --wait postgres-demo

down: ## 全サービス停止(データは保持)
	$(COMPOSE) --profile base --profile tools down

clean-db: ## 全サービス停止 + DB データ削除
	$(COMPOSE) --profile base --profile tools down -v

seed: ## クリーンデータを DB に投入(raw→staging→mart)
	$(COMPOSE) --profile base up -d --wait postgres-demo
	$(COMPOSE) --profile tools run --rm -T tools \
		/opt/venv/quality/bin/python pipeline/run_pipeline.py --data-dir data/seed/csv

# --- 領域A: データ品質(Soda Core / Great Expectations)---
demo-quality-soda: ## A-1 Soda 正常系(全チェック成功 → exit 0)
	scenarios/demo_quality_soda.sh clean

demo-quality-soda-ng: ## A-2 Soda 異常系(違反検知 → 非0 終了)
	scenarios/demo_quality_soda.sh ng

demo-quality-gx: ## A-3 GX 正常系(全チェック成功 → exit 0)
	scenarios/demo_quality_gx.sh clean

demo-quality-gx-ng: ## A-4 GX 異常系(違反検知 → 非0 終了)
	scenarios/demo_quality_gx.sh ng
