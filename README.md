# データガバナンス OSS デモ環境

データガバナンスの 4 領域(品質・リネージュ・カタログ・コントラクト)を、
代表的な OSS 製品でローカル PC(Docker)上に体験するデモ環境です。
対象読者は各製品を初めて触るデータエンジニアで、単なる動作確認ではなく
**各製品の設計思想の違い・長所・短所を体感できる**ことを目的としています。

| 領域 | 製品 | ガイド | デモ |
|---|---|---|---|
| A. データ品質 | Soda Core 4.19.0 / Great Expectations 1.19.1(比較) | [docs/guides/A-quality.md](docs/guides/A-quality.md) | A-1〜A-4 |
| B. データリネージュ | OpenLineage 1.52.0 + Marquez 0.51.1 | [docs/guides/B-lineage.md](docs/guides/B-lineage.md) | B-1〜B-2 |
| C. データカタログ | OpenMetadata 1.13.3 | [docs/guides/C-catalog.md](docs/guides/C-catalog.md) | C-1〜C-4 |
| D. データコントラクト | datacontract-cli 1.1.0(ODCS v3.1.0)+ GitHub Actions | [docs/guides/D-contract.md](docs/guides/D-contract.md) | D-1〜D-6 |

商用 SaaS(Soda Cloud / GX Cloud 等)には一切接続しません。
サンプルデータはすべて合成データで、実在の個人情報は含みません。

## 全体像

4 領域は「共通のサンプルデータセット(小さな EC の合成データ)+ 1 本の簡易パイプライン」を
軸に統合されています。**同じデータ・同じパイプラインを 4 つの製品がそれぞれの視点で扱う**
ことで、製品間の違いが比較しやすくなっています。

```
data/seed/csv(コミット済み合成 CSV)
   │ COPY                                     ┌─ A. 品質: Soda / GX が raw.* を検査
   ▼                                          ├─ B. リネージュ: 実行の流れを Marquez が記録
 raw.* ──SQL──> staging.stg_orders ──SQL──>   ├─ C. カタログ: OpenMetadata が全体を取り込み
                                mart.daily_sales ほか
                                              └─ D. 契約: mart.daily_sales を ODCS 契約で検証
```

Docker Compose の profile で領域ごとに起動・停止します(全製品の同時起動は不要です)。

| profile | 内容 | 常駐 |
|---|---|---|
| base | デモ用データ DB(postgres:16) | デモ実行中のみ |
| tools | ツール実行用 CLI コンテナ(Soda / GX / OpenLineage / OM ingestion を venv 分離で同梱) | 常駐しない(都度実行) |
| lineage | Marquez 一式(API / Web / 専用 DB) | 領域 B の間のみ |
| catalog | OpenMetadata 一式(サーバ / 専用 DB / Elasticsearch) | 領域 C の間のみ |
| contract | datacontract-cli(公式イメージ) | 常駐しない(都度実行) |

## ドキュメントの読み方

1. この README で環境構築と全体像を押さえる(このページの手順は全領域共通)。
2. 興味のある領域のガイド(上の表)へ進む。**各領域は独立していて、どの順でも
   実施できます**。初めての場合は A → B → C → D の順を推奨します
   (A が最も軽量で、データと パイプラインの理解が他領域の土台になるため)。
3. 終わったら本 README の「後片付け」で環境を完全に戻す。

## 前提条件(全領域共通)

- OS: Linux / macOS(Apple Silicon 可)/ Windows(WSL2)
- Docker Desktop または Docker Engine + Compose v2
  (検証環境: Docker 28.1.1 / Compose v2.35.1)
- CPU アーキテクチャ: amd64 / arm64 両対応。ただし **Marquez(領域 B)のイメージは
  amd64 のみ提供**で、Apple Silicon ではエミュレーション動作になります(ガイドに詳細)。
  また、本プロジェクトの実機検証は amd64(WSL2)のみです。
- メモリ: 領域により異なります(下表)。**領域 C(OpenMetadata)だけは Docker に
  6 GiB 以上の割り当てが必要**です。

