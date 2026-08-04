# docs/plan.md — データガバナンス OSS デモ環境 設計書(フェーズ0 成果物)

- 作成日: 2026-08-04
- 前提: CLAUDE.md の絶対制約(ローカル Docker 完結・最新安定版ピン留め・公式ドキュメント準拠・
  合成データのみ・日本語ドキュメント)に従う。
- 発注者指定の比較軸(本設計全体を貫く軸):
  1. Soda Core の手軽さ vs GX の Python ネイティブな表現力
  2. 同一の品質違反に対する Soda Core と GX の設定・結果の比較
  3. Marquez と OpenMetadata のリネージュの思想の違いと使い分け
  4. OpenMetadata によるカタログ化の様相
  5. ODCS によるデータコントラクトの可視化

---

## 1. 採用バージョン一覧

調査日はすべて 2026-08-04。詳細な調査記録(確認したリリース情報・注意点)は
`docs/build-log.md` の同日エントリを参照。

| 製品 | 採用バージョン | ライセンス | 参照URL(主) | 選定理由 |
|---|---|---|---|---|
| Soda Core(`soda-postgres`) | **4.19.0**(2026-07-28) | Elastic License 2.0(CLAUDE.md で許容済み) | github.com/sodadata/soda-core / pypi.org/project/soda-postgres / docs.soda.io | v4 系が現行開発ライン(v3 は公式に legacy)。最新安定 4.19.0。Soda Cloud 接続不要でローカル完結可を README で確認。**公開 PyPI** の `soda-postgres` を使用(docs の一部が指す `pypi.cloud.soda.io` は有償チャネルのため使わない) |
| Great Expectations | **1.19.1**(2026-07-24) | Apache-2.0 | pypi.org/project/great-expectations / docs.greatexpectations.io/docs/core | 1.x 刷新後 API の最新安定版。`great_expectations[postgresql]` extras で Postgres 対応。GX Cloud 不要 |
| OpenLineage(`openlineage-python`) | **1.52.0**(2026-07-23) | Apache-2.0 | github.com/OpenLineage/OpenLineage / openlineage.io/docs/client/python | 最新安定(monorepo 一括バージョン)。素の Python からの emit(event_v2 + HTTP transport)とカラムリネージュ facet を公式サポート |
| Marquez / Marquez Web | **0.51.1**(イメージ公開 2025-03-27) | Apache-2.0 | github.com/MarquezProject/marquez / hub.docker.com/r/marquezproject/marquez | Docker Hub の最新公開タグ(プロジェクトの `latest` も 0.51.1)。ただし GitHub Release/CHANGELOG は 0.50.0 止まり。**問題発生時は正式リリース済みの 0.50.0 へフォールバック**(判断は build-log.md 参照)。注意: **amd64 のみ提供**(→ §6 リスク) |
| OpenMetadata | **1.13.3**(2026-07-31) | サーバ: Apache-2.0 | github.com/open-metadata/OpenMetadata/releases / docs.open-metadata.org | 最新安定(2.0.0-rc1 は prerelease「DO NOT use in PROD」のため不採用)。全イメージ amd64+arm64 マルチアーチ |
| openmetadata-ingestion | **1.13.3.0**(2026-07-31) | Collate Community License 1.0(source-available・無料利用可。CLAUDE.md の「ソース公開・無料利用可能」の範囲内と判断) | pypi.org/project/openmetadata-ingestion | サーバとバージョン一致が公式推奨。Python 3.9–3.11 対応 |
| datacontract-cli | **1.0.17**(2026-08-01) | MIT | github.com/datacontract/datacontract-cli / docs.datacontract.com | 最新安定。v0.11.1 以降 **ODCS ネイティブ**(比較軸5と一致)。公式 Docker イメージ `datacontract/cli:1.0.17` あり |
| ODCS(仕様) | **v3.1.0**(2025-12-08) | Apache-2.0(Bitol / LF AI & Data) | bitol-io.github.io/open-data-contract-standard/latest/ | 最新安定仕様。datacontract-cli 1.x の既定 apiVersion |

