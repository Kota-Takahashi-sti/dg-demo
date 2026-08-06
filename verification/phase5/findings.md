# フェーズ5 通し検収 findings(2026-08-06)

検証方法: README.md と docs/guides/*.md に書かれた手順のみで、まっさら状態(事前クリーンアップ済み)から
環境構築 → 全 16 デモ(A-1〜A-4 / B-1〜B-2 / C-1〜C-4 / D-1〜D-6)を README 推奨順(A→B→C→D)に実行。
UI はブラウザの代わりに curl による疎通・API レスポンス確認で代替(12-marquez-ui-check.log / 21-om-ui-check.log)。

## 結果概要

- 全 16 デモ: 期待どおりの exit code・成功の目印を確認(正常系 9 本 = exit 0、検知系 7 本 = make exit 2)。
- **ガイドに書かれていない操作が必要になった箇所: なし**(発生した問題はすべてガイド記載のトラブルシューティングで解決)。
- 機械逐語検証(verify_verbatim.py): quality 8/8、lineage 6/6、contract 12/12、**catalog 7/10(NG 3)**。

## 指摘(ガイド記述と実測の食い違い)

### 指摘1 [中] catalog.md の出力例 3 ブロックが機械逐語検証 NG(40-verify-verbatim.log)

- 現象: verify_verbatim.py で catalog.md が 7/10。NG は
  (1) §4.1 L137 C-1 Workflow Summary(タイムスタンプ `2026-08-05 07:27:12` / `finished in time: 4s 990.188ms`)、
  (2) §4.2 L207 Profiler Summary(同様)、
  (3) §4.2 L234 profile JSON(`"timestamp": 1785917690731` が実測 `1785990350691`)。
  いずれも実行ごとに変わる値がブロック内に含まれ、かつ照合先の証跡
  (verification/phase3/demo-catalog-*.log、api-profile-customers.json)は**デモ実行のたびに再生成される**ため、
  初見の読者が再現実行すると逐語一致しない。
- ガイドに欠けている情報/規約違反: 本文には「タイムスタンプ・所要時間は実行ごとに変わります」の注記が
  あるものの、本リポジトリの verbatim 規約(可変ブロックには `<!-- verbatim: skip -->` 等のマーカー)が
  適用されていない。contract.md は同種の可変ブロックを「再生成されない terminal-*.log」と照合させて
  規約を満たしており、catalog.md だけ不整合。
- 修正案: 該当 3 ブロックに `<!-- verbatim: skip -->` を付す、または可変行(タイムスタンプ・所要時間・
  timestamp フィールド)を除いた抜粋に差し替える。

### 指摘2 [軽微] quality.md の出力例中の Makefile 行番号が現行と乖離

- 現象: §4.2 出力例 `make: *** [Makefile:38: demo-quality-soda-ng] Error 1` → 実測 `Makefile:56`。
  §4.4 出力例 `Makefile:44` → 実測 `Makefile:62`。
  (機械検証では phase1 にコミット済みの旧 terminal ログと一致したため 8/8 となるが、
  新規再現時の端末出力とは一致しない。)
- ガイドに欠けている情報: §4.2 には「数字は今後の変更で変わることがあります」の注記があるが、
  §4.4 には同注記がない。また出力例自体が現行 Makefile と 2 世代分ずれている。
- 修正案: 出力例を現行の行番号に更新する(あわせて §4.4 にも変動注記を追加するか、
  行番号部分をプレースホルダ表記に統一する)。
  参考: lineage.md §4.2(58→実測 69)は注記あり、contract.md §4.0(92)は実測と一致していた。

### 指摘3 [軽微] lineage.md §4.1「カラムレベルリネージュの確認(API)」の自己確認コマンドが facet を返さない

- 現象: 同節が提示する
  `docker compose --profile tools run --rm -T tools /opt/venv/lineage/bin/python lineage/marquez_api.py lineage demo.mart.daily_sales`
  を実行したところ(13-marquez-api-lineage.log、1017 行)、出力はリネージュグラフのみで
  `columnLineage` / `inputFields` は 0 件。節の主題である facet はこのコマンドでは確認できない。
  facet が入るのは `marquez_api.py dataset demo.mart.daily_sales`(B-1 が
  api-dataset-daily-sales.json として保存するもの。本検証でも facet の内容がガイド抜粋と完全一致)。
- ガイドに欠けている情報: 「自分で API を叩いて確認することもできます」の対象が
  facet ではなくグラフである旨、または facet を見るための正しいサブコマンド。
- 修正案: コマンドを `... marquez_api.py dataset demo.mart.daily_sales` に変更する
  (もしくは「このコマンドで得られるのはグラフで、facet は dataset 照会で確認」と明記)。

## ガイド外操作の有無

- **なし**。発生した事象と対応はいずれもガイド記載の範囲内:
  - B-1 初回実行がホスト側ポート 3000 の競合で失敗(占有者は本プロジェクト外のコンテナ
    obs-lab-control-plane)。lineage.md §7「ポート競合で起動に失敗する」の記載どおり
    `.env` に MARQUEZ_API_HOST_PORT=15000 / MARQUEZ_ADMIN_HOST_PORT=15001 /
    MARQUEZ_WEB_HOST_PORT=13000 を追記し `make down-lineage && make up-lineage` で解決、
    B-1 再実行で成功(11-port-conflict-fix-up-lineage.log)。デモ出力・B-2 出力の URL も
    13000 に追随して表示された(ガイド §3 の「実際の URL を表示します」のとおり)。
  - D-3 後の `make seed`、C-4 後の `make seed`+`make demo-catalog-ingest` はガイド記載の復旧手順。

## セッション固有の制約(ガイドの不備ではない)

- 本検収セッションの権限設定により `.env` の読み取り(grep/cat/ls とも)が拒否されるため、
  lineage.md §3 の `grep MARQUEZ_WEB_HOST_PORT .env ...` と catalog.md §3 の
  `grep OM_SERVER_HOST_PORT .env` は実行できなかった(実行を試みて拒否を確認)。
  既定ポート(OM 8585)/追記した値(Marquez 13000)で続行した。ガイドの確認手順自体の不備ではない。
- UI 確認はブラウザの代わりに curl で代替した(Marquez UI :13000 → 200、OM UI :8585 → 200・
  version API 1.13.3)。スクリーンショット記載の画面要素(ジョブ一覧の色など)は未確認。

## 事前状態の申告との相違(検収環境側のノート。ガイドの不備ではない)

- クリーンアップ済みとされていたが、以下が残存していた:
  - `data/seed/csv-injected/`(root 所有・8/5 生成)と `quality/gx/output/`(root 所有)
    → 各デモが上書き再生成するため影響なし。
  - `.git/hooks/pre-commit`(本日 10:51 作成。セッション開始前)
    → D-6 は「既存の pre-commit フックを退避しました。終了時に復元します」と表示して
    退避・復元まで行った(仕様どおり)。結果としてフックは検証前と同じ状態で残っている。

## 所要時間(実測)

- `make setup`: 275 秒(ガイド「数分」と整合)
- `make up-catalog`: 297 秒(イメージ pull 込み。ガイド「3〜6 分」と整合)
- 通し検証全体(セットアップ開始〜D-6 完了、確認作業込み): 約 137 分

## 証跡一覧(verification/phase5/)

- 01-docker-version.log / 02-make-setup.log
- terminal-demo-quality-{soda,soda-ng,gx,gx-ng}.log
- terminal-demo-lineage.log(初回失敗分は 11-port-conflict-fix-up-lineage.log で復旧)/ terminal-demo-lineage-fail.log
- 12-marquez-ui-check.log / 13-marquez-api-lineage.log
- 19-down-lineage.log / 20-up-catalog.log / 21-om-ui-check.log
- terminal-demo-catalog-{ingest,profile,lineage,drift}.log / 22-restore-after-drift.log / 29-down-catalog.log
- 30-up-base.log / terminal-demo-contract-{export,test,violation,breaking,ci,precommit}.log / 31-seed-after-violation.log
- 40-verify-verbatim.log(機械逐語検証の全文)
