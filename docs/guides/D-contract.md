# データコントラクトガイド — datacontract-cli で「生産者と消費者の合意」を管理する

このガイドでは、datacontract-cli 1.1.0 と ODCS(Open Data Contract Standard)v3.1.0 を使って、
共通サンプルデータの提供テーブル `mart.daily_sales` に**データコントラクト(データ契約)**を
定義します。契約の可視化・実データベースへの契約テスト・データ違反の検知・
**破壊的変更(列削除・型変更)を含む変更のブロック**までを、それぞれ単一の `make` コマンドで
体験します。

フェーズ1 の品質チェック(Soda Core / Great Expectations)と同じデータを扱うため、
「品質チェックの定義」と「契約」が**何がどう違うのか**(§6)を実測に基づいて比較できます。

## 1. 前提条件

- Docker Desktop または Docker Engine + Compose v2(検証環境: Docker 28.1.1 / Compose v2.35.1)
- 共通セットアップ(`make setup`。[README.md](../../README.md) の「環境構築」参照)が
  済んでいること。**この領域のための追加ビルドは不要**です(datacontract-cli は公式 Docker イメージ
  `datacontract/cli:1.1.0` をそのまま使います。初回実行時に自動で pull されます。約 277 MB)。
- D-5 では GitHub Actions ワークフローの静的検証に `rhysd/actionlint:1.7.12`(約 20 MB)も
  初回に自動 pull されます。
- 対応アーキテクチャ: amd64 / arm64(datacontract/cli 1.1.0・rhysd/actionlint 1.7.12 とも
  マルチアーチ提供をマニフェストで確認済み)。ただし本プロジェクトの実機検証は
  amd64(WSL2)のみです。
- 必要リソース: 常駐サービスはありません(デモ用 DB の postgres-demo のみ)。
  datacontract コンテナは実行時のみ起動し、すぐに破棄されます。
- ライセンス注記: datacontract-cli は MIT、ODCS 仕様は Apache-2.0(Bitol / LF AI & Data)、
  actionlint は MIT です。商用 SaaS への接続はありません(ローカル完結)。
- `demo-contract-precommit`(D-6)は **git リポジトリとして clone / 取得していること**が
  前提です(実際に `git commit` を試みてブロックされる様子を見るため)。

## 2. この領域の登場人物(初学者向けの整理)

| 役者 | 実体 | 役割 |
|---|---|---|
| ODCS v3.1.0 | 仕様(YAML の書式) | データ契約の標準フォーマット。スキーマ+品質+SLA+チームを 1 ファイルで表す |
| datacontract-cli | compose サービス `datacontract`(公式イメージ、都度実行) | 契約の検証(lint)・実 DB へのテスト(test / ci)・変換(export)・差分表示(changelog) |
| 契約 v1 | `contracts/daily_sales.yaml` | 現行の合意(status: active)。D-1〜D-3・CI の対象 |
| 契約 v2 案 | `contracts/daily_sales.v2-breaking.yaml` | 破壊的変更(列削除・型変更)を含む提案(status: proposed)。D-4〜D-6 の教材 |
| 判定スクリプト | `contracts/check_breaking.py` | 2 つの契約の schema を比較し、破壊的変更なら非0 で終了する自作スクリプト |
| CI ワークフロー | `.github/workflows/contract.yml` | PR で契約が変更されたら lint+破壊的変更判定+契約テストを実行 |

押さえておきたい構造が 3 つあります。

1. **契約は「生産者と消費者の合意」である**: フェーズ1 の Soda contract / GX スイートは
   データエンジニアが内部で使う*技術的な品質チェックの定義*でした。ODCS の契約は
   スキーマ・品質だけでなく **SLA(更新頻度・保持期間)と責任者(team)**まで含む
   *チーム間の合意文書*で、`export html` などで非エンジニアにも共有できる形になっています
   (Soda v4 も「contract」という語を使うため紛らわしいですが、このデモでは
   「Soda contract = 技術チェックの定義」「ODCS = 合意」と使い分けます)。