インフラ(4製品の「最新安定」要件の対象外。役割ごとに互換性優先で固定):

| 用途 | イメージ | 理由 |
|---|---|---|
| デモ用データ DB | `postgres:16` | 全ツールのコネクタ実績が厚い安定版 |
| Marquez メタ DB | `postgres:14` | Marquez 公式 compose / README の要件に従う |
| OpenMetadata 用 DB / 検索 | `docker.getcollate.io/openmetadata/postgresql:1.13.3` / `docker.elastic.co/elasticsearch/elasticsearch:9.3.0` | 1.13.3 公式リリースアセットの compose と同一構成 |
| Python 実行基盤 | `python:3.11-slim` | 全ツールの対応範囲の交差(Soda >=3.10 / GX <3.14 / OM ingestion <=3.11 / datacontract >=3.10)。datacontract 公式推奨も 3.11 |

**バージョン運用**: すべて上記に**ピン留め**(pip は `==`、イメージはタグ固定)。
変更時は build-log.md に理由を記録する。

---

## 2. リポジトリ構成案

```
.
├── CLAUDE.md / PROGRESS.md / README.md(入口: 全体像と各ガイドへの導線)
├── Makefile                  # すべてのデモの単一コマンド入口(make demo-XX)
├── .env.example              # デモ用資格情報(実シークレットなし・デモ用と明記)
├── docker-compose.yml        # profiles: base / lineage / catalog(§3.4)
├── docker/
│   └── tools/                # ツール実行用イメージ(python:3.11-slim ベース)
│       ├── Dockerfile        # 領域ごとに venv を分離(依存衝突回避)
│       └── requirements-{quality,lineage,catalog}.txt   # バージョンピン留め
├── data/
│   └── seed/                 # 合成データ生成スクリプト(乱数シード固定)
├── pipeline/                 # 共通パイプライン(SQL 変換 + OpenLineage 発行)
├── quality/
│   ├── soda/                 # データソース設定 + Soda contract YAML(正常/異常見比べ用)
│   └── gx/                   # GX 1.x Python スクリプト(同一チェックの GX 版)
├── lineage/                  # Marquez 用設定・openlineage.yml
├── catalog/                  # OpenMetadata ingestion workflow YAML・lineage 登録スクリプト
├── contracts/                # ODCS v3.1.0 コントラクト(v1 / v2-breaking)+ 判定スクリプト
├── .github/workflows/        # contract CI(YAML は静的検証 + ローカル等価実行で検収)
├── scenarios/                # 各 make demo-XX の実体スクリプト(ログ整形・exit code 制御)
├── docs/
│   ├── plan.md / build-log.md
│   └── guides/               # 利用者向けガイド(領域ごと + 全体セットアップ)
└── verification/phase{0..5}/ # 生の実行ログ・証跡
```

**この構成にした理由**:

- **領域ごとのディレクトリ分割**(quality/lineage/catalog/contracts): 対象読者(初学者)が
  「学びたい製品のディレクトリだけ読めば完結する」ことを優先。比較軸1・2のために
  `quality/soda` と `quality/gx` は**同じチェック内容を意図的に並置**する。
- **Makefile を単一入口に**: DoD の「単一コマンド実行・正常系 exit 0 / 異常系 非0」を
  Make ターゲットで統一的に保証する。scenarios/ に実体を置き、Makefile は薄く保つ。
- **tools イメージに領域別 venv**: GX・Soda・openmetadata-ingestion は依存が重く衝突しやすい
  (かつ OM ingestion は Python <=3.11 制約)。1 イメージ内で venv を分離すれば、
  ビルドは 1 回で依存は隔離できる。ホスト環境も汚さない。
  datacontract-cli のみ公式イメージ `datacontract/cli:1.0.17` をそのまま使う(自前ビルド不要)。
- **data/seed はスクリプトで再生成可能**(シード固定)とし、生成物 CSV もコミットする:
  検収時に「生成器のバグで別データになる」事故を避け、diff で変化を追えるようにするため。

---