| 領域 | 実測メモリ | 備考 |
|---|---|---|
| A. 品質 | DB 約 35 MiB + ツール実行時 約 0.5 GiB | 軽量 |
| B. リネージュ | Marquez 一式 約 0.35 GiB + DB | |
| C. カタログ | 一式 約 2.9 GiB(**割り当て 6 GiB 以上必須**・4 vCPUs 推奨) | 初回起動 3〜6 分。他領域を止めてから実施を推奨 |
| D. コントラクト | 常駐なし(DB のみ) | CLI コンテナを都度実行 |

- ネットワーク: 初回のみイメージ取得・pip インストールでインターネット接続が必要です。

## 環境構築(共通セットアップ)

### 1. リポジトリの取得

```console
$ git clone <このリポジトリの URL>
$ cd <クローンで作成したディレクトリ>
```

ZIP 取得でもほとんどのデモは動きますが、**D-6(pre-commit フック)だけは
git リポジトリであることが前提**のため、git clone を推奨します。

### 2. Docker の確認

```console
$ docker --version          # Docker 20.10 以降を推奨(検証環境: 28.1.1)
$ docker compose version    # Compose v2 であること(検証環境: v2.35.1)
```

### 3. セットアップ

```console
$ make setup
```

これは次の 2 つを行います(所要: 数分。2 回目以降の実行は安全にスキップされます)。

1. `.env` がなければ `.env.example` からコピーして作成する。
   **中身はすべてローカルデモ専用の設定値**です(実運用の値は入れないでください)。
   ポートを変更したい場合はこのファイルを編集します(下記「ポート一覧」)。
2. ツール実行用 Docker イメージ `dgd-tools:phase3` をビルドする
   (Python 3.11 上に 4 領域のツールを venv 分離でインストール)。

これで全領域のデモが実行できる状態になります。各領域のサービス起動
(`make up-lineage` 等)は各ガイドの手順に従ってください。
`make help` で全コマンドの一覧が見られます。

## デモシナリオ一覧

| # | コマンド | 内容 | 期待する結果 |
|---|---|---|---|
| A-1 | `make demo-quality-soda` | Soda Core 正常系 | exit 0 |
| A-2 | `make demo-quality-soda-ng` | Soda Core 品質違反の検知 | 非 0(検知成功) |
| A-3 | `make demo-quality-gx` | GX 正常系 | exit 0 |
| A-4 | `make demo-quality-gx-ng` | GX 品質違反の検知 | 非 0(検知成功) |
| B-1 | `make demo-lineage` | パイプライン実行 → Marquez でリネージュ確認 | exit 0 |
| B-2 | `make demo-lineage-fail` | 失敗 Run の追跡(FAILED 記録) | 非 0(検知成功) |
| C-1 | `make demo-catalog-ingest` | メタデータ取り込み → カタログ閲覧 | exit 0 |
| C-2 | `make demo-catalog-profile` | プロファイリング + サンプルデータ格納 | exit 0 |
| C-3 | `make demo-catalog-lineage` | リネージュ(SQL 解析 + API 手動登録) | exit 0 |
| C-4 | `make demo-catalog-drift` | スキーマ変更(列削除)の検知 | 非 0(検知成功) |
| D-1 | `make demo-contract-export` | 契約の可視化(HTML / mermaid ほか) | exit 0 |
| D-2 | `make demo-contract-test` | 契約テスト(スキーマ+品質+SLA を実 DB へ) | exit 0 |
| D-3 | `make demo-contract-violation` | データ違反の検知 | 非 0(検知成功) |
| D-4 | `make demo-contract-breaking` | 破壊的変更(v1→v2)の検知 | 非 0(検知成功) |
| D-5 | `make demo-contract-ci` | CI 構成の検証(静的検証 + ローカル等価実行) | exit 0 |
| D-6 | `make demo-contract-precommit` | pre-commit フックが破壊的変更をブロック | 非 0(検知成功) |

### 実行結果の見方(全デモ共通)

- **正常系は exit 0** で終わります。
- **検知系(A-2 / A-4 / B-2 / C-4 / D-3 / D-4 / D-6)は「違反・異常を検知したら
  エラー終了する」設計**です。シナリオが exit 1 で終わり、画面に make の
  `Error 1` 表示が出るのが**成功(正解)**の状態です。エラーなしで終わったら
  検知漏れ(失敗)です。
- シナリオの exit 1 を受けた **make コマンド自体の終了コードは 2** になります
  (make の仕様)。スクリプトから `$?` で判定する場合はご注意ください。
