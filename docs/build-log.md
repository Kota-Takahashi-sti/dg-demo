# build-log.md — 構築記録(随時追記)

## 2026-08-04 フェーズ0 開始

### 環境検証(生ログ: `verification/phase0/`)

- `01_docker_environment.log`
  - Docker Engine 28.1.1(client/server とも)、Docker Compose v2.35.1、buildx v0.23.0 を確認。
  - ホスト: WSL2 上の Ubuntu 24.04.2、x86_64(amd64)、CPU 14、メモリ 15.36 GiB。
  - Cgroup v1、overlay2。既存コンテナ多数(89、稼働2)・イメージ132 あり → ディスク残量に注意。
  - 注意: 実行環境は amd64。CLAUDE.md の要件により compose 定義は arm64/amd64 両対応とするが、
    arm64 での実機検証は本環境では不可 → 既知の制約として plan.md に記載する。
- `02_registry_connectivity.log`
  - Docker Hub への pull(hello-world)と run が成功。レジストリ接続に問題なし。
  - 各候補製品イメージの pull 検証は、バージョン調査でタグを確定した後に実施する
    (「pull できること」の検証を採用予定タグそのもので行うため)。

### バージョン調査(進行中)

- 4領域(Soda Core / GX、OpenLineage / Marquez、OpenMetadata、datacontract-cli / ODCS)について
  公式リリース情報・ドキュメントの Web 調査を並行実施中。調査日: 2026-08-04。
  結果は確定次第この下に追記し、plan.md の採用バージョン一覧に反映する。

#### データ品質: Soda Core / Great Expectations(調査日 2026-08-04)

- **Soda Core 4.19.0**(2026-07-28、PyPI `soda-postgres`)を採用候補とする。
  - v4 系(初回 v4.0.5、2026-01-28)は SodaCL を廃し**データコントラクト YAML** が既定の記法。
    v3(SodaCL)は公式に legacy 扱い(最終リリース 3.5.6 / 2025-09-24、`v3` ブランチ)。
  - ライセンス: v4 は **Elastic License 2.0**(main ブランチ LICENSE で確認。
    2026-01-27 の公式ブログで Apache-2.0→ELv2 移行を告知。ローカル・社内利用は無料で可)。
    CLAUDE.md で ELv2 は許容済み。v3 は Apache-2.0。
  - Soda Cloud 接続は**不要**(README 明記)。`soda contract verify -ds ds.yml -c contract.yml` でローカル完結。
  - 注意: 公式ドキュメントの一部インストール手順は有償チャネル `pypi.cloud.soda.io` を指す。
    本プロジェクトは**公開 PyPI の `soda-postgres==4.19.0`** を使う。
  - 参照: github.com/sodadata/soda-core(README/LICENSE)、pypi.org/project/soda-postgres/、
    docs.soda.io(contract-language-reference、release-notes)、soda.io/blog(ライセンス告知)
- **Great Expectations 1.19.1**(2026-07-24、PyPI `great-expectations`、Apache-2.0)を採用候補とする。
  - 1.x API(`gx.get_context()` → data_sources → batch_definition → suites → validation_definitions →
    checkpoints)を公式ドキュメントで確認。GX Cloud 不要でローカル完結可。
  - Postgres は extras `great_expectations[postgresql]`。
  - 参照: pypi.org/project/great-expectations/、github releases、docs.greatexpectations.io/docs/core/
- Python 互換: Soda >=3.10、GX >=3.10,<3.14 → デモ用 Python は **3.12** を共通採用予定。
- **設計への影響(重要)**: Soda v4 がコントラクト記法になったため、「Soda の手軽さ vs GX の表現力」
  比較軸は「宣言的コントラクト YAML vs Python ネイティブ API」という対比で設計する。
  また ODCS/datacontract-cli(フェーズ4)との概念的な関係(コントラクトの二重管理にならない整理)を
  plan.md で明示する必要がある。

#### リネージュ: OpenLineage / Marquez(調査日 2026-08-04)