## 3. 全体アーキテクチャ

### 3.1 共通サンプルデータセット(合成 EC データ)

小さな EC(通販)ドメインを採用。理由: 初学者に説明不要で、品質違反・リネージュ・契約の
すべての題材(欠損・重複・範囲・集計・スキーマ変更)が自然に作れるため。

| スキーマ.テーブル | 行数目安 | 主な列 | 役割 |
|---|---|---|---|
| raw.customers | 1,000 | customer_id, name, email, prefecture, created_at | 品質: email 欠損/形式、重複 |
| raw.products | 200 | product_id, name, category, price | 品質: price 範囲 |
| raw.orders | 5,000 | order_id, customer_id, order_date, status | 品質: 重複 order_id、参照整合 |
| raw.order_items | ~12,000 | order_item_id, order_id, product_id, quantity, unit_price | 品質: quantity/unit_price 範囲 |
| staging.stg_orders | ~12,000 | (orders+order_items+products 結合・クレンジング済み) | リネージュの中間ノード |
| mart.daily_sales | ~365 | sales_date, order_count, total_amount | 契約(ODCS)の対象。**テーブル**(CTAS) |
| mart.customer_summary | 1,000 | customer_id, total_orders, total_amount, last_order_date | **ビュー**として定義(OpenMetadata の SQL 解析リネージュを見せる) |

- 生成は Python(乱数シード固定)。実在の個人情報は含めない(名前・メールも機械生成)。
- 生成スクリプトに **`--inject <violation>` オプション**を持たせ、異常系デモ用の汚染データ
  (email NULL、order_id 重複、quantity<=0、負の金額)を意図的に混入できるようにする。
  正常/異常をコマンドで切り替えられることが、全デモの exit 0 / 非0 の作り分けの基盤になる。

### 3.2 パイプライン構成

```
[data/seed] --COPY--> raw.* --SQL--> staging.stg_orders --SQL--> mart.daily_sales
                                                        \--VIEW--> mart.customer_summary
   (step: seed)        (step: build_staging)              (step: build_mart)
        │                    │                                  │
        └────────────────────┴── OpenLineage RunEvent(START/COMPLETE/FAIL)──> Marquez(HTTP)
```

- 実体は `pipeline/run_pipeline.py` 1 本(+ステップ別実行可)。各ステップは
  psycopg2 で SQL を実行する素の Python。オーケストレータは導入しない。
- 品質チェック(Soda/GX)はパイプラインの外から同じ DB に対して実行する
  (初学者に「チェックは独立したツールである」ことを見せるため。統合はしない)。

### 3.3 OpenLineage イベント発行手段の選定

**採用: `openlineage-python` 1.52.0 クライアントを Python スクリプトから直接呼ぶ(HTTP transport → Marquez)**

| 候補 | 判断 | 理由 |
|---|---|---|
| Airflow 等のオーケストレータ統合 | 不採用 | CLAUDE.md で明示的に禁止(フル機能オーケストレータ導入不可) |
| dbt + dbt-ol ラッパー | 不採用 | イベントは自動化できるが dbt という追加ツールの学習が必要になり、「イベントがどう作られるか」がブラックボックス化する。デモの目的(思想の体感)に反する |
| **Python クライアント直接利用** | **採用** | 公式ドキュメントが正式にサポートする最小構成。RunEvent(START/COMPLETE/FAIL)や facet を**生のまま見せられる**ため、OpenLineage の仕様理解に最適。依存も openlineage-python 1 つ |
| console/file transport のみ | 不採用(併用はする) | UI で確認できない。ただし異常時の切り分け用に console transport の使い方はガイドに記載 |

- カラムレベルリネージュ: `facet_v2.column_lineage_dataset`(ColumnLineageDatasetFacet)を
  build_mart ステップに手動付与し、Marquez UI での見え方を確認する(公式 facet 1-2-0)。

### 3.4 compose profile の分割方針

「全製品の同時起動を要求しない」制約に従い、profile で領域ごとに起動・停止する。

