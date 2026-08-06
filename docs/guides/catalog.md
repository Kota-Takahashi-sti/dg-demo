# データカタログガイド — OpenMetadata で「データの意味と持ち主」を管理する

このガイドでは、OpenMetadata 1.13.3 を使って共通サンプルデータ(EC ドメイン)の
**データカタログ**を構築します。テーブルの検索・スキーマ閲覧に始まり、
プロファイリング(統計)、リネージュ、スキーマ変更の履歴管理までを、
それぞれ単一の `make` コマンドで体験します。

フェーズ2 の Marquez と同じデータ・同じテーブルを扱うため、
**「イベント駆動のリネージュ(Marquez)」と「メタデータ駆動のリネージュ(OpenMetadata)」の
思想の違い**(§5)が具体的に比較できます。

## 1. 前提条件

- Docker Desktop または Docker Engine + Compose v2(検証環境: Docker 28.1.1 / Compose v2.35.1)
- **メモリ: Docker に 6 GiB 以上を割り当てること(公式要件。4 vCPUs 以上も推奨)**。
  OpenMetadata はこのデモで扱う 4 製品の中で最も重く、実測でも一式で約 2.9 GiB を
  常時使用します(§3)。**他領域のプロファイル(lineage 等)は止めた状態で
  起動してください**(`make down-lineage` / `make down`)。
- 対応アーキテクチャ: amd64 / arm64(Apple Silicon)。OpenMetadata 1.13.3 の
  server / postgresql / elasticsearch イメージはすべてマルチアーチ提供です
  (Marquez と異なり arm64 ネイティブで動作します)。ただし本プロジェクトの
  実機検証は amd64(WSL2)のみです。
- ライセンス注記: OpenMetadata サーバは Apache-2.0、取り込みライブラリ
  openmetadata-ingestion は **Collate Community License 1.0**(ソース公開・無料利用可、
  OSI 認定外)です。本デモは無料利用の範囲で使用します。
- 共通セットアップ(`make setup`。[README.md](../../README.md) の「環境構築」参照)が
  済んでいること。過去に古い tools イメージ(`dgd-tools:phase1` / `phase2`)で
  セットアップした場合は `make build-tools` で tools イメージを更新してください。

## 2. この領域の登場人物(初学者向けの整理)

| 役者 | 実体(compose サービス) | 役割 |
|---|---|---|
| OpenMetadata サーバ | om-server(ポート 8585) | カタログ本体。UI と REST API を提供する |
| メタデータ DB | om-postgresql | カタログの格納先(PostgreSQL 15。デモ用データ DB とは別物) |
| 検索エンジン | om-elasticsearch | UI のテーブル検索を担う(Elasticsearch 9.3.0) |
| スキーマ移行 | om-migrate | 起動時に一度だけ動くワンショット。完了後に om-server が起動する |
| 取り込み CLI | tools コンテナ内の `metadata` コマンド | デモ用データ DB に接続してメタデータを**サーバへ送り込む**側 |

押さえておきたい構造が 2 つあります。

1. **カタログは「別の DB」である**: OpenMetadata はデモ用データ DB(postgres-demo)を
   直接参照して画面を描いているのではなく、**取り込み(ingestion)ワークフローが
   実行された時点のスナップショット**を自分の DB に保存して表示します。
   データ側が変わってもカタログは自動では追随しません(これが C-4 の伏線です)。
2. **取り込みは Airflow なしの external ingestion**: 公式構成には Airflow 入りの
   ingestion コンテナがありますが、本デモでは採用せず(メモリ節約と仕組みの可視化のため)、
   公式がサポートする **CLI 直接実行(`metadata ingest -c <YAML>`)** を使います。
   UI からのスケジュール実行はできませんが、ワークフロー YAML がそのまま見える分、
   初学者には仕組みが追いやすい構成です。

ワークフローは 4 種類を使い分けます(YAML は `catalog/` にあります):

| ワークフロー | YAML | 実行コマンド | 役割 |
|---|---|---|---|
| メタデータ取り込み | catalog/ingest.yaml | `metadata ingest` | テーブル・列・ビュー定義の取り込み(C-1) |
| プロファイラ | catalog/profiler.yaml | `metadata profile` | 行数・欠損率・分布などの統計(C-2a) |
| 自動分類 | catalog/classify.yaml | `metadata classify` | サンプルデータの格納(C-2b) |
| リネージュ | catalog/lineage.yaml | `metadata ingest` | ビュー定義 SQL の解析によるリネージュ導出(C-3a) |