- **OpenLineage 1.52.0**(2026-07-23、Apache-2.0、monorepo 一括バージョン)を採用候補とする。
  - Python クライアント `openlineage-python==1.52.0`(PyPI、Python >=3.10)。
  - オーケストレータなしの素の Python スクリプトからのイベント発行が公式にサポートされる:
    `event_v2` モデル(`RunEvent`/`RunState`/`InputDataset` 等)+ HTTP transport
    (`OPENLINEAGE__TRANSPORT__TYPE=http` 等の env 設定も可)。→ 「最小限の発行手段」の第一候補。
  - カラムレベルリネージュは公式 facet `columnLineage`(ColumnLineageDatasetFacet 1-2-0)があり、
    Python クライアントから `facet_v2.column_lineage_dataset` で手動付与可能(ソースで確認済み)。
  - 参照: github.com/OpenLineage/OpenLineage/releases、pypi.org/project/openlineage-python/、
    openlineage.io/docs/client/python、openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet
- **Marquez**: バージョン選定に注意点あり。
  - GitHub Release / CHANGELOG 上の最新は **0.50.0**(2024-10-24)。一方 git タグと Docker Hub には
    **0.51.0 / 0.51.1**(2025-03)が存在し、`latest` は 0.51.1 を指すが、リリースノート・CHANGELOG が無い。
  - **判断: 0.51.1 を採用**(プロジェクト自身の `latest` が指す最新公開イメージ。タグ固定で利用)。
    問題が出た場合は正式リリース済みの 0.50.0 へフォールバック(この判断を plan.md にも記載)。
  - ライセンス: Apache-2.0(GitHub license API で確認)。
  - イメージ: `marquezproject/marquez`(API)/ `marquezproject/marquez-web`(UI)。
    **amd64 のみで arm64 イメージ未提供** → Apple Silicon ではエミュレーション実行
    (compose に `platform: linux/amd64` 指定)。既知の制約として記録する。
  - 依存: PostgreSQL 14(公式 compose は `postgres:14`)、ポートは API 5000 / admin 5001 / Web 3000。
    macOS ではポート 5000 が予約される件が README に記載 → ガイドで代替ポートを案内する。
  - メモリ要件は公式未記載(JVM/Dropwizard + Postgres + Node web)→ フェーズ2 で実測して記録する。
  - 参照: github.com/MarquezProject/marquez(releases/CHANGELOG/README/docker-compose.yml)、
    hub.docker.com/r/marquezproject/marquez、marquezproject.ai/docs/quickstart

#### カタログ: OpenMetadata(調査日 2026-08-04)

- **OpenMetadata 1.13.3**(1.13.3-release、2026-07-31)を採用候補とする。
  2.0.0-rc1 が存在するが prerelease("DO NOT use this in PROD" 明記)のため不採用。
- ライセンスの注意点:
  - サーバ/リポジトリは **Apache-2.0**(GitHub API・README で確認)。
  - **PyPI `openmetadata-ingestion` は 1.6.0.0 以降 Collate Community License 1.0**
    (source-available・無料利用可、OSI 認定ではない)。CLAUDE.md の
    「OSS またはソース公開・無料利用可能」の範囲内と判断(Soda の ELv2 と同様の扱い)。
- Docker 構成(1.13.3 のリリースアセット compose を実際にダウンロードして確認):
  - イメージ: `docker.getcollate.io/openmetadata/server:1.13.3`、同 `ingestion:1.13.3`(Airflow ベース)、
    同 `postgresql:1.13.3`(PG variant)、`docker.elastic.co/elasticsearch/elasticsearch:9.3.0`。
  - **全イメージ amd64+arm64 のマルチアーチ提供**(レジストリ manifest で確認)。
  - 公式要件: **メモリ 6GiB / 4vCPU 以上**。ES は `-Xms1024m -Xmx1024m`。
  - **Airflow ingestion コンテナは CLI インジェスト(`metadata ingest -c ...`)のみなら不要**
    (公式 deployment ドキュメントで external ingestion が明記。server 単体 compose も公式提供)。
    → デモではメモリ節約のため ingestion コンテナを省略し CLI で取り込む方針。
  - ポート: UI/API 8585、ops 8586、ES 9200。既定ログイン: admin@open-metadata.org / admin。
  - 注意: docs の quickstart ページは 1.12.6 の URL のまま(ドキュメントがリリースに追随していない)。
    1.13.3 はリリースアセットの compose を使う。
- **OpenLineage 連携の重要な制約**: OpenMetadata の OpenLineage コネクタは **BETA で
  Kafka/Kinesis からの consume のみ**。HTTP で OL イベントを受け取るエンドポイントは無い。
  → Marquez と同じイベントを OpenMetadata に直接流すには Kafka が必要(重い)。
  **設計判断: OpenMetadata のリネージュは本来の思想どおり SQL 解析ベースの lineage workflow +
  必要に応じ lineage REST API(`/api/v1/lineage`)で構築する。** これは比較軸3
  (Marquez=実行時イベント駆動 vs OpenMetadata=メタデータ/SQL解析駆動)をむしろ純粋に見せられる。