| profile | サービス | 概算メモリ(実測をフェーズごとに追記) |
|---|---|---|
| `base`(全デモの前提) | postgres-demo(postgres:16) | ~0.3 GiB |
| (プロファイル外・都度実行) | tools(品質/リネージュ発行/カタログ取込の CLI 実行)、datacontract/cli | 実行時のみ ~0.5 GiB |
| `lineage` | marquez-db(postgres:14)/ marquez-api / marquez-web | ~1.5–2 GiB(公式未記載のため実測して記録) |
| `catalog` | om-postgresql / om-elasticsearch(heap 1GiB)/ om-migrate(one-shot)/ om-server | 公式要件 **6 GiB / 4 vCPU**。Airflow ingestion コンテナは**採用しない**(下記) |

- **OpenMetadata の Airflow ingestion コンテナは省略**し、取り込みは tools 内の
  `metadata ingest -c <yaml>`(external ingestion、公式サポート)で行う。
  理由: メモリを大幅節約でき、かつ「UI からのスケジュール実行」はデモ要件でないため。
  公式の server 単体 compose(docker-compose-openmetadata.yml)が存在することも確認済み。
- ホスト 15.36 GiB に対し、最重量の組み合わせ(base+catalog ≒ 6.5 GiB)でも余裕がある。
  lineage と catalog の同時起動もポート衝突なし(5000/3000 vs 8585/9200)だが、ガイドでは
  「領域ごとに起動→停止」を基本手順とする。

---

## 4. デモシナリオ一覧

各シナリオは `make demo-XX` の単一コマンドで実行(DoD: 正常系 exit 0、異常系は検知内容を出力して非0)。
「仮説」はフェーズ実装時に実際の出力で検証し、ガイドには**実測結果のみ**を書く。

### 領域A: データ品質(比較軸1・2)

**設計原則: Soda と GX に完全に同一の 4 種類の品質チェックを実装し、設定量と出力を並べて比較する。**

対象チェック(すべて raw 層):
(a) customers.email の欠損率 0%、(b) orders.order_id の一意性、
(c) order_items.quantity > 0 かつ unit_price の範囲、(d) orders のスキーマ(列の存在と型)

| シナリオ | make ターゲット案 | 内容 |
|---|---|---|
| A-1 Soda 正常系 | `demo-quality-soda` | クリーンデータに Soda contract YAML(4チェック)で `soda contract verify` → 全 pass、exit 0 |
| A-2 Soda 異常系 | `demo-quality-soda-ng` | `--inject` で汚染データ投入後に同じ contract を実行 → fail 検知を出力し exit 非0 |
| A-3 GX 正常系 | `demo-quality-gx` | 同一 4 チェックを GX 1.x(Checkpoint)で実行 → 全 pass、exit 0 |
| A-4 GX 異常系 | `demo-quality-gx-ng` | 同一汚染データで GX 実行 → 失敗詳細(unexpected values 等)を出力し exit 非0 |

- **仮説(長所・短所)**:
  - Soda: contract YAML 十数行で 4 チェックが書け、CLI 出力も簡潔(比較軸1の「手軽さ」)。
    一方、チェックは用意された check type の範囲に制約され、v4 で SodaCL から記法が刷新されたため
    Web 上の古い情報が使えない(短所として明記)。ライセンスも ELv2 で OSI OSS ではない。
  - GX: 同じ 4 チェックに Python コード(context→suite→validation definition→checkpoint)が
    必要で概念数が多く初期コストが高い。一方、失敗行のサンプル・統計など**結果の情報量**と、
    任意ロジック(カスタム Expectation)・Data Docs(HTML レポート)の表現力で勝る。
- **UI/証跡確認ポイント**: Soda は CLI 出力(+結果 JSON)、GX は CLI 出力 + Data Docs の HTML を
  `verification/` に保存。**同一違反に対する両者の出力を横並びにした比較表**をガイドに載せる(比較軸2)。

### 領域B: リネージュ(比較軸3の Marquez 側)

