# データ品質ガイド — Soda Core と Great Expectations を比較しながら体験する

このガイドは、同一のデータ・同一の品質チェックを **Soda Core 4.19.0** と
**Great Expectations(GX)1.19.1** の両方で実行し、2 製品の設計思想の違いを
体感するためのものです。対象読者は両製品を初めて触るデータエンジニアです。

本ガイドの手順・出力例は、すべて実際に実行して得た結果のみに基づいています
(生ログ: `verification/phase1/`)。

---

## 1. 前提条件

| 項目 | 要件 |
|---|---|
| OS | Linux / macOS(Apple Silicon 可)/ Windows(WSL2) |
| 必須ソフトウェア | Docker Desktop または Docker Engine + Compose v2(検証環境: Docker 28.1.1 / Compose v2.35.1) |
| CPU アーキテクチャ | amd64 / arm64 両対応(本領域で使うイメージはすべてマルチアーチ) |
| メモリ | 本領域は軽量。DB(postgres:16)実測 約 35 MiB + ツール実行時 約 0.5 GiB |
| ネットワーク | 初回のみイメージ取得・pip インストールでインターネット接続が必要 |

このガイドで登場する製品のライセンス:

- Soda Core: **Elastic License 2.0**(OSI 認定の OSS ではないが、ソース公開・無料利用可能)
- Great Expectations: Apache-2.0

商用 SaaS(Soda Cloud / GX Cloud)には一切接続しません。

## 2. 環境構築

リポジトリのルートで以下を実行します。

```console
$ make setup
```

これは次の 2 つを行います。

1. `.env` がなければ `.env.example` からコピーして作成する
   (**中身はすべてローカルデモ専用の設定値**です。実運用の値は入れないでください)。
2. ツール実行用 Docker イメージ(`dgd-tools:phase3`)をビルドする。
   Python 3.11 上に Soda Core と GX(および他領域のツール)を venv 分離で
   インストールします(数分かかります)。

デモ用 DB は各デモコマンドが自動起動しますが、手動で操作したい場合は:

```console
$ make up-base    # デモ用 DB(postgres:16)起動
$ make down      # 停止(データ保持)
$ make clean-db  # 停止 + データ削除
```

### 使用するサンプルデータ

小さな EC(通販)の合成データです(実在の個人情報は含みません)。
コミット済み CSV(`data/seed/csv/`)を `raw` スキーマに投入し、
`staging` → `mart` へ SQL で変換します。

| テーブル | 行数 | 品質チェックの対象 |
|---|---|---|
| raw.customers | 1,000 | email の欠損 |
| raw.products | 200 | (本領域では対象外) |
| raw.orders | 5,000 | order_id の重複、スキーマ(列と型) |
| raw.order_items | 12,561 | quantity・unit_price の値域 |

## 3. 4 つの品質チェック(両製品共通)

**まったく同じ内容のチェック**を両製品に実装してあります。これが比較の土台です。

| # | チェック内容 | Soda での定義 | GX での定義 |
|---|---|---|---|
| (a) | customers.email に欠損(NULL)がない | `missing:` | `ExpectColumnValuesToNotBeNull` |
| (b) | orders.order_id が一意 | `duplicate:` | `ExpectColumnValuesToBeUnique` |
| (c) | order_items.quantity ≥ 1、unit_price が 0〜100,000 | `invalid:` + `valid_min`/`valid_max` | `ExpectColumnValuesToBeBetween` ×2 |
| (d) | orders の列構成と型が期待どおり | `columns` の `data_type` 宣言 + `schema:` | `ExpectTableColumnsToMatchOrderedList` + `ExpectColumnValuesToBeOfType` |

定義ファイルの場所:

- Soda: `quality/soda/contracts/*.yaml`(データセットごとに 1 ファイル)+ 接続設定 `quality/soda/ds_config.yml`
- GX: `quality/gx/run_checks.py`(1 スクリプトに 4 チェックすべて)

## 4. デモの実行手順

### 4.0 実行結果の見方(最初にお読みください)