- カラムレベルリネージュ: SQL 解析(`collate-sqllineage`)で自動生成+UI で手動編集可+API あり。
- Postgres 取り込み: `pip install "openmetadata-ingestion[postgres]"`(**1.13.3.0、
  requires_python >=3.9、docs は 3.9–3.11**)+ YAML workflow + `metadata ingest -c`。
  → **Python 3.10 or 3.11 に要調整**(Soda/GX の 3.12 案から変更の可能性。品質系と別 venv/イメージにする)。
- 参照: github.com/open-metadata/OpenMetadata/releases、docs.open-metadata.org
  (quick-start/local-docker-deployment、deployment/ingestion、connectors/database/postgres/yaml、
  connectors/pipeline/openlineage、how-to-guides/data-lineage/column)、pypi.org/project/openmetadata-ingestion/

#### コントラクト: datacontract-cli / ODCS(調査日 2026-08-04)

- **datacontract-cli 1.0.17**(2026-08-01、MIT、Python >=3.10,<3.15)を採用候補とする。
  Docker イメージ `datacontract/cli:1.0.17` あり(Docker Hub API で確認)。
- **重要な歴史的経緯(設計に直結)**:
  - v0.11.1(2025-12-14)で内部モデルが Data Contract Specification(DCS)から
    **ODCS(Open Data Contract Standard)へ全面移行**。DCS は deprecated。
    → コントラクトは **ODCS v3.1.0 形式**で書く(発注者の比較軸5とも一致)。
  - v1.0.0(2026-06-04)で **テストエンジンが Soda Core から ibis に置換**(soda 依存を完全削除)。
    `export sodacl` / `export great-expectations` は残存 → 品質領域との相互リンクのデモに使える。
  - **`datacontract breaking` / `diff` コマンドは v0.11.1 で削除済み**。
    `changelog`(v0.11.8 で再実装)は added/removed/updated を出すが **breaking 判定なし・常に exit 0**
    (main のソース command_changelog.py で確認)。
    → 破壊的変更デモは `changelog` の JSON 出力を小さなスクリプトで判定して非0終了させるか、
    `datacontract ci` / `test`(違反時 exit 非0)を組み合わせて設計する。
  - `datacontract ci`(v0.11.8 追加): CI 向け。GitHub Actions 検知で PR アノテーション+ジョブサマリ、
    `--fail-on`、junit/json 出力、違反時 exit 非0。ローカル実行でもワークフローと同一コマンド
    → GitHub Actions を実行できない本環境での等価検証手段として最適。
  - export 形式: html / mermaid / great-expectations / sodacl / dbt-models / sql / markdown ほか多数。
    0.12.0 で CLI 構文が位置引数化(`datacontract export html file.yaml`、`--format` 廃止)。
  - Postgres テスト: extras `datacontract-cli[postgres]`、資格情報は
    `DATACONTRACT_POSTGRES_USERNAME/PASSWORD` 環境変数(1.0.17 から host 等も env 上書き可、
    `--config-file` 対応)。`datacontract import postgres` で既存 DB からコントラクト生成可(1.0.15+)。
  - 注意: README の Python 記述(3.10–3.12 推奨)は古い。PyPI メタデータが正。
- **ODCS v3.1.0**(2025-12-08、Apache-2.0、Bitol / LF AI & Data)を採用。
  トップレベル: fundamentals(apiVersion/kind/id/version/status/description...)、schema、quality
  (3.1.0 で標準メトリクス rowCount/nullValues/duplicateValues 等)、team、roles、slaProperties、
  servers、customProperties 等 11 セクション。docs: bitol-io.github.io/open-data-contract-standard/latest/
- GitHub Actions: 公式 action `datacontract/datacontract-action` はあるがタグ・リリースなし(@main 参照のみ)
  → 公式ドキュメント推奨の「CLI 直接実行(`datacontract ci`)」パターンでワークフローを書く。
- 参照: github.com/datacontract/datacontract-cli(releases/README/CHANGELOG/ソース)、
  pypi.org/project/datacontract-cli/、docs.datacontract.com(commands/exports/testing/postgres/
  migrate-dcs-to-odcs/scheduling/github-actions)、github.com/bitol-io/open-data-contract-standard

#### 共通 Python バージョンの決定