2. **契約テストは「提供テーブル」に対して走る**: 契約の対象は raw ではなく、消費者に
   提供する `mart.daily_sales` です。スキーマ(列の存在・型)、品質
   (nullValues / duplicateValues / rowCount / 任意 SQL)、SLA(retention)が
   `datacontract test` 1 コマンドで実 DB に対して検査されます(検査エンジンは ibis)。
3. **破壊的変更の判定コマンドは本家に存在しない**: かつての `datacontract breaking` は
   v0.11.1 で削除され、後継の `changelog` は差分の*表示*のみで常に exit 0 です
   (公式ソースで確認。docs/build-log.md 参照)。そのため本デモでは
   `contracts/check_breaking.py`(約 100 行)が契約 YAML 同士を直接比較して判定します。
   「何を breaking とみなすか」はこのスクリプトを読むとそのまま分かります
   (列削除・型変更・required 化 = 破壊的、列追加 = 非破壊)。

接続情報の扱い: 契約 YAML の `servers` セクションには接続先(ホスト・DB 名)だけを書き、
**資格情報は書きません**。ユーザー名とパスワードは環境変数
`DATACONTRACT_POSTGRES_USERNAME` / `_PASSWORD` で渡します(公式仕様。compose が
`.env` の値を注入します)。

## 3. 環境構築

```console
$ make setup             # 共通セットアップ(.env 作成 + tools イメージビルド)。済みならスキップ
$ make up-base           # デモ用 DB(postgres-demo)を起動
```

追加のビルドやサービス起動はありません。以降の `make demo-contract-*` が必要に応じて
DB 起動・データ投入・イメージ pull を自動で行います。

## 4. デモの実行手順

### 4.0 実行結果の見方(最初にお読みください)

- **正常系(D-1、D-2、D-5)は exit 0** で終わります(`echo $?` で 0)。
- **検知系(D-3、D-4、D-6)は「検知に成功したら」シナリオが exit 1** で終わります。
  make 経由ではエラー表示の後に **make 自体は exit 2** になります(make の仕様)。
  たとえば D-3 の末尾は次のようになります(`verification/phase4/terminal-demo-contract-violation.log`):

```text
(mart.daily_sales は汚染されたままです。復旧するには make seed を実行してください)
make: *** [Makefile:92: demo-contract-violation] Error 1
```

  この `make: *** ... Error 1` は「シナリオが意図どおり非0 で終了した」ことを示すもので、
  デモの失敗ではありません。逆に検知系で exit 0 になったり、
  「エラー: 〜を検知できなかった(デモ失敗)」(exit 2)が出た場合が本当の失敗です。
- 出力例の `# 実行日時:` 行、`Took N seconds` の秒数、経過時間は実行ごとに変わります。
- 各デモの生ログは `verification/phase4/` に上書き保存されます(ログ名 = make ターゲット名)。

### 4.1 D-1 正常系: 契約の可視化(export)

```console
$ make demo-contract-export
```

契約 v1 を構文検証(lint)した後、5 つの形式に変換して保存します。
出力例(`verification/phase4/demo-contract-export.log`):

```text
=== datacontract-cli 1.1.0: 契約の構文検証(lint)===
╭────────┬──────────────────────────────────────┬───────┬─────────╮
│ Result │ Check                                │ Field │ Details │
├────────┼──────────────────────────────────────┼───────┼─────────┤
│ passed │ Data contract is syntactically valid │       │         │
╰────────┴──────────────────────────────────────┴───────┴─────────╯
🟢 data contract is valid. Run 1 checks. Took 0.319554 seconds.

=== 契約を利害関係者向けの形式に変換(export)===
Written result to verification/phase4/export/daily_sales.html
[証跡] verification/phase4/export/daily_sales.html(ブラウザで開ける契約仕様書)
Written result to verification/phase4/export/daily_sales.mmd
[証跡] verification/phase4/export/daily_sales.mmd(ER 図。以下に内容を表示)
erDiagram
	"**daily_sales**" {
	sales_date🔑🔒 date
	order_count integer
	total_amount number
}

Written result to verification/phase4/export/daily_sales.md
[証跡] verification/phase4/export/daily_sales.md(Markdown 形式の契約仕様書)

=== 契約から品質チェック定義を導出(領域Aとのつながり)===
Written result to verification/phase4/export/daily_sales.sodacl.yaml
[証跡] verification/phase4/export/daily_sales.sodacl.yaml(SodaCL 形式。Soda Core 3.x 系の記法)
Written result to verification/phase4/export/daily_sales.gx.json
[証跡] verification/phase4/export/daily_sales.gx.json(Great Expectations の Expectation Suite)

datacontract 結果: 契約の可視化 5 形式を保存(exit 0)
```

