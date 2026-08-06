# データリネージュガイド — OpenLineage + Marquez で「実行の事実」を追う

このガイドは、共通パイプライン(raw → staging → mart)から **OpenLineage** の
リネージュイベントを発行し、**Marquez** の UI と API でジョブ・データセット・
リネージュグラフを確認するためのものです。対象読者は両製品を初めて触るデータエンジニアです。

- OpenLineage クライアント: `openlineage-python` **1.52.0**(Apache-2.0)
- リネージュサーバ/UI: **Marquez 0.51.1**(Apache-2.0)

本ガイドの手順・出力例は、すべて実際に実行して得た結果のみに基づいています
(生ログ・API レスポンス・UI スクリーンショット: `verification/phase2/`)。

---

## 1. 前提条件

| 項目 | 要件 |
|---|---|
| OS | Linux / macOS / Windows(WSL2) |
| 必須ソフトウェア | Docker Desktop または Docker Engine + Compose v2(検証環境: Docker 28.1.1 / Compose v2.35.1) |
| CPU アーキテクチャ | **Marquez のイメージは amd64 のみ提供**。Apple Silicon(arm64)ではエミュレーションで動作します(compose に `platform: linux/amd64` 指定済み。起動が遅くなることがあります) |
| メモリ | lineage 一式の実測(アイドル時): marquez-api 約 253 MiB + marquez-db 約 75 MiB + marquez-web 約 23 MiB ≒ **約 0.35 GiB**(+ デモ用 DB 約 35 MiB) |
| ポート | ホスト側で 5000(API)/ 5001(API 管理)/ 3000(Web UI)を使用。競合時は `.env` で変更可能(→ §7) |
| ネットワーク | 初回のみイメージ取得でインターネット接続が必要 |

> **macOS の注意**: macOS ではポート 5000 を OS(AirPlay Receiver)が予約していることが
> あります(Marquez README 記載の既知問題)。その場合は §7 の手順でポートを変更してください。

商用 SaaS には一切接続しません。イベントはローカルの Marquez にのみ送信されます。

## 2. この領域の登場人物(初学者向けの整理)

- **OpenLineage** は「リネージュイベントの標準仕様 + クライアントライブラリ」です。
  サーバではありません。ジョブの実行(Run)ごとに
  `START` → `COMPLETE`(失敗時は `FAIL`)というイベントを発行します。
  イベントには「このジョブは何を読み(inputs)、何を書いたか(outputs)」が含まれます。
- **Marquez** は OpenLineage イベントを受け取って蓄積・可視化するサーバ(API + Web UI)です。
  受け取ったイベントからジョブ・データセット・リネージュグラフを組み立てます。
- 本デモの構成(オーケストレータは使いません。plan.md §3.3):

```
pipeline/run_pipeline.py --openlineage
  ├─ seed          : CSV → raw.*(4テーブル)
  ├─ build_staging : raw.* → staging.stg_orders
  └─ build_mart    : staging → mart.daily_sales / mart.customer_summary
        │
        └─ 各ステップで RunEvent(START/COMPLETE/FAIL)を HTTP で送信
             → marquez-api(:5000)→ Marquez UI(:3000)で可視化
```

- イベント発行は `openlineage-python` クライアントを Python から直接呼んでいます。
  「イベントがどう作られるか」は [pipeline/run_pipeline.py](../../pipeline/run_pipeline.py) の
  `LineageEmitter` クラスに集約してあり、送信先の設定は
  [lineage/openlineage.yml](../../lineage/openlineage.yml)(HTTP transport)です。
- 名前の付き方(OpenLineage の命名規約):
  - ジョブは namespace `demo_pipeline` に `run_pipeline.seed` などの名前で登録されます。
  - データセットは namespace `postgres://postgres-demo:5432` に
    `demo.raw.customers` のような `DB名.スキーマ.テーブル` 形式で登録されます。
  - seed の入力 CSV は namespace `file` のデータセットとして登録されます。
- `build_mart` の出力 `mart.daily_sales` には**カラムレベルリネージュ facet**
  (`columnLineage`、spec 1-2-0)を付与しています(§4.2 で確認)。

## 3. 環境構築

リポジトリのルートで以下を実行します(全領域共通のセットアップです。
[README.md](../../README.md) の「環境構築」で実施済みならスキップできます)。

```console
$ make setup
```

Marquez 一式(compose profile: `lineage`)の起動・停止は次のとおりです。
デモコマンドが自動起動するため、通常は手動で起動する必要はありません。