| シナリオ | make ターゲット案 | 内容 |
|---|---|---|
| B-1 パイプライン実行→リネージュ収集 | `demo-lineage` | `lineage` profile 起動 → パイプライン実行(OL イベント発行)→ Marquez UI(:3000)にジョブ・データセット・リネージュグラフが出る。exit 0 |
| B-2 失敗実行の追跡 | `demo-lineage-fail` | build_mart を意図的に失敗させ FAIL イベントを発行 → Marquez 上で該当 Run が FAILED になり、どの段が止まったか追える。exit 非0 |

- **仮説**: Marquez は「**実行(Run)の事実**」を時系列で記録する運用視点のリネージュ。
  ジョブの成功/失敗・実行時刻・バージョンが残るのが強み。逆にイベントを発行しない処理は
  一切見えない(発行側の実装が必須)のが短所。amd64 のみの提供も短所として記録。
- **UI 確認ポイント**: リネージュグラフ(raw→staging→mart)、Run の状態遷移
  (RUNNING→COMPLETED/FAILED)、build_mart のカラムレベルリネージュ facet の表示。
  スクリーンショット + API レスポンス(`/api/v1/namespaces/.../lineage`)を証跡保存。

### 領域C: カタログ(比較軸3の OpenMetadata 側・比較軸4)

| シナリオ | make ターゲット案 | 内容 |
|---|---|---|
| C-1 メタデータ取込 | `demo-catalog-ingest` | `catalog` profile 起動 → `metadata ingest`(Postgres コネクタ)で raw/staging/mart を取込 → UI(:8585)にテーブル・スキーマが並ぶ。exit 0 |
| C-2 プロファイリング | `demo-catalog-profile` | profiler workflow で行数・欠損率・分布を取得 → UI の Profiler タブで確認。exit 0 |
| C-3 リネージュ(SQL 解析) | `demo-catalog-lineage` | lineage workflow がビュー定義(mart.customer_summary)を解析し自動でリネージュ生成。スクリプト由来の mart.daily_sales は Lineage API(`/api/v1/lineage`)で登録し、手段の違いを見せる。exit 0 |
| C-4 スキーマ変更の検知(異常系) | `demo-catalog-drift` | 列を削除して再取込 → OM のエンティティ**バージョン履歴**に差分が記録される。検知結果を出力し exit 非0 |

- **仮説(比較軸3: Marquez との思想の違い)**:
  - Marquez = **イベント駆動(実行時)**。「昨夜のジョブはどのデータを読んで失敗したか」に答える。
  - OpenMetadata = **メタデータ駆動(静的・SQL解析)**。実行がなくても定義(ビュー・クエリログ)から
    リネージュを導出し、カタログ・用語集・所有者・タグと統合する。「このテーブルはどこ由来で
    誰の持ち物か」に答える。
  - 使い分け仮説: パイプライン運用監視は Marquez(OpenLineage)、全社的なデータ発見・
    ガバナンスは OpenMetadata。なお OM の OpenLineage コネクタは Kafka 経由のみ(BETA)のため
    本デモでは接続せず、**思想の違いをそのまま見せる**(この判断は build-log.md 参照)。
- **UI 確認ポイント(比較軸4)**: テーブル検索、スキーマ・サンプルデータ・プロファイル表示、
  オーナー/タグ/説明の付与、用語集(最小 1 用語)、リネージュタブ(カラムレベル含む)、
  バージョン履歴。各画面をスクリーンショット保存。

### 領域D: データコントラクト(比較軸5)