このデモには「わざと品質違反を混入させ、ツールに**検知させる**」シナリオ
(A-2 / A-4)が含まれます。検知シナリオでは、**違反を見つけるとコマンドが
エラー終了し、画面に `Error` と表示されます。それが成功(正解)です。**
これは、CI やパイプラインに品質チェックを組み込んだとき「違反があれば処理を
止められる」ことを確認するための仕様です。逆に A-2 / A-4 がエラーなしで
終わってしまったら、違反を見逃したことになり失敗です。

各コマンドの成否は**画面の最後に出る行**で判定できます(いずれも実測の出力):

| コマンド | 期待する最終出力(これが出れば成功) |
|---|---|
| `make demo-quality-soda` | `Soda 結果: 全 contract 成功(exit 0)` |
| `make demo-quality-soda-ng` | `Soda 結果: 品質違反を検知(exit 1)` + make の `Error 1` 表示 |
| `make demo-quality-gx` | `GX 結果: 全チェック成功(exit 0)` |
| `make demo-quality-gx-ng` | `GX 結果: 品質違反を検知(exit 1)` + make の `Error 1` 表示 |

> 補足(exit 0 / exit 1 とは): コマンドの終了コードのことで、0 が正常終了、
> 0 以外がエラー終了を意味します。検知シナリオは「違反を検知したらエラー終了する」
> 設計のため、exit 1 とそれを受けた make の `Error 1` 表示が正解の状態です。
> なお、シナリオの exit 1 を受けた **make コマンド自体の終了コードは 2** になります
> (make の仕様)。スクリプトから `$?` で判定する場合はご注意ください。

### 4.1 Soda Core 正常系(A-1)

```console
$ make demo-quality-soda
```

クリーンな seed CSV を DB に投入し、3 つの contract を `soda contract verify` で
検証します。**全チェックが成功し、正常終了すれば成功**です。実際の出力(抜粋):

```
### Contract results for postgres_demo/demo/raw/customers
+----------+-------------------+-------------+-----------+---------------------------+
| Column   | Check             | Threshold   | Outcome   | Diagnostics               |
+==========+===================+=============+===========+===========================+
| email    | No missing values | level: fail | ✅ PASSED | missing_count: 0          |
|          |                   | must be: 0  |           | missing_percent: 0.0      |
|          |                   |             |           | check_rows_tested: 1000   |
|          |                   |             |           | dataset_rows_tested: 1000 |
+----------+-------------------+-------------+-----------+---------------------------+
```

**成功の目印** — 画面の最後にこの行が出ます(実測):

```
Soda 結果: 全 contract 成功(exit 0)
```

### 4.2 Soda Core 異常系(A-2)

```console
$ make demo-quality-soda-ng
```

`data/seed/generate.py --inject all` で 4 種類の品質違反
(email NULL ×30 / order_id 重複 ×20 / quantity≤0 ×15 / unit_price 負値 ×10)を
混入したデータを投入してから、**同じ contract** を実行します。
このシナリオは**違反を検知してエラー終了すれば成功**です(§4.0 参照)。
出力(抜粋):

```
| email    | No missing values | level: fail | ❌ FAILED | missing_count: 30         |
|          |                   | must be: 0  |           | missing_percent: 3.0      |
```

**成功の目印** — 画面の最後にこの 2 行が出ます(実測。`Error` の表示が正解です。
`Makefile:38` の数字は今後の変更で変わることがあります):

```
Soda 結果: 品質違反を検知(exit 1)
make: *** [Makefile:38: demo-quality-soda-ng] Error 1
```

### 4.3 GX 正常系(A-3)

```console
$ make demo-quality-gx
```

同じクリーンデータに対して GX の Checkpoint を実行します。
**全チェックが成功し、正常終了すれば成功**です。結果は JSON 全文が表示されます。
以下は email チェック部分の抜粋です(端末出力そのまま。インデントが深いのは
JSON 全体の中の一部のため):

```json
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "success": true,
                    "kwargs": {
                        "batch_id": "postgres_demo-raw.customers",
                        "column": "email"
                    },
                    "result": {
                        "element_count": 1000,
                        "unexpected_count": 0,
                        "unexpected_percent": 0.0,
                        "partial_unexpected_list": [],
                        "partial_unexpected_counts": []
                    }
```

**成功の目印** — 画面の最後にこの 2 行が出ます(実測):

```
GX チェック結果: 全チェック成功
GX 結果: 全チェック成功(exit 0)
```