```console
$ make up-lineage      # marquez-db / marquez-api / marquez-web を起動
$ make down-lineage    # lineage 一式のみ停止(蓄積したリネージュは保持)
$ make down            # 全プロファイル停止(データ保持)
$ make clean-db        # 全停止 + データ削除(Marquez の蓄積イベントも消える)
```

### Marquez UI の URL の確認

Marquez UI の URL は **`http://localhost:<MARQUEZ_WEB_HOST_PORT>`** です。
ポートは自分の `.env` の値で決まります(未設定なら既定の **3000**)。
次のコマンドで確認できます:

```console
$ grep MARQUEZ_WEB_HOST_PORT .env || echo "未設定(既定の 3000)"
```

各デモコマンドも、実行結果の最後に実際の URL を表示します。
**以降の本文では既定の http://localhost:3000 と表記しますが、必ず自分の環境の
ポートに読み替えてください**(このリポジトリの検証ログ・スクリーンショット内の URL が
`13000` なのは、検証環境でポート競合があり `.env` で変更していたためです。→ §7)。

## 4. デモの実行手順

### 4.0 実行結果の見方(最初にお読みください)

| コマンド | 何を見せるデモか | 期待する最終出力(成功の目印) |
|---|---|---|
| `make demo-lineage` | 正常系: 3 ステップの実行が Marquez に記録される | `リネージュデモ結果: 全ステップ COMPLETE(exit 0)` |
| `make demo-lineage-fail` | 異常系: 失敗した実行が FAILED として追跡できる | `リネージュ異常系デモ結果: 失敗 Run を検知(exit 1)` のあとに make の `Error 1` |

異常系デモは「パイプラインの失敗を Marquez が正しく記録したこと」を確認して
**エラー終了するのが正解**です(検知の証明としてコマンド全体は非 0 で終わります。
シナリオの exit 1 を受けた make 自体の終了コードは 2 になります — make の仕様)。

### 4.1 B-1 正常系: パイプライン実行 → リネージュ収集

```console
$ make demo-lineage
```

このコマンドは (1) デモ用 DB と Marquez 一式を起動し、(2) クリーンデータで
パイプラインを実行しながら OpenLineage イベントを発行し、(3) 証跡として
Marquez API のレスポンスを保存します。

パイプライン部分の出力(実測。runId は実行ごとに変わります):

```text
=== クリーンデータでパイプライン実行(OpenLineage イベント発行あり)===
=== step: seed ===
[openlineage] START    run_pipeline.seed (runId=019fcbff-fbda-77c3-abde-afce53092be6)
[sql] 01_create_raw.sql を実行
[seed] raw.customers: 1000 行
[seed] raw.products: 200 行
[seed] raw.orders: 5000 行
[seed] raw.order_items: 12561 行
[openlineage] COMPLETE run_pipeline.seed
=== step: build_staging ===
[openlineage] START    run_pipeline.build_staging (runId=019fcbff-fefd-7335-8868-814993255a2f)
[sql] 02_staging.sql を実行
[build_staging] staging.stg_orders: 11927 行
[openlineage] COMPLETE run_pipeline.build_staging
=== step: build_mart ===
[openlineage] START    run_pipeline.build_mart (runId=019fcc00-021b-7848-92f4-f341db714140)
[sql] 03_mart.sql を実行
[build_mart] mart.daily_sales: 365 行
[build_mart] mart.customer_summary(ビュー): 1000 行
[openlineage] COMPLETE run_pipeline.build_mart
パイプライン完了
```

成功の目印(画面の最後):

```text
リネージュデモ結果: 全ステップ COMPLETE(exit 0)
```

#### UI 確認ポイント(スクリーンショット: `verification/phase2/ui/`)