認証について: ワークフローがサーバへ書き込む際は **ingestion-bot** という
ボットアカウントの JWT トークンを使います(公式手順では UI からコピーします)。
本デモではこの取得を自動化しており、`catalog/run_ingestion.py` が
admin ログイン → ingestion-bot の JWT 取得 → YAML の `${OM_JWT}` への注入までを行って
`metadata` CLI を起動します。トークンやパスワードがリポジトリのファイルに
残らないようにするための仕組みです(値はコンテナ内の一時ファイルのみに存在)。

## 3. 環境構築

```console
$ make setup             # 共通セットアップ(.env 作成 + tools イメージビルド)。済みならスキップ
$ make up-catalog
```

`make up-catalog` は om-postgresql / om-elasticsearch → om-migrate(ワンショット)→
om-server の順に healthcheck を待ちながら起動します。

- **初回起動の実測時間: まっさらな状態から約 3〜6 分**(検証環境での複数回の実測は
  186〜366 秒。`verification/phase3/resource-usage.log` 参照。イメージ pull が未了の
  場合はさらにかかります)。2 回目以降は移行が省略され短くなります。
- 起動完了後のメモリ実測(検証環境): om-server 約 1.0 GiB、om-elasticsearch 約 1.8 GiB、
  om-postgresql 約 0.15 GiB(合計約 2.9 GiB)。`verification/phase3/resource-usage.log` 参照。

### UI の URL とログイン

UI のポートは `.env` の `OM_SERVER_HOST_PORT`(既定 8585)で決まります。
確認するには:

```console
$ grep OM_SERVER_HOST_PORT .env
```