さらに HTML レポート(**Data Docs**)が `quality/gx/output/data_docs/index.html` に
生成されます。ブラウザで開くと、チェックごとの成否・統計を GUI で確認できます。

### 4.4 GX 異常系(A-4)

```console
$ make demo-quality-gx-ng
```

Soda 異常系とまったく同じ汚染データに対して GX を実行します。
このシナリオも**違反を検知してエラー終了すれば成功**です(§4.0 参照)。
出力には失敗した値の実例(`partial_unexpected_list`)まで含まれます。
以下は quantity チェック部分の抜粋です(端末出力そのまま):

```json
                    "expectation_type": "expect_column_values_to_be_between",
                    "success": false,
                    "kwargs": {
                        "batch_id": "postgres_demo-raw.order_items",
                        "column": "quantity",
                        "min_value": 1.0
                    },
                    "result": {
                        "element_count": 12561,
                        "unexpected_count": 15,
                        "unexpected_percent": 0.11941724385001193,
                        "partial_unexpected_list": [
                            -1,
                            0,
                            -2,
                            0,
                            0,
                            0,
                            0,
                            -1,
                            0,
                            -1,
                            -1,
                            -1,
                            -2,
                            -1,
                            -1
                        ],
                        "missing_count": 0,
                        "missing_percent": 0.0,
                        "unexpected_percent_total": 0.11941724385001193,
                        "unexpected_percent_nonmissing": 0.11941724385001193,
                        "partial_unexpected_counts": [
                            {
                                "value": -1,
                                "count": 7
                            },
                            {
                                "value": 0,
                                "count": 6
                            },
                            {
                                "value": -2,
                                "count": 2
                            }
                        ]
                    }
```

(JSON 全文は `verification/phase1/demo-quality-gx-ng.log` を参照)

**成功の目印** — 画面の最後にこの 2 行が出ます(実測。`Error` の表示が正解です。
`Makefile:44` の数字は今後の変更で変わることがあります):

```
GX 結果: 品質違反を検知(exit 1)
make: *** [Makefile:44: demo-quality-gx-ng] Error 1
```

## 5. 比較: 同じ違反を両製品はどう報告したか

異常系デモ(同一の汚染データ)の実測結果の対比です。

| 違反(混入内容) | Soda の報告 | GX の報告 |
|---|---|---|
| email NULL ×30 | `missing_count: 30` / `missing_percent: 3.0` | `unexpected_count: 30`、`partial_unexpected_counts` に null の内訳 |
| order_id 重複 ×20 組 | `duplicate_count: 20`(**重複している値の数**) | `unexpected_count: 40`(**重複に関与する全行数**)+ 重複値のサンプル |
| quantity ≤ 0 ×15 | `invalid_count: 15` | `unexpected_count: 15` + 実際の値 `[0, -1, -2, ...]` |
| unit_price 負値 ×10 | `invalid_count: 10` | `unexpected_count: 10` + 実際の値 |

> 注目: **同じ「order_id 重複 20 組」に対して Soda は 20、GX は 40 と報告します。**
> どちらも正しく、「重複した値の個数」を数えるか「重複に巻き込まれた行数」を
> 数えるかという設計の違いです。ツールの数値を読むときは定義の確認が必要、
> という教訓がそのまま体験できます。

### 設定の分量と形式

| 観点 | Soda Core | GX |
|---|---|---|
| 定義形式 | YAML(contract)。4 チェックで計 44 行(コメント除く、3 ファイル) | Python。context → data source → asset → batch → suite → validation definition → checkpoint と概念が 7 つ登場 |
| 実行方法 | CLI 1 コマンド(`soda contract verify`) | Python スクリプトを実行 |
| 結果の見せ方 | 表形式で簡潔。人間がターミナルで読む前提 | JSON 全文 + Data Docs(HTML)。機械処理・共有向き |
| 失敗時の情報量 | 件数・割合(diagnostics) | 件数・割合に加え**違反値の実例リスト**、型の観測値など |

### 長所・短所(このデモで実際に確認できた範囲)

**Soda Core**

- 長所: 宣言的な YAML 十数行で始められる導入の軽さ。CLI 出力が簡潔で、
  「何が契約違反か」が一目で分かる。接続設定と契約が分離されており構成が単純。