**成功の目印**: 最後に「契約の可視化 5 形式を保存(exit 0)」が出ること。

生成物の見どころ(いずれも `verification/phase4/export/`):

- `daily_sales.html` — ブラウザで開くと、スキーマ・品質・SLA・チームが 1 ページに
  まとまった**契約仕様書**になります。非エンジニアとの合意形成に使える形です。
- `daily_sales.mmd` — Mermaid の ER 図(上の出力例に全文が表示されています)。
- `daily_sales.sodacl.yaml` / `daily_sales.gx.json` — **契約から品質チェック定義を導出**
  したもの。フェーズ1 で手書きした Soda / GX のチェックに相当するものが契約から
  生成できる、という「合意 → 技術チェック」の方向性を示します。
  注意: sodacl 出力は Soda Core 3.x 系の SodaCL 記法で、フェーズ1 で使った
  Soda Core 4.x の contract 記法とは別物です(そのままでは v4 で実行できません)。

### 4.2 D-2 正常系: 契約テスト(実 DB への検証)

```console
$ make demo-contract-test
```

クリーンデータを投入し、契約 v1 を `datacontract test` で実 DB に検証します。
出力例(`verification/phase4/demo-contract-test.log`。表の中身は 17 チェックの一部を抜粋):

```text
=== datacontract test(契約を実 DB へ検証: スキーマ + 品質 + SLA)===
Testing contracts/daily_sales.yaml
Written json test results to verification/phase4/test-results-clean.json
Server: local (type=postgres, host=postgres-demo, port=5432, database=demo, 
schema=mart)
╭────────┬────────────────────────────────────────────┬──────────────┬─────────╮
│ Result │ Check                                      │ Field        │ Details │
├────────┼────────────────────────────────────────────┼──────────────┼─────────┤
│ passed │ Check that model daily_sales has row_count │              │         │
│        │ > 300                                      │              │         │
```

(中略: passed の行が 17 チェック分続きます。全文は生ログを参照)

```text
│ passed │ Check that field 'total_amount' is present │ total_amount │         │
│ passed │ Check that field total_amount has physical │ total_amount │         │
│        │ type numeric                               │              │         │
│ passed │ Check that field total_amount has no       │ total_amount │         │
│        │ missing values                             │              │         │
│ passed │ Check that field total_amount has          │ total_amount │         │
│        │ missing_count = 0                          │              │         │
│ passed │ 売上合計が負の日は存在しないこと(消費者向… │ total_amount │         │
╰────────┴────────────────────────────────────────────┴──────────────┴─────────╯
🟢 data contract is valid. Run 17 checks. Took 1.82946 seconds.
[証跡] verification/phase4/test-results-clean.json(テスト結果の JSON)

datacontract 結果: 契約テスト成功(exit 0)
```

**成功の目印**: 「🟢 data contract is valid. Run 17 checks.」と
「契約テスト成功(exit 0)」。

17 チェックの内訳を知ると契約の守備範囲が分かります:

- **スキーマ**: 3 列それぞれの存在(is present)と物理型(physical type)— 契約に書いた
  `physicalType` と DB の実際の型の照合
- **品質**: sales_date の欠損ゼロ・重複ゼロ、order_count / total_amount の欠損ゼロ、
  行数 > 300、任意 SQL(負の売上合計の日が 0 件)
- **SLA**: `Retention of daily_sales.sales_date < 94608000s` — slaProperties の
  retention(3 年)が**実際に検査されている**ことに注目してください。品質ツールには
  ない観点です(この検査は「最古行の経過時間 < retention」として解釈されます。
  §8 の既知の制約も参照)。

テスト結果の機械可読な証跡は `verification/phase4/test-results-clean.json` に
保存されます(CI やダッシュボードへの連携を想定した形式)。

### 4.3 D-3 異常系: データ違反の検知

```console
$ make demo-contract-violation
```