- 制約: Soda >=3.10 / GX >=3.10,<3.14 / openlineage-python >=3.10 /
  openmetadata-ingestion >=3.9(docs は 3.9–3.11)/ datacontract-cli >=3.10,<3.15
- → **Python 3.11 を全ツール共通で採用**(全製品の交差範囲内。datacontract 公式も 3.11 推奨)。

#### インフラ(製品以外)の選定

- デモ用データ DB: **postgres:16**(全ツールのコネクタ実績が厚い安定版。データ基盤役であり
  4製品の「最新安定」要件の対象外。問題なければ 16 系最新パッチに追随)。
- Marquez メタ DB: **postgres:14**(Marquez 公式 compose / README 要件に従う)。
- OpenMetadata 用: 公式 compose 同梱の `openmetadata/postgresql:1.13.3` + `elasticsearch:9.3.0`。

### 採用予定イメージの pull 検証(2026-08-04)

- 確定タグ 9 イメージ(marquez 2種 / openmetadata 2種 / elasticsearch / datacontract-cli /
  postgres 16・14 / python:3.11-slim)の pull を実行。
  生ログ: `verification/phase0/04_image_pulls.log`
- **結果: 9/9 すべて成功(exit 0)**。docker.getcollate.io(OpenMetadata)、docker.elastic.co、
  Docker Hub のいずれからも取得可能なことを確認。環境検証は完了。

### フェーズ0 まとめ(2026-08-04)

- 成果物: docs/plan.md(6項目構成)、verification/phase0/ 生ログ4本、本ログ、PROGRESS.md 更新。
- 実装は未着手(フェーズ0 スコープ厳守)。plan.md のレビュー・承認待ち。

---

## フェーズ1: 基盤 + データ品質(2026-08-04 着手)

### 公式ドキュメント調査(Soda Core 4.19.0 / GX 1.19.1)— 調査日 2026-08-04

**Soda Core v4(参照 URL と確認内容)**

- docs.soda.io/soda-v4/reference/contract-language-reference
  - 契約 YAML の必須構造: トップレベル `dataset: <datasource>/<db>/<schema>/<dataset>` + `columns:`(各列 `name` / 任意 `data_type` / 任意 `checks:`)+ データセットレベル `checks:`。
  - 4チェックの構文を確認:
    - 欠損: `- missing:`(既定は欠損 0 件を要求。`threshold:` で許容量調整可)
    - 重複: `- duplicate:`(`threshold: must_be: 0` 等)
    - 値域: `- invalid:` + `valid_min` / `valid_max`
    - スキーマ: データセットレベル `- schema:`(columns の `data_type` 宣言と照合。`allow_extra_columns` / `allow_other_column_order` オプションあり)
- docs.soda.io/soda-v4/reference/cli-reference
  - ローカル実行(Soda Cloud 不要): `soda contract verify --data-source ds.yml --contract contract.yaml`(短縮 `-ds` / `-c`)。`--verbose` あり。
  - データソース設定の作成: `soda data-source create -f ds.yml`、接続テスト: `soda data-source test -ds ds.yml`。
  - **exit code は docs に明記なし → フェーズ1 で実測して本ログに記録する。**
- docs.soda.io/soda-v4/reference/data-source-reference-for-soda-core
  - postgres 設定 YAML: `type: postgres / name: ... / connection: {host, port, user, password, database}`。
  - 環境変数参照は `${env.VAR_NAME}` 構文(実行環境に環境変数が必要)。
  - 注意: CLI リファレンスの例は `data_source:` ラッパーあり、データソースリファレンスの例はラッパーなし。**どちらが正か実測で確認する。**

**Great Expectations 1.19.1(参照 URL と確認内容)**

- docs.greatexpectations.io/docs/core/connect_to_data/sql_data
  - 接続文字列: `postgresql+psycopg2://user:pass@host:port/db`
  - `context.data_sources.add_postgres(name=..., connection_string=...)` → `data_source.add_table_asset(table_name=..., name=...)` → `asset.add_batch_definition_whole_table(name=...)`
  - 公式例に `add_table_asset` の schema 引数の記載なし → **schema 指定方法(schema_name 引数の有無)は実装時に確認・記録。**
- docs.greatexpectations.io/docs/core/define_expectations/organize_expectation_suites
  - `suite = context.suites.add(gx.ExpectationSuite(name=...))` → `suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=...))`