| シナリオ | make ターゲット案 | 内容 |
|---|---|---|
| D-1 契約の可視化 | `demo-contract-export` | mart.daily_sales の ODCS v3.1.0 契約を `datacontract export html / mermaid` で可視化し `verification/` に保存。exit 0 |
| D-2 契約テスト正常系 | `demo-contract-test` | `datacontract test`(ibis エンジン)で実 DB に対しスキーマ+品質(rowCount 等の標準メトリクス)を検証 → pass、exit 0 |
| D-3 データ違反(異常系) | `demo-contract-violation` | 汚染データ投入後に同じ契約でテスト → 違反を出力し exit 非0 |
| D-4 破壊的変更(異常系) | `demo-contract-breaking` | 契約 v1→v2(列削除・型変更)を `datacontract changelog` で差分抽出し、**自作判定スクリプトで removed/updated を breaking と判定して exit 非0**(`breaking` コマンドは v0.11.1 で削除済みのため。build-log.md 参照) |
| D-5 CI 統合 | `demo-contract-ci` | `.github/workflows/contract.yml`(`datacontract ci` を実行する公式推奨パターン)を作成。本環境では (a) YAML の静的検証、(b) ワークフローと同一コマンド `datacontract ci` のローカル実行、(c) 可能なら `act` での実行、をもって検証とする |

- **仮説**: ODCS は品質チェック(Soda/GX)と違い「**生産者と消費者の合意**」を 1 ファイルで表す。
  スキーマ+品質+SLA+チーム情報が 1 つの YAML に載り、html/mermaid export で非エンジニアにも
  見せられる(比較軸5)。短所仮説: ツールチェーンが若く、コマンド体系の変化が激しい
  (breaking 削除、Soda エンジン廃止など)。`export sodacl` / `export great-expectations` で
  領域Aとの概念的つながり(契約→チェック生成)も 1 シナリオ内で紹介する。
- **確認ポイント**: export された HTML/mermaid、test の JSON 出力、changelog の差分出力、
  CI 実行ログ(ローカル equivalents)をすべて証跡保存。

---

## 5. フェーズ1〜5の実装順序と検証計画

| フェーズ | スコープ | 主な成果物 | 検証計画(DoD 適用) |
|---|---|---|---|
| 1 | **基盤 + データ品質**: リポジトリ骨格、.env.example、compose(base)、合成データ生成(+ --inject)、パイプライン(OL 発行なし版)、Soda/GX の 4 チェック、ガイド | Makefile、data/seed、pipeline、quality/、docs/guides/quality.md | `make demo-quality-{soda,gx}` exit 0 / `-ng` 非0 の生ログを verification/phase1/ に保存。Soda↔GX 出力比較表の元データ取得。pip 依存はすべて `==` ピン |
| 2 | **リネージュ**: lineage profile(Marquez 0.51.1)、パイプラインへの OL イベント発行実装(カラム facet 含む)、ガイド | lineage/、pipeline 拡張、docs/guides/lineage.md | `make demo-lineage` 実行→ UI スクリーンショット + lineage API レスポンス保存。`demo-lineage-fail` 非0。Marquez 実測メモリを build-log に記録。amd64 のみの制約をガイドに明記 |
| 3 | **カタログ**: catalog profile(OM 1.13.3、Airflow なし構成)、CLI ingestion(metadata/profiler/lineage workflow)、Lineage API 登録、ガイド | catalog/、docs/guides/catalog.md | `make demo-catalog-*` の生ログ + UI スクリーンショット保存。起動時間・実測メモリ記録。C-4 の非0 動作確認 |
| 4 | **コントラクト**: ODCS v1/v2 契約、test/export/changelog+判定スクリプト、GitHub Actions ワークフロー、ガイド | contracts/、.github/workflows/、docs/guides/contract.md | D-1〜D-5 の生ログ保存。CI は静的検証+ローカル等価実行(+可能なら act)で証跡化し、その旨をガイドに明記 |
| 5 | **統合**: README(全体導線)、全ガイドの通し読み校正、**まっさら状態からの通し再現テスト**(イメージ削除→ガイド手順のみで全デモ再実行) | README.md、docs/guides/ 全体 | 通し実行の生ログを verification/phase5/ に保存。ガイド記載外の操作が必要になった箇所はすべてガイドへ反映(検収の予行) |

- 品質を最初に置く理由: 依存が最少(base profile + tools のみ)で、データ生成・注入の
  仕組み(全領域の土台)をこの段階で固められるため。
- 各フェーズ完了時に PROGRESS.md 更新+完了報告→**発注者検収を待って**次フェーズへ。

---

## 6. リスクと事前に分かっている制約