- 各デモは実行のたびに DB へクリーンデータを再投入するため、**領域間・デモ間の
  実行順序の依存はありません**(手動でデータを戻したい場合は `make seed`)。
- 各デモは実行ログを `verification/` 配下(検収証跡と同じ場所)に保存します。
  **コミット済みの証跡ログが上書きされて `git status` が汚れます**が、
  `git restore verification/` で元に戻せます。

### UI とポート一覧

ポートはすべて `.env` で変更できます(変更後はそのポートに読み替えてください)。

| 変数(.env) | 既定 | 用途 |
|---|---|---|
| `DEMO_DB_HOST_PORT` | 15432 | デモ用データ DB(PostgreSQL) |
| `MARQUEZ_WEB_HOST_PORT` | 3000 | **Marquez UI** → http://localhost:3000 |
| `MARQUEZ_API_HOST_PORT` | 5000 | Marquez API |
| `MARQUEZ_ADMIN_HOST_PORT` | 5001 | Marquez 管理ポート |
| `OM_SERVER_HOST_PORT` | 8585 | **OpenMetadata UI / API** → http://localhost:8585(admin@open-metadata.org / admin) |
| `OM_ADMIN_HOST_PORT` | 8586 | OpenMetadata 管理ポート(healthcheck 用) |

UI を持たない領域の成果物: GX の Data Docs は `quality/gx/output/data_docs/index.html`、
契約の仕様書 HTML は D-1 実行後の `verification/phase4/export/daily_sales.html` を
ブラウザで開いて確認します。

## ライセンス

### 本リポジトリのライセンス

本リポジトリの**自作物**(Makefile、`docker-compose.yml`、`pipeline/`、`quality/`、
`lineage/`、`catalog/`、`contracts/`、`scenarios/`、`data/seed/`、`docs/`、
`.github/workflows/` 等)は **Apache License 2.0** です。全文は [LICENSE](LICENSE) を
参照してください。

適用範囲には次の例外があります。

- **`verification/` 配下の証跡は第三者の生成物・著作物を含みます**。それぞれ元の
  ライセンスに従います。具体的には:
  - `verification/phase1/gx_data_docs/` — Great Expectations が生成した Data Docs
    (Apache-2.0)。同梱の **HK Grotesk フォント**(`static/fonts/HKGrotesk/`)は
    **SIL Open Font License 1.1**(ライセンス文は同ディレクトリの
    [OFL.txt](verification/phase1/gx_data_docs/static/fonts/HKGrotesk/OFL.txt))、
    同梱のロゴ画像は Great Expectations の商標です。
  - `verification/phase2/ui/`、`verification/phase3/ui/` — Marquez / OpenMetadata の
    UI スクリーンショット。各製品の画面の記録であり、商標は各権利者に帰属します。
- **`docker-compose.yml` の catalog profile** は OpenMetadata 公式リリースアセット
  (Copyright 2021 Collate、Apache-2.0)の派生物です。帰属表示と変更点は
  同ファイル冒頭のコメントに記載しています。

### 採用製品のライセンス・バージョン一覧

**本リポジトリは各製品のバイナリ・ソースコードを同梱していません。**
`pip install` / `docker pull` で各配布元から取得する構成のため、利用者は各製品の
ライセンスを配布元から直接受けることになります(下表は採用バージョンの記録です)。

バージョンはすべてピン留めしています。調査記録は [docs/plan.md](docs/plan.md) §1 と
[docs/build-log.md](docs/build-log.md) を参照してください。