クリーンデータを投入した後、`contracts/sql/inject_violation.sql` が提供テーブル
`mart.daily_sales` に 3 種類の契約違反(重複日付・負の売上合計・NULL の注文数)を
注入し、**D-2 とまったく同じ契約**でテストします。
出力例(`verification/phase4/demo-contract-violation.log` の抜粋):

```text
--- 契約違反を注入(contracts/sql/inject_violation.sql)---
    違反1: 重複日付 / 違反2: 負の売上合計 / 違反3: NULL の注文数
INSERT 0 1
UPDATE 1
UPDATE 1
```

```text
🔴 data contract is invalid, found the following errors:
1) sales_date Check that unique field sales_date has no duplicate values: Actual
duplicate_count(sales_date) was 1, expected = 0
2) sales_date Check that field sales_date has duplicate_count = 0: Actual 
duplicate_count(sales_date) was 1, expected = 0
3) order_count Check that field order_count has no missing values: Actual 
missing_count(order_count) was 1, expected = 0
4) order_count Check that field order_count has missing_count = 0: Actual 
missing_count(order_count) was 1, expected = 0
5) total_amount 売上合計が負の日は存在しないこと(消費者向けの業務的な保証): 
Actual custom_sql(total_amount) was 1, expected = 0

[証跡] verification/phase4/test-results-violation.json(テスト結果の JSON)

datacontract 結果: 契約違反を検知(exit 1)
(mart.daily_sales は汚染されたままです。復旧するには make seed を実行してください)
```

**成功の目印**: failed が 5 件(重複 2・欠損 2・負値 1)並び、
「契約違反を検知(exit 1)」で終わること(make 経由の最終行は `Error 1`。§4.0 参照)。

実行後、`mart.daily_sales` は汚染されたままです。**`make seed` で復旧してください**
(他領域のデモは各自でデータを再投入するため放置しても壊れませんが、
D-2 や D-5 を続けて実行する場合はそれらが自動で再投入します)。

なぜ raw ではなく mart に注入するのか: フェーズ1 の汚染データ(`--inject all`)を
そのまま使った場合に daily_sales がどうなるかを構築時に実測したところ、
負の単価や重複注文は**日次集計で薄まってしまい、提供テーブル上は契約違反として
観測できません**でした(365 行・重複なし・最小の日次売上 544,110 円 > 0)。
この実測が示す「品質チェック(raw の粒度)と契約(提供面の粒度)の守備範囲の違い」は
§6 で整理します。

### 4.4 D-4 異常系: 破壊的変更(列削除・型変更)の検知

```console
$ make demo-contract-breaking
```

契約 v1 → v2 案の差分を扱います(DB は使いません)。v2 案には
**order_count の削除(列削除)**と **total_amount の numeric → integer(型変更)**という
2 つの破壊的変更と、**cancelled_count の追加(非破壊)**が含まれています。

まず `datacontract changelog` が差分を表示します
(`verification/phase4/demo-contract-breaking.log` の抜粋):

```text
=== 2) datacontract changelog による差分表示(参考表示・常に exit 0)===
Summary
[ 1 Added ]  [ 4 Updated ]  [ 1 Removed ]
╭─────────┬───────────────────────────────────────────────╮
│ Change  │ Field                                         │
├─────────┼───────────────────────────────────────────────┤
│ Updated │ description                                   │
│ Added   │ schema.daily_sales.properties.cancelled_count │
│ Removed │ schema.daily_sales.properties.order_count     │
│ Updated │ schema.daily_sales.properties.total_amount    │
│ Updated │ status                                        │
│ Updated │ version                                       │
╰─────────┴───────────────────────────────────────────────╯
```

changelog は Added / Updated / Removed を**表示するだけで、常に exit 0** です
(破壊的かどうかの判定はしません)。判定は自作スクリプトが行います:

```text
=== 3) 自作判定スクリプトによる破壊的変更の判定 ===
変更前: contracts/daily_sales.yaml (version: 1.0.0)
変更後: contracts/daily_sales.v2-breaking.yaml (version: 2.0.0)

[BREAKING] 列削除: daily_sales.order_count
[BREAKING] 型変更: daily_sales.total_amount logicalType 'number' → 'integer'
[BREAKING] 型変更: daily_sales.total_amount physicalType 'numeric' → 'integer'
[OK]       列追加(非破壊): daily_sales.cancelled_count

判定: 破壊的変更 3 件を検知(非破壊的変更 1 件)


datacontract 結果: 破壊的変更を検知(exit 1)
```