| # | リスク/制約 | 影響 | 対応方針 |
|---|---|---|---|
| R1 | **GitHub Actions は本環境で実行不可** | フェーズ4 の CI 検証 | CLAUDE.md 記載のとおり (a) YAML 静的検証 (b) `datacontract ci` のローカル実行(ワークフローと同一コマンド)(c) 可能なら `act`、で検証済みとみなし、ガイドに明記 |
| R2 | **Marquez は amd64 イメージのみ**(0.50/0.51 とも) | Apple Silicon ではエミュレーション動作(性能低下・稀に不安定) | compose に `platform: linux/amd64` を明示。ガイドに既知の制約として記載。実機 arm64 検証は本環境(amd64)では不可であることも明記 |
| R3 | Marquez 0.51.1 は GitHub Release/CHANGELOG なし | 変更内容が追えない | タグ固定で採用し、問題があれば 0.50.0 へフォールバック(判断記録済み) |
| R4 | **OpenMetadata は 6 GiB / 4 vCPU 要求**・起動が遅い | 低スペックマシンで catalog デモ不可の恐れ | 公式要件をガイド冒頭に明記。Airflow ingestion コンテナ省略で軽量化。起動待ち(healthcheck)を Make に組込み |
| R5 | openmetadata-ingestion は **Collate Community License**(1.6 以降、OSI 外) | ライセンス条件 | 無料利用可・ソース公開であり CLAUDE.md の許容範囲と判断(Soda ELv2 と同等の扱い)。ガイドに明記 |
| R6 | openmetadata-ingestion は **Python <=3.11** | ツール環境の分離が必要 | tools イメージを Python 3.11 で統一し、領域別 venv で依存衝突を回避 |
| R7 | Soda v4 は記法刷新直後で Web 上の情報(SodaCL)が古い。docs の一部は有償チャネル `pypi.cloud.soda.io` を案内 | 実装時の混乱 | 公式 contract-language-reference のみを参照。公開 PyPI `soda-postgres==4.19.0` を使用し、Cloud 設定なしで動くことをフェーズ1 で最初に確認 |
| R8 | **datacontract-cli に breaking 判定コマンドがない**(v0.11.1 で削除、changelog は常に exit 0) | D-4 シナリオ | changelog の JSON 出力を自作スクリプトで判定して非0 終了を実装(設計に織込み済み) |
| R9 | OpenMetadata の OpenLineage コネクタは Kafka/Kinesis 経由のみ(BETA) | Marquez と同一イベントの共有は不可 | 接続せず、思想の違い(イベント駆動 vs SQL解析)としてデモに転化。Kafka 導入はスコープ外と明記 |
| R10 | ポート衝突(macOS の 5000 予約、既存コンテナ、8585/9200 等) | 起動失敗 | .env でポートを変更可能にし、ガイドに macOS 向け注記(Marquez README 記載の既知問題)を記載 |
| R11 | 本環境は WSL2/amd64・メモリ 15.36 GiB | arm64 実機検証不可 | R2 と併せて既知の制約として明記。compose はマルチアーチ対応の書き方を維持 |
| R12 | OM 公式 docs の quickstart が 1.12.6 の URL のまま等、**各製品で docs がリリースに未追随** | 誤った手順の混入 | リリースアセット・PyPI メタデータ等の一次情報を優先(調査記録は build-log.md に保存済み) |

---

## 付記: 品質2製品とコントラクトの概念整理(実装時の指針)

Soda v4 も「コントラクト」を名乗るため、初学者が ODCS と混同するリスクがある。
デモでは次の整理で一貫させる(ガイドにも記載する):

- **Soda contract / GX suite** = *技術的な品質チェックの定義*(データエンジニア内部の道具)
- **ODCS** = *生産者と消費者の間の合意*(スキーマ+品質+SLA+責任者を含む上位概念)。
  `datacontract export sodacl / great-expectations` により「合意から技術チェックを導出できる」
  関係として見せる(D-1 内で紹介)。二重管理はせず、正とするのは用途ごとに明確化する。