| 領域 | 製品/コンポーネント | 採用バージョン | ライセンス |
|---|---|---|---|
| A. 品質 | Soda Core(`soda-postgres`) | 4.19.0 | Elastic License 2.0 ※ |
| A. 品質 | Great Expectations(`[postgresql]`) | 1.19.1 | Apache-2.0 |
| B. リネージュ | openlineage-python | 1.52.0 | Apache-2.0 |
| B. リネージュ | Marquez / Marquez Web(イメージ) | 0.51.1 | Apache-2.0 |
| C. カタログ | OpenMetadata server(イメージ) | 1.13.3 | Apache-2.0 |
| C. カタログ | OpenMetadata 同梱 PostgreSQL(イメージ) | 1.13.3 | Apache-2.0(ビルド)+ PostgreSQL License |
| C. カタログ | Elasticsearch(イメージ) | 9.3.0 | Elastic License 2.0(バイナリ配布)※ |
| C. カタログ | openmetadata-ingestion(`[postgres,pii-processor]`) | 1.13.3.0 | Collate Community License 1.0 ※ |
| D. コントラクト | datacontract-cli(イメージ / pip) | 1.1.0 | MIT |
| D. コントラクト | ODCS(仕様) | v3.1.0 | Apache-2.0(Bitol / LF AI & Data) |
| D. コントラクト | actionlint(イメージ) | 1.7.12 | MIT |
| D. コントラクト | act(ローカル CI 検証ツール) | v0.2.89 | MIT |
| D. コントラクト | act ランナーイメージ(`catthehacker/ubuntu`) | act-22.04 | MIT(同梱物は各自のライセンス) |
| D. コントラクト | actions/checkout / actions/setup-python | v4 / v5 | MIT |
| 共通 | PostgreSQL(デモ用 DB / CI サービス) | 16 | PostgreSQL License |
| 共通 | PostgreSQL(Marquez 用) | 14 | PostgreSQL License |
| 共通 | Python ベースイメージ(tools) | 3.11-slim | PSF-2.0(同梱 Debian パッケージは各自のライセンス) |
| 共通 | psycopg2-binary(pip) | 2.9.10 | LGPL with exceptions |
| 証跡 | HK Grotesk(GX Data Docs 同梱フォント) | 1.045 | SIL Open Font License 1.1 |

※ = OSI 認定外のライセンス。いずれもソース公開・無料利用可能で、本デモの
ローカル利用の範囲では制約になりません。要点:

- **Elastic License 2.0**(Soda Core / Elasticsearch): 第三者への SaaS 提供等が制限
  されます。ローカル・社内利用は無料で可能です。
- **Collate Community License 1.0**(openmetadata-ingestion 1.6 以降):
  source-available・無料利用可ですが OSI 認定外です。

## 既知の制約

| # | 制約 | 詳細 |
|---|---|---|
| 1 | arm64(Apple Silicon)の実機検証は未実施 | 検証環境が amd64(WSL2)のため。compose はマルチアーチ対応の構成 |
| 2 | Marquez のイメージは amd64 のみ提供 | Apple Silicon ではエミュレーション動作(compose で `platform` 明示済み) |
| 3 | macOS でポート 5000 が AirPlay と衝突しうる | `.env` の `MARQUEZ_API_HOST_PORT` を変更(リネージュガイド §7) |
| 4 | 検知系デモの make 終了コードは 2 | シナリオ自体は exit 1(上記「実行結果の見方」) |
| 5 | ~~GitHub Actions ワークフローの GitHub 上での実実行は未検証~~ → **解消済み**(2026-08-06) | 構築時は actionlint 静的検証 + act ローカル実行で代替検証していたが、PR #2 で GitHub 上の実実行に成功(contract-gate / contract-test とも success)。詳細はコントラクトガイド §5 |
| 6 | 契約の retention(3 年)検査は 2028-07 以降に実行すると失敗する | 合成データの日付が固定(2025-07-01 起点)のため(コントラクトガイド §8 に対処方法) |
| 7 | デモ実行でコミット済みの検収証跡が上書きされる | `git restore verification/` で復元(上記「実行結果の見方」) |
| 8 | OpenMetadata と Marquez は接続しない | OM の OpenLineage コネクタは Kafka/Kinesis 経由のみ(BETA)のため。思想の違いの教材として扱う(カタログガイド §5) |

## トラブルシューティング(全領域共通)

| 現象 | 対処 |
|---|---|
| `make demo-*` が `permission denied` | `chmod +x scenarios/*.sh` を実行(ZIP 取得時に起きやすい) |
| ポートが使用中というエラー | `.env` の該当ポート変数(上記一覧)を空きポートに変更 |
| DB 起動待ちでタイムアウト | `make clean-db` 後に再実行 |
| 検知系デモで `Error` が表示される | 仕様どおり(検知成功)。上記「実行結果の見方」参照 |

