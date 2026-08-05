# データガバナンス OSS デモ環境 — 全デモの単一コマンド入口
# 実体は scenarios/*.sh に置き、Makefile は薄く保つ(plan.md §2)。
SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help setup build-tools up-base up-lineage down-lineage up-catalog down-catalog \
        down clean-db seed \
        demo-quality-soda demo-quality-soda-ng demo-quality-gx demo-quality-gx-ng \
        demo-lineage demo-lineage-fail \
        demo-catalog-ingest demo-catalog-profile demo-catalog-lineage demo-catalog-drift \
        demo-contract-export demo-contract-test demo-contract-violation \
        demo-contract-breaking demo-contract-ci demo-contract-precommit \
        install-contract-hook

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-24s %s\n", $$1, $$2}'

setup: ## 初回セットアップ(.env 作成 + tools イメージビルド)
	@test -f .env || (cp .env.example .env && echo ".env を作成しました(デモ用設定値)")
	$(COMPOSE) --profile tools build tools

build-tools: ## tools イメージを再ビルド
	$(COMPOSE) --profile tools build tools

up-base: ## デモ用 DB(profile: base)を起動
	$(COMPOSE) --profile base up -d --wait postgres-demo

up-lineage: ## Marquez 一式(profile: lineage)を起動
	$(COMPOSE) --profile lineage up -d --wait

down-lineage: ## Marquez 一式のみ停止(データは保持)
	$(COMPOSE) --profile lineage down

up-catalog: ## OpenMetadata 一式(profile: catalog)を起動
	$(COMPOSE) --profile catalog up -d --wait

down-catalog: ## OpenMetadata 一式のみ停止(データは保持)
	$(COMPOSE) --profile catalog down

down: ## 全サービス停止(データは保持)
	$(COMPOSE) --profile base --profile tools --profile lineage --profile catalog --profile contract down

clean-db: ## 全サービス停止 + DB データ削除(OpenMetadata のカタログ内容も消える)
	$(COMPOSE) --profile base --profile tools --profile lineage --profile catalog --profile contract down -v

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

# --- 領域B: データリネージュ(OpenLineage / Marquez)---
demo-lineage: ## B-1 パイプライン実行 → Marquez でリネージュ確認(正常系・exit 0)
	scenarios/demo_lineage.sh

demo-lineage-fail: ## B-2 失敗 Run の追跡(FAIL イベント検知 → 非0 終了)
	scenarios/demo_lineage_fail.sh

# --- 領域C: データカタログ(OpenMetadata)---
demo-catalog-ingest: ## C-1 メタデータ取り込み → カタログ閲覧(正常系・exit 0)
	scenarios/demo_catalog_ingest.sh

demo-catalog-profile: ## C-2 プロファイリング + サンプルデータ格納(正常系・exit 0)
	scenarios/demo_catalog_profile.sh

demo-catalog-lineage: ## C-3 リネージュ(SQL 解析の自動導出 + API 手動登録)(正常系・exit 0)
	scenarios/demo_catalog_lineage.sh

demo-catalog-drift: ## C-4 スキーマ変更(列削除)の検知(異常系・非0 終了)
	scenarios/demo_catalog_drift.sh

# --- 領域D: データコントラクト(datacontract-cli)---
demo-contract-export: ## D-1 契約の可視化(export html/mermaid ほか)(正常系・exit 0)
	scenarios/demo_contract_export.sh

demo-contract-test: ## D-2 契約テスト(実 DB へスキーマ+品質+SLA を検証)(正常系・exit 0)
	scenarios/demo_contract_test.sh

demo-contract-violation: ## D-3 データ違反の検知(異常系・非0 終了)
	scenarios/demo_contract_violation.sh

demo-contract-breaking: ## D-4 破壊的変更(v1→v2)の検知(異常系・非0 終了)
	scenarios/demo_contract_breaking.sh

demo-contract-ci: ## D-5 CI 構成の検証(YAML 静的検証 + ローカル等価実行)(正常系・exit 0)
	scenarios/demo_contract_ci.sh

demo-contract-precommit: ## D-6 pre-commit フックが破壊的変更のコミットをブロック(非0 終了)
	scenarios/demo_contract_precommit.sh

install-contract-hook: ## pre-commit フック(破壊的変更ゲート)を .git/hooks に導入
	install -m 755 contracts/hooks/pre-commit .git/hooks/pre-commit
	@echo "pre-commit フックを導入しました(解除: rm .git/hooks/pre-commit)"