- 短所: チェックは用意された check type の範囲に制約される。
  v4 で構文が刷新されたため、Web 上に多い旧 SodaCL(v3)の情報がそのまま使えない
  (本デモは v4 公式リファレンスのみに準拠)。ライセンスは Elastic License 2.0 で
  OSI 認定 OSS ではない。
- 補足: Soda v4 の「contract」は*技術的な品質チェック定義*であり、フェーズ4 で扱う
  ODCS(生産者と消費者の合意文書)とは別概念です。名前が似ているので注意してください。

**Great Expectations**

- 長所: 失敗行の実例・統計まで含む圧倒的な結果の情報量。Data Docs による HTML
  レポート。Python ネイティブなので任意ロジックへの拡張やパイプラインへの
  組み込みが自然にできる。
- 短所: 概念数が多く(Data Source / Asset / Batch / Suite / Validation Definition /
  Checkpoint)、最初の 1 チェックを動かすまでのコード量・学習コストが大きい。
  型チェックは SQLAlchemy の観測値(例: `VARCHAR(20)`)に依存するため、
  DB の型表現を正確に知らないと書けない(§7 参照)。

**使い分けの目安**: チームにまず品質ゲートを導入したい・非 Python 環境も混在
→ Soda。失敗データの調査・レポート共有・カスタムロジックまで踏み込みたい
→ GX。両者は排他ではなく、同じ DB に外側から当てる「独立したチェック」として
共存できます(本デモの構成そのものです)。

## 6. 生成される証跡

| 場所 | 内容 |
|---|---|
| `verification/phase1/demo-quality-{soda,gx}[-ng].log` | 各デモの生実行ログ(実行のたび上書き) |
| `verification/phase1/terminal-demo-quality-*.log` | `make` コマンドの端末出力全体(make のメッセージ含む。ガイドの「成功の目印」の出典) |
| `verification/phase1/gx_data_docs/` | GX Data Docs(HTML)の保存版 |
| `quality/gx/output/` | GX の実行時出力(最新の結果 JSON と Data Docs) |
| `data/seed/csv-injected/` | 異常系デモが生成した汚染データ(git 管理外) |

## 7. トラブルシューティング(データ品質領域)

| 現象 | 原因と対処 |
|---|---|
| `make demo-quality-*` が `permission denied` | `scenarios/*.sh` に実行権限がない。`chmod +x scenarios/*.sh` を実行 |
| DB 起動待ちでタイムアウトする | 既存のコンテナ・ボリュームが壊れている可能性。`make clean-db` 後に再実行 |
| ポート 15432 が使用中というエラー | `.env` の `DEMO_DB_HOST_PORT` を空きポートに変更(コンテナ間通信には影響しない) |
| Soda が `Could not connect` を出す | DB 未起動(`make up-base`)、または `.env` の値を書き換えた場合は contract の `dataset:` 先頭セグメント(`postgres_demo`)と `ds_config.yml` の `name:` の一致を確認 |
| Soda の情報を Web 検索すると `checks for ...:` 形式(SodaCL)が出てくる | それは **v3 の旧構文**で v4 では動きません。`docs.soda.io` の **Soda v4** → Contract Language reference を参照してください |
| GX の型チェックが `VARCHAR` で失敗する | GX は長さ付きの観測値(実測: `VARCHAR(20)`)を返します。`type_` には観測値どおりの文字列を指定してください(失敗時の `observed_value` がそのまま正解です) |
| 異常系デモ(A-2 / A-4)で `make` が `Error 1` を表示する | 仕様どおりです。「違反を検知したのでエラー終了した」という成功の状態です(§4.0)。最終行に「品質違反を検知」が出ていれば成功と判断してください |
| 実行のたびに古いチェック結果が混ざらないか不安 | 各デモは毎回データを再投入してから検証します。DB を完全に初期化したい場合は `make clean-db` |

## 8. 片付け

```console
$ make down      # コンテナ停止(データ保持)
$ make clean-db  # コンテナ停止 + DB データ削除
```

実行時生成物(`quality/gx/output/`、`data/seed/csv-injected/` など)や Docker イメージ
まで含めた完全な後片付けの手順は、[README.md](../../README.md) の「後片付け」を
参照してください。