- docs.greatexpectations.io/docs/core/run_validations/create_a_validation_definition
  - `ValidationDefinition`(batch definition + suite + name)を作成し validation に使う。
- docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/create_a_checkpoint_with_actions
  - `gx.Checkpoint(name=..., validation_definitions=[...], actions=[...], result_format={"result_format": "COMPLETE"})` → `context.checkpoints.add(checkpoint)` → `checkpoint.run()`。
  - `UpdateDataDocsAction(name=...)` で Data Docs 更新。result_format 既定は SUMMARY。

**チェック対応表(plan.md 領域A の4チェック → 両製品の実装)**

| チェック | Soda v4 | GX 1.x |
|---|---|---|
| (a) customers.email 欠損 0% | `missing:` | `ExpectColumnValuesToNotBeNull` |
| (b) orders.order_id 一意 | `duplicate:` | `ExpectColumnValuesToBeUnique` |
| (c) order_items.quantity>0・unit_price 値域 | `invalid: valid_min/valid_max` ×2 | `ExpectColumnValuesToBeBetween` ×2 |
| (d) orders スキーマ(列と型) | columns の `data_type` 宣言 + `schema:` チェック | `ExpectTableColumnsToMatchOrderedList` + `ExpectColumnValuesToBeOfType` |

### 基盤実装(2026-08-04)

- 骨格を plan.md §2 どおり作成: `.env.example` / `docker-compose.yml`(profiles: base / tools)/
  `docker/tools/`(python:3.11-slim + venv 分離)/ `Makefile` / `scenarios/` / `data/seed/` / `pipeline/`。
- tools イメージはフェーズ1 時点では quality venv のみ(`soda-postgres==4.19.0`、
  `great_expectations[postgresql]==1.19.1`、`psycopg2-binary==2.9.10`)。lineage / catalog venv は
  フェーズ2・3 で追加する。ビルドは初回成功(exit 0)。
- tools は常駐させず `docker compose --profile tools run --rm` で都度実行する構成にした
  (plan.md「プロファイル外・都度実行」の実現手段。profile 名 `tools` を付けたのは
  `--profile base up` で誤って起動しないようにするため)。
- `.gitignore` 調整: 既存の `*.log` が検収用生ログを除外してしまうため
  `!verification/**/*.log` を追加。汚染データ `data/seed/csv-injected/` と
  `quality/gx/output/` は git 管理外とした(クリーン seed CSV はコミットする)。
- 合成データ生成(`data/seed/generate.py`、シード 42): customers 1,000 / products 200 /
  orders 5,000 / order_items 12,561 行。`--inject`(email_null=30行 / dup_order_id=20行 /
  bad_quantity=15行 / bad_unit_price=10行 / all)を実装。
- パイプライン実行結果(クリーンデータ): staging.stg_orders 11,927 行 /
  mart.daily_sales 365 行 / mart.customer_summary(ビュー)1,000 行。
- raw 層のテーブルには PRIMARY KEY / NOT NULL を意図的に付けない(違反データを
  「投入できてしまう」ことがデモの前提のため)。

### 遭遇した問題と解決(フェーズ1)

1. **再シード時に `DependentObjectsStillExist`**(試行1で解決):
   mart.customer_summary(ビュー)が raw.customers に依存しており、2 回目以降の
   seed ステップで `DROP TABLE raw.customers` が失敗。
   → `01_create_raw.sql` の冒頭で `DROP VIEW IF EXISTS mart.customer_summary;` を実行して解決。
   CASCADE は「何が消えるか見えない」ため不採用。
2. **GX の型チェックが `VARCHAR` で不一致**(試行1で解決):
   `ExpectColumnValuesToBeOfType(column="status", type_="VARCHAR")` に対し観測値は
   長さ付きの `VARCHAR(20)`。→ `type_="VARCHAR(20)"` に修正(実測値準拠)。
   ガイドのトラブルシューティングにも記載。
3. **GX の進捗バー(tqdm)が生ログを汚す**:
   `context.variables.progress_bars = ProgressBarsConfig(globally=False)` で無効化。

### 実測で確認した仕様(公式 docs に明記がなかったもの)

- **Soda v4 データソース設定の形式**: CLI リファレンスの例にある `data_source:` ラッパーは
  不要で、トップレベル `type:/name:/connection:` 形式が正
  (`soda data-source test` で接続成功を確認)。`${env.VAR}` 補間も動作確認済み。