**成功の目印**: `[BREAKING]` が 3 件・`[OK](非破壊)` が 1 件表示され、
「破壊的変更を検知(exit 1)」で終わること。

型変更が「破壊的」なのは、消費者(BI ツールや下流パイプライン)が
`numeric` 前提で読んでいる列が `integer` になると精度や型マッピングが
黙って変わるためです。列追加が「非破壊」なのは、既存の消費者は新しい列を
無視すればよいためです。この判定基準は `contracts/check_breaking.py` に
そのまま書かれています。

### 4.5 D-5 正常系: CI 構成の検証

```console
$ make demo-contract-ci
```

`.github/workflows/contract.yml`(破壊的変更を含む PR をブロックするワークフロー)を
検証します。**このデモ環境からは GitHub Actions を実行できない**ため、次の 2 段で
検証します(§5 に検証範囲の全体像をまとめています):

- **(a) 静的検証**: actionlint 1.7.12 でワークフロー YAML を検査
- **(b) ローカル等価実行**: ワークフローの各ステップと同一のコマンドをローカルで実行し、
  「正常な PR 相当 → exit 0」「破壊的変更を含む PR 相当 → 非0(= ジョブ fail = ブロック)」
  の両方を確認

出力例(`verification/phase4/demo-contract-ci.log` の抜粋):

```text
=== (a) ワークフロー YAML の静的検証(actionlint 1.7.12)===
actionlint: 問題は検出されませんでした(exit 0)
```

```text
--- job: contract-gate / step: 破壊的変更の判定(破壊的変更を含む PR 相当: v1 → v2)---
変更前: contracts/daily_sales.yaml (version: 1.0.0)
変更後: contracts/daily_sales.v2-breaking.yaml (version: 2.0.0)

[BREAKING] 列削除: daily_sales.order_count
[BREAKING] 型変更: daily_sales.total_amount logicalType 'number' → 'integer'
[BREAKING] 型変更: daily_sales.total_amount physicalType 'numeric' → 'integer'
[OK]       列追加(非破壊): daily_sales.cancelled_count

判定: 破壊的変更 3 件を検知(非破壊的変更 1 件)

→ 期待どおり非0 終了(このジョブは fail し、PR がブロックされる)
```

最後にワークフローの contract-test ジョブと同じ `datacontract ci` を実 DB へ実行し、
17 チェックの成功を確認して終わります:

```text
🟢 data contract is valid. Run 17 checks. Took 1.672234 seconds.

CI 検証結果: (a) 静的検証 OK、(b) ローカル等価実行 OK(exit 0)
```

**成功の目印**: 「actionlint: 問題は検出されませんでした」、破壊的 PR 相当での
「→ 期待どおり非0 終了」、最後の「CI 検証結果: (a) 静的検証 OK、
(b) ローカル等価実行 OK(exit 0)」。

### 4.6 D-6 異常系: pre-commit フックで破壊的変更のコミットをブロック(GitHub なしの代替)

GitHub を使わない(使えない)環境でも、同じゲートを **git の pre-commit フック**として
運用できます。フックの導入は 1 コマンドです:

```console
$ make install-contract-hook   # 解除は rm .git/hooks/pre-commit
```

導入後は、`contracts/*.yaml` の変更をコミットしようとするたびに HEAD 版と比較され、
破壊的変更ならコミットがブロックされます(意図的に進める場合は
`git commit --no-verify` で明示的に回避できます)。

この一連の動きを自動で実演するのが D-6 です(フックの導入 → v2 で上書き →
コミット試行 → ブロック → 自動復旧、まで行います。手元の契約ファイル・ステージ・
フックはデモ終了時に元へ戻ります):

```console
$ make demo-contract-precommit
```

出力例(`verification/phase4/demo-contract-precommit.log`。
`.contract-gate.XXXXXX` の部分は一時ディレクトリ名で実行ごとに変わります):