ブラウザで `http://localhost:<OM_SERVER_HOST_PORT>`(既定なら http://localhost:8585)を
開き、次の**デモ専用アカウント**でログインします:

- メールアドレス: `admin@open-metadata.org`
- パスワード: `admin`

これは OpenMetadata の Basic 認証既定の管理者アカウントです(ローカルデモ専用。
公開環境では必ず変更してください)。

停止は `make down-catalog`(カタログの内容は保持)、
カタログの中身ごと消すには `make clean-db` です。

## 4. デモの実行手順

### 4.0 実行結果の見方(最初にお読みください)

| コマンド | 何を見せるデモか | 期待する最終出力(成功の目印) |
|---|---|---|
| `make demo-catalog-ingest` | C-1 正常系: メタデータ取り込み+説明・タグ等の付与 | `カタログ取り込みデモ結果: 成功(exit 0)` |
| `make demo-catalog-profile` | C-2 正常系: プロファイリング+サンプルデータ格納 | `プロファイリングデモ結果: 成功(exit 0)` |
| `make demo-catalog-lineage` | C-3 正常系: リネージュ(自動導出+手動登録) | `リネージュデモ結果: 成功(exit 0)` |
| `make demo-catalog-drift` | C-4 異常系: スキーマ変更(列削除)の検知 | `スキーマ変更検知デモ結果: 破壊的変更を検知(非0 終了)` のあとに make の `Error 1` |

- 各デモは DB・カタログの起動、クリーンデータの再投入、取り込みまでを内包しており、
  **単体で実行しても動きます**が、初回は C-1 → C-2 → C-3 → C-4 の順に実行することを
  推奨します(§4.4 の出力例はこの順で実行した場合のものです)。
- 異常系デモ(C-4)は「破壊的変更をカタログが記録したこと」を確認して
  **エラー終了するのが正解**です(検知の証明としてコマンド全体は非 0 で終わります)。
- ログの途中に出る `ERROR ... pg_stat_statements does not exist` は想定内です(§8)。

### 4.1 C-1 正常系: メタデータ取り込み → カタログ閲覧

```console
$ make demo-catalog-ingest
```

このコマンドは (1) デモ用 DB を起動してクリーンデータを投入し、
(2) OpenMetadata 一式を起動し(未起動の場合)、(3) Postgres コネクタで
raw / staging / mart の 3 スキーマを取り込み、(4) 説明・オーナー・タグ・用語集を
API で付与します。

取り込みログの最後に出力される要約(実測。タイムスタンプ・所要時間は実行ごとに
変わります。12 レコード = サービス/DB/スキーマ 3 + テーブル 6 + ビュー 1 ほか):

```text
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Workflow Postgres Summary:
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Processed records: 12
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Updated records: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Warnings: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Filtered: 2
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Errors: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Success %: 100.0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Workflow OpenMetadata Summary:
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Processed records: 2
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Updated records: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Warnings: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Errors: 0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Success %: 100.0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Workflow Success %: 100.0
[2026-08-05 07:27:12] INFO     {metadata.Utils:logger:222} - Workflow finished in time: 4s 990.188ms
```

続いて、カタログを「データの意味が書かれた台帳」にする手入力メタデータの付与が
実行されます(通常は UI から人が行う操作です。再実行しても壊れないよう、
付与済みの場合はスキップされます):

```text
=== 手入力メタデータの付与(説明・オーナー・タグ・用語集。API 経由)===
説明を付与: mart.daily_sales
オーナーを付与: mart.daily_sales ← admin
タグを付与: raw.customers.email ← PersonalData.Personal
用語集を作成: demo_glossary(デモ用語集)
用語を作成: demo_glossary.uriage_kingaku(売上金額)
用語を割り当て: mart.daily_sales.total_amount ← 売上金額
```

(2 回目以降の実行では各行が「付与済み」「作成済み」表示になります)

成功の目印(画面の最後):

```text
カタログ取り込みデモ結果: 成功(exit 0)
```

#### UI 確認ポイント(スクリーンショット: `verification/phase3/ui/`)

1. **テーブル検索(Explore)**: 上部の Explore → Tables を開くと、取り込んだ
   テーブル・ビューが並びます(実測: `c1-explore-tables.png`)。検索窓で `daily` と
   打てば mart.daily_sales が引けます。**検索できるカタログ**が OpenMetadata の
   基本価値です。
2. **テーブル詳細(スキーマ)**: `demo_postgres.demo.mart.daily_sales` を開くと、
   列一覧・型に加えて、C-1 が付与した**説明文・オーナー(admin)**が表示されます
   (実測: `c1-table-daily-sales-schema.png`。ヘッダのバージョンが説明等の付与により
   0.2 になっている点も注目)。
3. **タグ**: `demo_postgres.demo.raw.customers` の email 列に **PersonalData.Personal**
   タグが付いています(実測: `c1-table-customers-schema.png`)。個人データの所在を
   カタログで管理する、ガバナンスの入口です。
4. **用語集**: 左メニューの Govern → Glossary に「デモ用語集」があり、
   用語「売上金額」の定義が確認できます(実測: `c1-glossary.png`)。この用語は
   mart.daily_sales.total_amount 列に割り当て済みです(API 証跡
   `api-table-daily-sales.json` の tags に `demo_glossary.uriage_kingaku` が入っています)。

### 4.2 C-2 正常系: プロファイリング + サンプルデータ

```console
$ make demo-catalog-profile
```

プロファイラ(C-2a)が行数・欠損率・最小最大などの統計を計算し、
自動分類ワークフロー(C-2b)が各テーブルのサンプル行を格納します。

プロファイラの要約出力(実測。タイムスタンプ・所要時間は実行ごとに変わります。
108 レコード = 9 オブジェクト × テーブル+各列の統計):

```text
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Workflow Profiler Summary:
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Processed records: 108
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Updated records: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Warnings: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Errors: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Success %: 100.0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Workflow OpenMetadata Summary:
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Processed records: 6
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Updated records: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Warnings: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Errors: 0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Success %: 100.0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Workflow Success %: 100.0
[2026-08-05 08:15:25] INFO     {metadata.Utils:logger:222} - Workflow finished in time: 35s 088.794ms
```

成功の目印(画面の最後):

```text
プロファイリングデモ結果: 成功(exit 0)
```

証跡として保存した API レスポンス(`verification/phase3/api-profile-customers.json`)には
行数・列統計が入っています(抜粋。`timestamp` はプロファイル取得時刻のため実行ごとに
変わります):

```json
  "profile": {
    "columnCount": 5.0,
    "profileSampleType": "PERCENTAGE",
    "rowCount": 1000.0,
    "sizeInByte": 90112.0,
    "timestamp": 1785917690731
  },
```

#### UI 確認ポイント

1. **プロファイル表示**: raw.customers を開き **Data Observability タブ**へ
   (Table Profile / Column Profile)。行数 1,000・各列の Null 率・ユニーク数・分布が
   表示されます(実測: `c2-profiler-customers.png`)。email 列の Null 率 0% は、
   フェーズ1 の品質チェック(Soda / GX)が検査していた内容と同じ事実を
   **カタログ側の統計として**見ていることになります。
2. **Sample Data タブ**: 同じテーブルの Sample Data タブに実データのサンプル行が
   表示されます(実測: `c2-sample-data-customers.png`)。データの中身を一目で
   確認できるのはカタログとして便利ですが、**実データがカタログ DB にコピーされる**
   ことを意味するため、実運用では格納可否をポリシーで決める項目です
   (本デモは合成データなので格納しています)。

### 4.3 C-3 正常系: リネージュ — 自動導出と手動登録(Marquez との比較の核心)

```console
$ make demo-catalog-lineage
```

このデモは**同じ mart 層の 2 つのオブジェクトを意図的に違う方法で**リネージュ化します:

- **mart.customer_summary(ビュー)**: DatabaseLineage ワークフローが、C-1 で取り込んだ
  **ビュー定義 SQL を解析**して上流(raw.customers、staging.stg_orders)を自動導出します。
  パイプラインを一度も実行していなくても、定義さえあればリネージュが得られます。
- **mart.daily_sales(CTAS で作ったテーブル)**: 作成時の SQL が DB に残らないため
  自動導出できません。そこで **Lineage API(PUT /api/v1/lineage)で手動登録**します
  (カラム単位の対応と元 SQL 付き)。

手動登録部分の出力(実測):

```text
=== C-3b: CTAS テーブルのリネージュを Lineage API で手動登録 ===
Lineage API で手動登録しました:
  demo_postgres.demo.staging.stg_orders → demo_postgres.demo.mart.daily_sales
  列: demo_postgres.demo.staging.stg_orders.order_date → demo_postgres.demo.mart.daily_sales.sales_date
  列: demo_postgres.demo.staging.stg_orders.order_id → demo_postgres.demo.mart.daily_sales.order_count(count)
  列: demo_postgres.demo.staging.stg_orders.amount → demo_postgres.demo.mart.daily_sales.total_amount(sum)
```

成功の目印(画面の最後):

```text
リネージュデモ結果: 成功(exit 0)
```

#### UI 確認ポイント

1. **自動導出されたリネージュ**: mart.customer_summary の Lineage タブに
   raw.customers と staging.stg_orders → customer_summary のグラフが表示されます
   (実測: `c3-lineage-customer-summary.png`)。エッジをクリックすると
   導出元のビュー定義 SQL が確認できます。
2. **手動登録したリネージュ**: mart.daily_sales の Lineage タブに
   staging.stg_orders → daily_sales のエッジが表示されます
   (実測: `c3-lineage-daily-sales.png`)。列アイコンを展開すると
   **カラムレベルの対応(order_date→sales_date、amount→total_amount 等)**も見えます。
3. **Marquez との見比べ**(任意): フェーズ2 の B-1(`make demo-lineage`)で見た
   同じ daily_sales のリネージュには「どの Run が・いつ・成功/失敗したか」が
   ありました。OpenMetadata のグラフには **Run という概念がありません**。
   この違いの意味は §5 で整理します。

### 4.4 C-4 異常系: スキーマ変更(列削除)の検知

データ提供側が「使っていないはずの列」を消してしまう——という破壊的変更を再現し、
再取り込みでカタログがそれをどう記録するかを確認します。

```console
$ make demo-catalog-drift
```

流れ: ベースライン取り込み → `ALTER TABLE raw.customers DROP COLUMN prefecture` →
再取り込み → バージョン履歴の検査、です。検査部分の出力(実測):

```text
テーブル: demo_postgres.demo.raw.customers
現在のバージョン: 1.2(直前: 0.2。列削除は破壊的変更としてメジャーバージョンが +1.0 される)
変更履歴に記録された削除列: ['prefecture']
→ 列削除がカタログに記録されています: prefecture
```

成功の目印(検知して**非 0 終了**するのが正解です):

```text
スキーマ変更検知デモ結果: 破壊的変更を検知(非0 終了)
```

> **バージョン番号の読み方**: OpenMetadata は後方互換の変更(説明・タグの追加等)で
> +0.1、**破壊的変更(列削除等)で +1.0** バージョンを上げます。出力例の
> 「0.2 → 1.2」の 0.2 は、C-1 が説明やタグを付与した分の +0.1 が積まれた状態です
> (C-1 を実行せずに C-4 を単体実行した場合は 0.1 → 1.1 になります)。
> また、列を元に戻して再取り込みすると、OpenMetadata は**過去と同一の状態を検出して
> バージョンを巻き戻す**ため(実測: 1.2 の状態に prefecture を戻すと 0.2 に戻る)、
> C-4 は何度実行しても同じ「0.2 → 1.2」を再現します。

#### UI 確認ポイント

1. raw.customers を開くと、ヘッダにバージョン番号(例: 1.2)が表示されます。
   クリックすると**バージョン履歴**が開き、最新版で prefecture 列が
   **赤の取り消し線付きで表示**されます(実測: `c4-versions-customers.png`)。
   「いつ・どの取り込みで・何が消えたか」を後から誰でも確認できるのが
   カタログのバージョン管理の価値です。
2. 確認後、データを元に戻すには:

```console
$ make seed                  # prefecture 列を含む状態で再作成
$ make demo-catalog-ingest   # カタログへ再反映
```

## 5. Marquez との比較(比較軸3)— リネージュの思想の違い

同じテーブル(mart.daily_sales)のリネージュを両方で見た結果を並べると、
2 製品が**別の問いに答えている**ことがわかります。

| 観点 | Marquez(OpenLineage) | OpenMetadata |
|---|---|---|
| リネージュの材料 | パイプラインが実行時に**発行したイベント**(RunEvent) | 取り込んだ**メタデータ**(ビュー定義 SQL の解析、または API/UI での登録) |
| パイプライン実行 | **必須**(イベントがなければ何も見えない) | **不要**(定義があれば導出できる。実行の有無は関知しない) |
| Run(実行履歴) | 中核概念。成功/失敗・所要時間・時系列が残る | 概念自体がない(取り込みの履歴はあるが Run の成否ではない) |
| 発行側の実装 | 必要(フェーズ2 では Python クライアントを実装した) | 不要(コネクタが接続して読む。ただし CTAS のような「定義が残らない」処理は手動登録が必要 — C-3b) |
| リネージュ以外の機能 | ほぼリネージュ専用 | カタログ・検索・プロファイル・タグ・用語集・所有者と**統合** |
| 得意な問い | 「昨夜のジョブはどのデータを読んで、どこで失敗したか」 | 「このテーブルはどこ由来で、何を意味し、誰の持ち物か」 |
| 苦手なこと | 実行されない限り何も記録されない。台帳的な情報(意味・持ち主)は持てない | 「その日その時の実行」は追えない。SQL が残らない処理は自動では見えない |

**使い分けの指針**(このデモで体感した範囲):

- パイプラインの**運用監視**(失敗の追跡・影響範囲の特定)には Marquez/OpenLineage。
  イベント駆動なので「実行の事実」が正確に残ります。
- 全社の**データ発見とガバナンス**(検索・意味付け・所有者・機密タグ・変更履歴)には
  OpenMetadata。実行がなくても静的に構築でき、リネージュはその一機能として
  カタログに溶け込みます。
- 両者は排他ではありません。OpenMetadata には OpenLineage コネクタもありますが、
  1.13 時点で **Kafka/Kinesis 経由のみ(BETA)** のため本デモでは接続していません
  (Kafka の導入はスコープ外。docs/plan.md R9)。本デモのように
  「運用視点は Marquez・台帳視点は OpenMetadata」と役割分担するのが現実的です。

## 6. OpenMetadata の長所・短所(このデモで確認できた範囲)

**長所**:

- カタログ・検索・プロファイル・リネージュ・タグ・用語集・バージョン履歴が
  **1 つの UI に統合**されている。C-1〜C-4 で見た機能はすべて追加ツールなしの標準機能。
- 取り込みは**コネクタ設定(YAML)を書くだけ**で、対象システム側の改修が不要。
  Marquez のような発行側実装(フェーズ2 の LineageEmitter)が要らない。
- スキーマ変更が**エンティティのバージョン履歴**として自動記録される(C-4)。
  変更の監査という、品質チェックともリネージュとも違う第 3 の検知手段になる。
- REST API が包括的で、UI でできることは概ね API でも自動化できる
  (C-1 の説明・タグ付与、C-3b の手動リネージュ登録がその実例)。

**短所**:

- **重い**。サーバ + 専用 DB + Elasticsearch で実測約 2.9 GiB(公式要件 6 GiB 割当)。
  Marquez 一式(実測約 0.35 GiB。リネージュガイド §1)の 8 倍前後で、
  初回起動も約 3 分かかる。
- 概念数が多い(サービス/データベース/スキーマ/テーブル、ワークフロー 4 種、
  ボット認証など)。動かすまでの理解コストは Marquez より高い。
- 取り込みは**スナップショット**であり、データ側の変更は再取り込みまで反映されない。
  鮮度はスケジューラ運用(本デモではスコープ外)に依存する。
- 定義が残らない処理(CTAS 等)のリネージュは自動では得られず、手動登録か
  クエリログ(pg_stat_statements 等の追加設定)が必要(C-3b・§8)。
- openmetadata-ingestion のライセンスが 1.6 以降 Collate Community License
  (OSI 認定外)である点は、採用時に組織のポリシー確認が必要。

## 7. 生成される証跡

| ファイル(verification/phase3/) | 内容 |
|---|---|
| demo-catalog-ingest.log / -profile.log / -lineage.log / -drift.log | 各デモの生ログ(シナリオが自動保存) |
| api-tables.json | 取り込まれたテーブル一覧(C-1) |
| api-table-daily-sales.json / api-table-customers.json | テーブル詳細。説明・オーナー・タグ・用語の付与結果(C-1) |
| api-profile-customers.json / api-profile-daily-sales.json | プロファイル統計(C-2) |
| api-lineage-customer-summary.json / api-lineage-daily-sales.json | リネージュグラフ(C-3) |
| api-drift-versions-before.json / -after.json | C-4 前後のバージョン履歴 |
| resource-usage.log | 起動時間・メモリ実測 |
| ui/*.png | UI スクリーンショット(各節の「実測」参照) |

このほか、フェーズ3 構築時の回帰確認(品質・リネージュ領域のデモが tools イメージ
更新後も動くことの確認)で取得した demo-quality-*.log / demo-lineage.log /
clean-db.log / down-lineage.log も同じディレクトリに置いています(本ガイドの
手順からは生成されません)。

## 8. トラブルシューティング(カタログ領域)

- **UI が開けない**: URL のポートは `.env` の `OM_SERVER_HOST_PORT` で決まります(§3)。
  他プロセスと衝突する場合は `.env` の値を変えて `make up-catalog` し直してください。
- **起動が終わらない / unhealthy になる**: 初回は om-migrate の完了後に om-server が
  起動するため 3〜6 分かかります(実測)。Docker のメモリ割当が 6 GiB 未満の場合や、
  他プロファイル(lineage 等)と同時起動している場合はまず割当・停止状況を
  確認してください(`docker stats`)。
- **ログに `ERROR ... relation "pg_stat_statements" does not exist` が出る**: 想定内です。
  取り込み前の接続テストのうち「クエリログ取得(GetQueries)」という**任意ステップ**が、
  デモ用 DB に pg_stat_statements 拡張がないため失敗と報告されるものです。
  ワークフロー本体の成否(`Workflow Success %: 100.0`)には影響しません。
  クエリログ由来のリネージュ・利用状況分析を使いたい場合のみ、この拡張の導入が
  必要になります(本デモではスコープ外)。
- **`network ... not found` で起動に失敗する**: プロファイルの起動・停止を繰り返すと、
  既存コンテナが削除済みネットワークを参照したままになることがあります。
  `docker compose --profile base up -d --force-recreate postgres-demo` のように
  該当サービスを作り直してください(構築時に実際に発生した事象です)。
- **C-4 のバージョン番号が出力例と違う**: バージョンは操作履歴に依存します(§4.4 の注記)。
  確認すべき不変条件は「メジャーバージョンが +1.0 されること」と
  「変更履歴に削除列(prefecture)が記録されること」の 2 点です。
- **`make demo-catalog-*` が classify で `No module named 'presidio_analyzer'` になる**:
  tools イメージが古い(フェーズ3 より前の)ままです。`make build-tools` で
  再ビルドしてください。

## 9. 片付け

```console
$ make down-catalog   # OpenMetadata のみ停止(カタログの内容は保持)
$ make down           # 全プロファイル停止(データは保持)
$ make clean-db       # 全停止 + ボリューム削除(カタログの内容・デモ DB とも初期化)
```

Docker イメージまで含めた完全な後片付けの手順は、[README.md](../../README.md) の
「後片付け」を参照してください。