- **Soda の exit code(実測)**: チェック全 pass = 0、チェック fail あり = 1。
- **GX**: `checkpoint.run()` は exit code を持たないため、`result.success` を見て
  スクリプト側で 0/1 を返す実装にした。
- **重複の数え方が両製品で異なる**: 同じ「order_id 重複 20 組」に対し
  Soda `duplicate_count: 20`(重複している値の数)、GX `unexpected_count: 40`
  (重複に関与する全行数)。比較軸2 の好例としてガイド §5 に記載。
- **GX Data Docs は ephemeral context でも生成可能**:
  `context.add_data_docs_site(...)` + `UpdateDataDocsAction` で
  `quality/gx/output/data_docs/` に HTML 出力(証跡は verification/phase1/gx_data_docs/ に保存)。

### フェーズ1 検証結果(2026-08-04)

| コマンド | 期待 | 実測 |
|---|---|---|
| `make demo-quality-soda` | exit 0 | **0**(3 contract / 5 チェック全 PASSED) |
| `make demo-quality-soda-ng` | 非0 | **非0**(4 違反すべて FAILED 検知。soda 単体 exit 1) |
| `make demo-quality-gx` | exit 0 | **0**(3 validation / 9 expectation 全成功) |
| `make demo-quality-gx-ng` | 非0 | **非0**(4 違反すべて success:false。スクリプト exit 1) |
| `make clean-db` → `make demo-quality-soda` | まっさら状態から exit 0 | **0**(再現確認済み) |

- 生ログ: `verification/phase1/demo-quality-{soda,gx}[-ng].log`(計4本)+
  `verification/phase1/gx_data_docs/`(GX HTML レポート)。
- 実測リソース: postgres-demo 約 35 MiB(アイドル時)。tools は実行時のみ。
- 既知の制約: 異常系の `make` 終了コードは make のラップにより 2 になる
  (シナリオ自体は 1。DoD の「非0」要件は満たす)。

### 検収指摘への対応(2026-08-04)

- **指摘**: ガイド §4.4(GX 異常系)の出力例が端末の実行結果と一致しない。
- **原因**: GX の結果 JSON をガイド掲載時に整形し直していた(配列を 1 行に圧縮、
  インデントを浅く変更、一部キーを省略)。端末出力は配列要素 1 行ずつ・インデント付きの
  ため、見比べると別物に見える。「出力例は実際に実行して得た内容のみに基づく」の趣旨に反していた。
- **対処**: §4.3 / §4.4 の JSON 例を生ログ(verification/phase1/)からの**逐語転記**に差し替え。
  併せてガイド内の全出力例(Soda 2 箇所・GX 2 箇所)が生ログと逐語一致することを
  スクリプトで機械検証した(4/4 VERBATIM)。
- **再発防止**: 今後のフェーズでもガイドの出力例は「ログからのコピー+省略箇所は明記」のみとし、
  整形し直しはしない。掲載前に同じ機械検証を行う。

### 検収指摘への対応 その2(2026-08-04)

- **指摘**: 異常系デモの「非 0 で終了」という表現が分かりにくい。想定出力を記載するか、
  「エラーを検知し、正常終了」のように一目で正解が分かるようにしてほしい。
- **対処**(docs/guides/quality.md):
  1. §4.0「実行結果の見方」を新設。「検知シナリオは `Error` 表示が正解」であることを冒頭で明示し、
     4 コマンドすべての「期待する最終出力」を一覧表にした。exit 0 / exit 1 の意味も補足。
  2. 各シナリオ(§4.1〜4.4)に**「成功の目印」**として、画面最後に出る行の実測値を
     そのまま掲載(異常系は make の `Error 1` 行まで含む)。
  3. 本文の「非 0 で終了」表現を「違反を検知してエラー終了すれば成功」に全面的に置き換え。
     §7 トラブルシューティングの該当項も同様に修正。
- **証跡の追加**: make コマンドの端末出力全体(make のメッセージ含む)を
  `verification/phase1/terminal-demo-quality-*.log` 4 本として新規保存
  (従来のシナリオログには make 自身の `Error 1` 行が含まれないため)。
  4 デモを再実行して取得(exit 0 / 2 / 0 / 2 を再確認)。
- **機械検証**: ガイド内の出力例 8 ブロックすべてが生ログまたは端末キャプチャと
  逐語一致することを確認(8/8 VERBATIM)。
- **留意点**: 「成功の目印」の make エラー行に含まれる `Makefile:38` 等の行番号は
  Makefile の変更で変わりうる旨をガイドに注記した。