```text
--- pre-commit フックを導入(make install-contract-hook と同じ内容)---
導入先: .git/hooks/pre-commit

--- 破壊的変更(v2)で契約を上書きし、コミットを試みる ---

[contract-gate] contracts/daily_sales.yaml を HEAD 版と比較します
変更前: .contract-gate.PwNTMI/old_daily_sales.yaml (version: 1.0.0)
変更後: .contract-gate.PwNTMI/new_daily_sales.yaml (version: 2.0.0)

[BREAKING] 列削除: daily_sales.order_count
[BREAKING] 型変更: daily_sales.total_amount logicalType 'number' → 'integer'
[BREAKING] 型変更: daily_sales.total_amount physicalType 'numeric' → 'integer'
[OK]       列追加(非破壊): daily_sales.cancelled_count

判定: 破壊的変更 3 件を検知(非破壊的変更 1 件)

[contract-gate] 破壊的変更を検知したため、コミットをブロックしました。
[contract-gate] 消費者と合意済みで進める場合のみ git commit --no-verify で回避できます。

→ pre-commit フックが破壊的変更を検知し、コミットをブロックしました(検知成功)
(契約ファイル・ステージ・フックは自動で元に戻します)
```

**成功の目印**: 「破壊的変更を検知したため、コミットをブロックしました。」と
「(検知成功)」が出ること(make 経由の最終行は `Error 1`。§4.0 参照)。

このフックと make ターゲットは実際に最後まで動作確認済みです(証跡:
`verification/phase4/demo-contract-precommit.log` と
`verification/phase4/terminal-demo-contract-precommit.log`)。

## 5. CI での確認ポイントと検証範囲

### ワークフローの構成(.github/workflows/contract.yml)

トリガーは `pull_request` の `paths: contracts/**`(契約に触れた PR のみ実行)。
ジョブは 2 つです:

| ジョブ | ステップ | 落ちる条件 |
|---|---|---|
| contract-gate | pip で datacontract-cli==1.1.0 導入 → `datacontract lint` → ベースブランチ版の契約を取得 → `datacontract changelog`(参考表示)→ `contracts/check_breaking.py` | 契約の構文エラー、または**ベースブランチとの比較で破壊的変更を検知**したとき |
| contract-test | postgres:16 をサービスコンテナとして起動 → `pipeline/run_pipeline.py` でサンプルデータ構築 → `datacontract ci` | 契約テスト(スキーマ+品質+SLA)が失敗したとき |

GitHub 上での確認ポイント:

- **PR がブロックされる仕組み**: ジョブが fail した PR をマージ不可にするには、
  リポジトリ設定の branch protection(Require status checks to pass)で
  この 2 ジョブを必須に指定します(ワークフロー単体では「赤くなる」ところまでです)。
- `datacontract ci` は GitHub Actions 上で実行されたことを自動検知し、
  **PR へのアノテーションとジョブサマリ**を出力します(ローカル実行では表のみ)。
- contract-test の接続先: 契約の `servers.local` は compose 内ホスト名
  (postgres-demo)なので、CI では環境変数 `DATACONTRACT_POSTGRES_HOST=localhost` で
  上書きしています(1.0.17 以降の公式機能)。「契約は環境に依らず 1 つ、接続先は
  環境変数で差し替える」という運用パターンの例です。

### どこまで検証済みか(正直な申告)