ブラウザで Marquez UI を開きます(URL は §3 の方法で確認。既定は
http://localhost:3000 で、デモ出力の最後にも実際の URL が表示されています)。
開けない場合は §7 の最初の項を確認してください。

1. **ジョブ一覧**: 左サイドバーのジョブ(歯車)アイコンから Jobs 画面を開き、
   右上の namespace セレクタ(`ns default` と表示されている部分)で **`demo_pipeline`** を
   選びます。`run_pipeline.seed` / `run_pipeline.build_staging` / `run_pipeline.build_mart` の
   3 ジョブが並び、LATEST RUN STATE がすべて **COMPLETED**(緑)になります
   (実測: `b1-jobs-list.png`。実行時間も 300 ms 前後で記録されています)。
2. **リネージュグラフ**: ジョブ名(例: `run_pipeline.build_mart`)をクリックすると
   グラフ画面に遷移します。CSV 4 ファイル → `seed` → `demo.raw.*` 4 テーブル →
   `build_staging` → `demo.staging.stg_orders` → `build_mart` →
   `demo.mart.daily_sales` / `demo.mart.customer_summary` という
   **ジョブとデータセットが交互に連なるグラフ**が表示され、各データセットノードには
   列名も表示されます(実測: `b1-lineage-graph-build-mart.png`)。
   これが Marquez の思想の核心で、**グラフは「実行の事実(イベント)」だけから
   組み立てられています**。
3. **データセット側からの遡り**: 左サイドバーのデータセット(円筒)アイコン →
   namespace `postgres://postgres-demo:5432` を選ぶとテーブル一覧が出ます。
   `demo.mart.daily_sales` をクリックすると、このテーブルを終点とする
   上流一式(どの CSV・どのジョブに由来するか)が追えます
   (実測: `b1-lineage-dataset-daily-sales.png`)。

> **Run の履歴は実行のたびに蓄積されます**: Marquez は「実行の事実」をすべて記録する
> ため、デモを繰り返すと COMPLETED の Run が増えていき、異常系デモ(§4.2)を一度でも
> 実行していれば **FAILED の Run が 1 件、履歴に残り続けます**。これは正常であり、
> むしろ Marquez の価値そのものです(例: 正常系 2 回 + 異常系 1 回のあとの履歴は
> COMPLETED 8 件 + FAILED 1 件になります)。B-1 の成否は「コマンドが
> `リネージュデモ結果: 全ステップ COMPLETE(exit 0)` で終わること」と
> 「ジョブ一覧の LATEST RUN STATE(**最新** Run の状態)がすべて COMPLETED であること」で
> 判断してください。履歴ごと消してやり直したい場合は `make clean-db` です。

#### カラムレベルリネージュの確認(API)

`mart.daily_sales` に付与した `columnLineage` facet は、保存済みの API レスポンス
`verification/phase2/api-dataset-daily-sales.json` で確認できます
(UI のデータセット詳細からも辿れますが、facet の生の構造は API の方が分かりやすいです)。
`total_amount` 列の部分(実測・抜粋):

```json
        "total_amount": {
          "inputFields": [
            {
              "field": "amount",
              "name": "demo.staging.stg_orders",
              "namespace": "postgres://postgres-demo:5432",
              "transformations": [
                {
                  "description": "sum(amount)",
                  "masking": false,
                  "subtype": "AGGREGATION",
                  "type": "DIRECT"
                }
              ]
            },
            {
              "field": "order_date",
              "name": "demo.staging.stg_orders",
              "namespace": "postgres://postgres-demo:5432",
              "transformations": [
                {
                  "description": "GROUP BY order_date",
                  "masking": false,
                  "subtype": "GROUP_BY",
                  "type": "INDIRECT"
                }
              ]
            }
          ],
          "transformationDescription": "sum(amount)",
          "transformationType": "AGGREGATION"
        }
```

「`total_amount` は `stg_orders.amount` の集計(DIRECT/AGGREGATION)で、
`order_date` はグルーピングとして間接的に影響(INDIRECT/GROUP_BY)」という
SQL(03_mart.sql)の内容がそのまま構造化されています。
**この facet はパイプライン側が自己申告したものです**(SQL を解析して自動生成された
ものではありません)。この点は後述の長所短所に直結します。

自分で API を叩いて確認することもできます:

```console
$ docker compose --profile tools run --rm -T tools \
    /opt/venv/lineage/bin/python lineage/marquez_api.py lineage demo.mart.daily_sales
```

### 4.2 B-2 異常系: パイプライン失敗の追跡

「mart 構築 SQL にバグが入った」状況を再現します。`--simulate-failure` により
`build_mart` が存在しない列を参照する SQL([pipeline/sql/03_mart_broken.sql](../../pipeline/sql/03_mart_broken.sql))を
実行して失敗し、`FAIL` イベントが発行されます。

```console
$ make demo-lineage-fail
```

出力(実測。seed / build_staging は成功し、build_mart だけが失敗します):

```text
=== step: build_mart ===
[openlineage] START    run_pipeline.build_mart (runId=019fcbf3-f736-74dc-aba8-20fbcaa3792b)
[sql] 03_mart_broken.sql を実行
[openlineage] FAIL     run_pipeline.build_mart
エラー: step build_mart が失敗しました: column "amount_with_tax" does not exist
LINE 13:     sum(amount_with_tax)    AS total_amount   -- ← この列は...
                 ^
```

シナリオは続けて Marquez API から `run_pipeline.build_mart` の Run 履歴を取得し、
最新 Run が FAILED で記録されていることを確認します。成功の目印(画面の最後):

```text
=== 検知結果: 最新 Run の状態 ===
      "state": "FAILED",
Marquez 上で run_pipeline.build_mart の Run が FAILED として記録されています。
UI: http://localhost:13000 の Jobs → run_pipeline.build_mart でも確認できます。
リネージュ異常系デモ結果: 失敗 Run を検知(exit 1)
make: *** [Makefile:58: demo-lineage-fail] Error 1
```

(`Makefile:58` の行番号は Makefile の変更で変わることがあります。
また URL のポートは検証環境の設定値です。既定では 3000 になります。)

#### UI 確認ポイント

1. **ジョブ一覧**(namespace: `demo_pipeline`): `run_pipeline.build_mart` の
   LATEST RUN STATE だけが **FAILED**(赤)になり、seed / build_staging は
   COMPLETED のまま残ります。「**どの段で止まったか**」が一覧で分かります
   (実測: `b2-jobs-list-failed.png`)。
2. **リネージュグラフ**: `run_pipeline.build_mart` のグラフでは失敗したジョブの
   ノードが**赤色**で表示され、上流(成功した部分)は緑のまま残ります
   (実測: `b2-lineage-graph-build-mart-failed.png`)。
3. **エラー内容も Run に残ります**: FAIL イベントに `errorMessage` facet
   (SQL エラーメッセージ本文)を付けて送っているためです。
   保存済みの `verification/phase2/api-runs-build-mart.json`(実測・抜粋):

```json
        "errorMessage": {
          "_producer": "https://github.com/OpenLineage/OpenLineage/tree/1.52.0/client/python",
          "_schemaURL": "https://openlineage.io/spec/facets/1-0-1/ErrorMessageRunFacet.json#/$defs/ErrorMessageRunFacet",
          "message": "column \"amount_with_tax\" does not exist\nLINE 13:     sum(amount_with_tax)    AS total_amount   -- ← この列は...\n                 ^\n",
          "programmingLanguage": "python"
        },
```

> **実測で確認した UI の挙動**: 失敗直後に `demo.mart.daily_sales` の
> データセットグラフを開くと、上流エッジが表示されず単独ノードになることがあります。
> これは FAIL イベントには outputs を付けていないため、ジョブの「最新バージョン」の
> 入出力が失敗時点の情報で更新されるためです。次に `make demo-lineage`(正常系)を
> 実行すると元どおり全系譜が表示されます。
> なお、失敗した SQL はロールバックされるため、DB の既存の mart テーブル自体は壊れません。

## 5. Marquez / OpenLineage の設計思想と長所・短所(このデモで確認できた範囲)

**Marquez は「実行(Run)の事実」を時系列で記録する、運用視点のリネージュ**です。
「昨夜のパイプラインはどのデータを読んで、どの段で失敗したか」に答えます。

長所(実測に基づく):

- **実行の記録が残る**: ジョブごとに Run の履歴(状態・開始/終了時刻・所要時間・
  エラー内容)が蓄積され、UI で FAILED がひと目で分かる(§4.2)。
  品質チェック(フェーズ1)が「データの中身」を見るのに対し、こちらは
  「処理の流れと結果」を見る、補完関係にある。
- **標準仕様(OpenLineage)ベース**: イベントは Airflow・dbt・Spark など多数の
  ツールが発行でき、受け側も Marquez 以外に交換可能。本デモのように
  素の Python からでも公式クライアントだけで発行できる(依存 1 パッケージ)。
- **イベントの中身が読める**: RunEvent は単なる JSON で、facet(schema /
  columnLineage / sql / errorMessage)を足すだけで表現が豊かになる。
  仕様の学習教材としても優れている。
- **軽量**: 一式で実測約 0.35 GiB。OpenMetadata(フェーズ3、公式要件 6 GiB)と
  比べて圧倒的に軽い。

短所・注意点(実測・調査に基づく):

- **発行しない処理は一切見えない**: リネージュは「送られてきたイベント」だけから
  作られる。パイプライン側に発行実装(または対応ツールの利用)が必須で、
  手書きスクリプトの場合は本デモの `LineageEmitter` のような実装コストがかかる。
  入出力やカラムリネージュの内容も**自己申告**であり、実装が間違っていれば
  グラフも間違う(SQL 解析による自動検証はない)。
- **amd64 イメージのみ提供**: Apple Silicon ではエミュレーション動作(§1)。
- **リリース運用がやや不安定**: 採用した 0.51.1 は Docker Hub の最新タグだが、
  GitHub 上のリリースノート・CHANGELOG は 0.50.0 止まり(選定判断は
  docs/build-log.md 参照)。
- カラムレベルリネージュは facet として保存されるが、0.51.1 の UI での
  可視化は限定的(本デモでは API レスポンスで構造を確認する手順とした)。

> **フェーズ3 との対比(予告)**: OpenMetadata は逆に「実行」ではなく
> 「定義(SQL・メタデータ)」からリネージュを導出します。同じ mart テーブルを
> 両方式で見比べるのがフェーズ3 のテーマです(比較軸3)。

## 6. 生成される証跡

| ファイル | 内容 |
|---|---|
| `verification/phase2/demo-lineage.log` / `demo-lineage-fail.log` | 各シナリオの生ログ |
| `verification/phase2/terminal-demo-lineage.log` / `terminal-demo-lineage-fail.log` | make コマンドの端末出力全体(make の `Error 1` 行を含む) |
| `verification/phase2/api-*.json` | Marquez API レスポンス(namespaces / jobs / datasets / dataset 詳細 / リネージュグラフ / 失敗 Run 履歴) |
| `verification/phase2/ui/*.png` | Marquez UI のスクリーンショット(正常系 b1-*、異常系 b2-*) |
| `verification/phase2/web-ui-check.log` | Web UI / API のホストからの疎通確認 |
| `verification/phase2/resource-usage.log` | lineage 一式の実測メモリ |

## 7. トラブルシューティング(リネージュ領域)

- **UI(http://localhost:3000)が開けない**: 原因は主に次の 2 つです。
  1. **Marquez が起動していない**: `make down` 後は停止しています。
     `docker compose --profile lineage ps` で確認し、`make up-lineage` で起動してください。
  2. **ポートが `.env` で変更されている**: §3 のコマンドで実際のポートを確認し、
     その番号で開いてください(例: `MARQUEZ_WEB_HOST_PORT=13000` なら
     http://localhost:13000)。

- **ポート競合で起動に失敗する / macOS で 5000 が使えない**:
  `.env` に以下を追記して(値は例)、`make down-lineage && make up-lineage` で再起動
  してください。ブラウザで開く URL も読み替えます。

  ```dotenv
  MARQUEZ_API_HOST_PORT=15000
  MARQUEZ_ADMIN_HOST_PORT=15001
  MARQUEZ_WEB_HOST_PORT=13000
  ```

  ※ コンテナ間の通信(イベント送信)はコンテナ名 `marquez-api:5000` を使うため、
  ホスト側ポートの変更はデモの動作に影響しません。

- **`Marquez API(...)が 120 秒以内に応答しませんでした`**: 初回起動は DB マイグレーションの
  ぶん時間がかかることがあります。`docker compose --profile lineage logs marquez-api` で
  起動ログを確認し、起動完了後にデモを再実行してください。Apple Silicon の
  エミュレーション環境では特に遅くなります。
- **イベントが Marquez に届いているか切り分けたい**: `lineage/openlineage.yml` の
  transport を `type: console` に切り替えると、送信する代わりにイベント JSON が
  標準出力に表示されます(切り分け後は http に戻してください)。
- **UI にジョブが出ない**: namespace セレクタが `default` のままになっていないかを
  確認してください(ジョブは `demo_pipeline`、データセットは
  `postgres://postgres-demo:5432` にあります)。
- **正常系しか実行していないのに UI に FAILED が表示されている**: 過去に異常系デモ
  (§4.2)を実行した履歴です。Run 履歴は蓄積される仕様で、最新の実行結果は
  ジョブ一覧の LATEST RUN STATE で確認します(§4.1 の注記)。
  履歴ごとリセットするには `make clean-db` を実行してください。
- **`demo.mart.daily_sales` のグラフが単独ノードになる**: 直前に異常系デモを実行した
  場合の仕様どおりの挙動です(§4.2 の注記)。`make demo-lineage` を実行すると戻ります。
- **リネージュを一からやり直したい**: `make clean-db` で Marquez の蓄積イベントごと
  削除できます(次回起動時に自動で再初期化されます)。

## 8. 片付け

```console
$ make down-lineage   # Marquez のみ停止(リネージュは保持)
$ make down           # すべて停止(データ保持)
$ make clean-db       # すべて停止 + データ削除
```

Docker イメージまで含めた完全な後片付けの手順は、[README.md](../../README.md) の
「後片付け」を参照してください。