領域固有のトラブルシューティングは各ガイドの該当セクションを参照してください
(品質 §7 / リネージュ §7 / カタログ §8 / コントラクト §8)。

## 後片付け

用途に応じて 3 段階あります。

### 停止のみ(データ保持)

```console
$ make down
```

### コンテナ・ネットワーク・ボリュームの削除

```console
$ make clean-db
```

全 profile のコンテナと compose ネットワークに加え、名前付きボリューム 4 つ
(デモ用 DB / Marquez DB / OpenMetadata DB / Elasticsearch)を削除します。
蓄積したリネージュ・カタログの内容もすべて消えます。

### 完全な後片付け(生成物・イメージも削除)

`make clean-db` に加えて、以下を**この順に**実行します(生成物の削除は
tools イメージを使うため、イメージ削除より先に行ってください)。

```console
# 実行時に生成されたファイルを削除
#(Linux / WSL2 ではコンテナ(root)が生成したファイルのためホストの rm では
#  Permission denied になります。tools イメージ経由で削除します。
#  sudo rm -rf でも構いません。macOS の Docker Desktop では通常 rm -rf で消せます)
$ docker run --rm -v "$(pwd)":/workspace dgd-tools:phase3 \
    rm -rf /workspace/data/seed/csv-injected /workspace/quality/gx/output
$ rm -f .env
$ rm -f .git/hooks/pre-commit          # make install-contract-hook を使った場合のみ

# デモ実行で上書きされた検収証跡をコミット時点に戻す
$ git restore verification/

# このデモで使った Docker イメージを削除
$ docker rmi dgd-tools:phase3 \
    marquezproject/marquez:0.51.1 marquezproject/marquez-web:0.51.1 \
    docker.getcollate.io/openmetadata/server:1.13.3 \
    docker.getcollate.io/openmetadata/postgresql:1.13.3 \
    docker.elastic.co/elasticsearch/elasticsearch:9.3.0 \
    datacontract/cli:1.1.0 rhysd/actionlint:1.7.12 \
    postgres:16 postgres:14 python:3.11-slim
```

- 他のプロジェクトのコンテナ(停止中を含む)が参照しているイメージは削除に
  失敗します(`conflict: unable to remove repository reference`)。その場合は
  そのまま残して問題ありません。`postgres:16` / `postgres:14` /
  `python:3.11-slim` などの汎用イメージで起きやすい事象です。
- 削除確認は次のコマンドで行えます(docker 系は一覧に何も出なければ、
  ls は「No such file or directory」になれば完全に消えています):

```console
$ docker ps -a --filter name=claude-demo-data-governance
$ docker volume ls --filter name=claude-demo-data-governance
$ docker network ls --filter name=claude-demo-data-governance
$ ls data/seed/csv-injected quality/gx/output .env
```

## リポジトリ構成

```
├── README.md               # 本ファイル(入口)
├── LICENSE                 # Apache License 2.0(自作物に適用。適用範囲は「ライセンス」参照)
├── Makefile                # 全デモの単一コマンド入口(make help で一覧)
├── docker-compose.yml      # profiles: base / tools / lineage / catalog / contract
├── .env.example            # デモ用設定値(make setup が .env にコピー)
├── docker/tools/           # ツール実行用イメージ(4 領域の venv を分離して同梱)
├── data/seed/              # 合成データ生成スクリプト + コミット済みクリーン CSV
├── pipeline/               # 共通パイプライン(raw → staging → mart、OpenLineage 発行)
├── quality/                # 領域 A: Soda contract / GX スクリプト
├── lineage/                # 領域 B: OpenLineage 設定・Marquez API ヘルパ
├── catalog/                # 領域 C: OM ingestion ワークフロー YAML・API スクリプト
├── contracts/              # 領域 D: ODCS 契約(v1 / v2 案)・判定スクリプト・フック
├── .github/workflows/      # 領域 D: 契約 CI(contract.yml)
├── scenarios/              # 各デモの実体スクリプト
├── docs/
│   ├── plan.md             # 設計書(フェーズ0 成果物)
│   ├── build-log.md        # 構築記録(設計判断・調査・問題と解決)
│   └── guides/             # 利用者向けガイド(本 README から領域ごとに参照)
└── verification/           # 各フェーズの検収証跡(生ログ・スクリーンショット等)
```