| 検証手段 | 実施 | 結果 |
|---|---|---|
| (a) actionlint 1.7.12 による静的検証 | D-5 で毎回実行 | 指摘 0 件 |
| (b) ワークフローと同一コマンドのローカル実行 | D-5 で毎回実行 | 正常系 exit 0 / 破壊系 非0 を確認 |
| (c) act(GitHub Actions のローカル実行ツール)による実行 | 構築時に実施(2026-08-05) | 下記 3 ケースすべて期待どおり |
| (d) GitHub 上での実実行 | **実施済み**(2026-08-06、PR #2) | contract-gate / contract-test とも **success**(下記) |

**(d) GitHub 上での実実行の結果**(2026-08-06。証跡:
`verification/phase5/96-github-actions-run.log` にジョブログ全文を保存):

| ジョブ | 所要 | 結果 |
|---|---|---|
| 契約の構文検証と破壊的変更ゲート(contract-gate) | 24 秒 | success。`datacontract lint` が `🟢 data contract is valid. Run 1 checks.`、`check_breaking.py` は破壊的変更なしと判定 |
| 実データベースへの契約テスト(contract-test) | 47 秒 | success。postgres:16 サービスコンテナ + seed 投入 + `datacontract ci` で `🟢 data contract is valid. Run 17 checks.` |

ローカル(act)での検証と同じ結果が GitHub 上でも再現されました。なお実行時に
`actions/checkout@v4` と `actions/setup-python@v5` について
「Node.js 20 は非推奨(Node.js 24 で強制実行)」の warning が出ますが、
ジョブは正常に完了します(将来 v5 / v6 系への更新が必要になります)。

act v0.2.89 + ランナーイメージ catthehacker/ubuntu:act-22.04 による構築時検証の内訳
(証跡は `verification/phase4/act-*.log`。作業リポジトリを汚さないよう、
一時的な clone にローカルの bare リポジトリを origin として作り、
「破壊的変更を含む PR ブランチ」を再現して実行しました):

| ケース | ジョブ | 期待 | 実測 |
|---|---|---|---|
| 破壊的変更を含む PR | contract-gate | ジョブ fail(= ブロック) | fail(act exit 1)。check_breaking.py が 3 件検知して非0 |
| 契約に変更のない PR | contract-gate | ジョブ成功 | 成功(act exit 0) |
| 契約テスト | contract-test(postgres サービス込み) | ジョブ成功 | 成功(act exit 0)。17 チェック pass |

## 6. 長所・短所 — 品質ツール・カタログとの守備範囲の違い

同じ「データの異常を検知する」でも、3 領域は**検知する場所とタイミング**が違います。
このデモで実測できた範囲で整理します:

| 観点 | 品質ツール(Soda / GX、フェーズ1) | カタログ(OpenMetadata、フェーズ3) | 契約(ODCS + datacontract-cli、本フェーズ) |
|---|---|---|---|
| 主な守備範囲 | 製造工程(raw〜)の技術的チェック | 事後の可視化・変更履歴 | 提供テーブル(データ製品)の合意 |
| 検知タイミング | パイプライン実行時 | 取り込み(ingestion)時 | **PR 時点(実データ不要)**+テスト実行時 |
| スキーマ変更 | 定義すれば検知(実行時) | 取り込み後にバージョン履歴で検知(C-4) | **マージ前にブロックできる**(D-4/D-5/D-6) |
| 何が書けるか | チェックロジック | 説明・タグ・所有者(事後付与) | スキーマ+品質+**SLA+責任者**を 1 YAML で事前合意 |
| 実測の例 | raw の負の単価を検知(A-2) | 列削除を取り込み時に検知(C-4) | raw の汚染は**集計で薄まり検知されない**。提供面の違反(D-3)と契約差分(D-4)を検知 |

- 使い分けの目安: **上流の製造品質は品質ツール、提供面の約束(と破壊的変更の統制)は契約、
  事後の発見・調査はカタログ**。同じ違反でも「どの面で捕まえたいか」で道具が変わります。
- 相互の接続: `datacontract export sodacl / great-expectations`(D-1)で
  「合意から技術チェックを導出する」方向の連携が可能です(ただし sodacl 出力は
  Soda 3.x 記法。v4 でそのまま使えない点は §4.1 のとおり)。

### 長所(このデモで確認できた範囲)

- スキーマ・品質・SLA・責任者が 1 つの YAML に載り、`export html` で
  そのまま非エンジニアに見せられる(D-1)。
- `datacontract test / ci` 1 コマンドで実 DB への検証まで行える。SLA(retention)まで
  検査されるのは品質ツールにない観点(D-2)。
- CI 親和性が高い: `ci` コマンドは GitHub Actions を自動検知して PR アノテーションを
  出す。資格情報は環境変数で分離され、契約ファイルは環境に依らず 1 つで済む(D-5)。
- 破壊的変更の統制を「実データに触れる前(PR / コミット時点)」に置ける(D-4/D-6)。

### 短所・注意点(このデモで実際に遭遇した範囲)

- **ツールチェーンが若く、コマンド体系の変化が激しい**: `breaking` / `diff` コマンドは
  v0.11.1 で削除、テストエンジンは v1.0.0 で Soda Core から ibis に総入れ替え、
  1.1.0 では Docker イメージがシェルレス化。学習資料が最新版と食い違いやすい。
- **破壊的変更の判定は自前実装が必要**: `changelog` は表示のみ・常に exit 0
  (本デモの check_breaking.py 約 100 行で補った)。
- retention 検査の意味論が独特(「最古行の経過時間 < retention」)。
  「最低 N 年保持する」という合意をそのまま表現できるわけではない。
- 契約テストは提供テーブルの粒度で走るため、上流の違反は集計で薄まって
  見えないことがある(D-3 の実測)。品質ツールの代替にはならない。

## 7. 生成される証跡

`verification/phase4/` に保存されます:

| ファイル | 内容 | 生成元 |
|---|---|---|
| demo-contract-{export,test,violation,breaking,ci,precommit}.log | 各デモの生ログ | 各 `make demo-contract-*` |
| test-results-clean.json / test-results-violation.json | 契約テスト結果(機械可読) | D-2 / D-3 |
| changelog-v1-v2.txt | changelog の差分出力 | D-4 |
| export/daily_sales.{html,mmd,md,sodacl.yaml,gx.json} | 契約の変換結果 5 形式 | D-1 |
| terminal-demo-contract-*.log | make 経由の端末出力(Error 表示込み) | 構築時の検証記録 |
| act-contract-{gate-breaking,gate-normal,test}.log | act によるワークフロー実行 3 ケース | 構築時の検証記録(§5) |

注: `terminal-*.log` と `act-*.log` は構築時検証の記録で、本ガイドの手順からは
再生成されません(`make demo-contract-*` が上書きするのは `demo-contract-*.log` と
JSON・export・changelog の各証跡です)。

## 8. トラブルシューティング(コントラクト領域)

- **`permission denied` で verification/ に書き込めない**: datacontract コンテナは
  ホスト側ユーザー(既定 uid/gid = 1000)で動きます。`id -u` が 1000 以外の環境では
  `.env` に `DC_UID=<id -u の値>` / `DC_GID=<id -g の値>` を追記してください
  (フェーズ1〜3 から使っている `.env` にはこの変数がないため、`.env.example` の
  末尾を参考に追記します。値が既定の 1000 のままでよい場合は追記不要です)。
- **D-3 の後に手動で `datacontract test` を実行すると失敗する**: 仕様です
  (汚染が残っています)。`make seed` で復旧してください。
- **`demo-contract-precommit` が「未コミットの変更があります」で exit 2**:
  デモが `contracts/daily_sales.yaml` を一時的に上書きするための安全装置です。
  同ファイルへの変更をコミットまたは退避(`git stash`)してから再実行してください。
- **retention の検査が失敗する(Retention ... exceeds the threshold)**:
  合成データの日付は 2025-07-01〜2026-06-30 に固定されているため、
  **2028-07 以降に実行すると retention(3 年)の検査が失敗します**(既知の制約)。
  その場合は `data/seed/generate.py` の `DATE_FROM` を近い日付に変えて CSV を再生成するか、
  契約の retention 値を延ばしてください。
- **イメージの pull に失敗する**: プロキシ環境では Docker Hub
  (datacontract/cli、rhysd/actionlint)への到達性を確認してください。
- **DB に接続できない(connection refused 等)**: `make up-base` で postgres-demo が
  Healthy になっているか、`.env` の `DEMO_DB_HOST_PORT`(既定 15432)が他プロセスと
  衝突していないかを確認してください。

## 9. 片付け

```console
$ make down      # 全サービス停止(データは保持)
$ make clean-db  # データも含めて削除する場合
```

contract 領域に常駐サービスはないため、postgres-demo を止めれば終了です。
pre-commit フックを試した場合で不要になったら `rm .git/hooks/pre-commit` で解除できます
(D-6 のデモは自動で解除まで行うため、通常は残りません)。

Docker イメージまで含めた完全な後片付けの手順は、[README.md](../../README.md) の
「後片付け」を参照してください。
