# PROGRESS.md — 進捗状態(常に最新を保つこと)

## フェーズ状況

| フェーズ | 内容 | 状態 | 検収 |
|---|---|---|---|
| 0 | 調査・設計(docs/plan.md) | 完了報告済み | 合格(フェーズ1指示により承認とみなす) |
| 1 | 基盤 + データ品質(Soda Core / GX) | 完了報告済み | 合格(フェーズ2指示により承認とみなす) |
| 2 | リネージュ(OpenLineage / Marquez) | 完了報告済み | 合格(フェーズ3指示により承認とみなす) |
| 3 | カタログ(OpenMetadata) | 完了報告済み | 合格(2026-08-05。main へマージ済み) |
| 4 | コントラクト(datacontract-cli / CI) | 完了報告済み | - |
| 5 | ドキュメント統合・通し検証 | 未着手 | - |

状態: 未着手 / 作業中 / 完了報告済み / 差し戻し対応中
検収: - / 合格 / 差し戻し

## 現在のフェーズの詳細タスク

フェーズ4(2026-08-05 完了報告。ブランチ: phase4):
- [x] 公式ドキュメント調査(datacontract-cli **1.1.0**(2026-08-04 リリース)を採用、
      ODCS v3.1.0。1.0.17 → 1.1.0 の差分確認・シェルレス化の影響検証。build-log.md 参照)
- [x] compose に contract profile(公式イメージ datacontract/cli:1.1.0、都度実行、
      uid は .env の DC_UID/DC_GID(既定 1000))。**tools イメージの再ビルドなし**
      (判定スクリプトはイメージ同梱 Python で実行)
- [x] contracts/(daily_sales.yaml v1 / daily_sales.v2-breaking.yaml /
      check_breaking.py(自作破壊的変更判定)/ sql/inject_violation.sql / hooks/pre-commit)
- [x] シナリオ 6 本 + Make ターゲット(D-1 export / D-2 test / D-3 violation /
      D-4 breaking / D-5 ci / D-6 precommit + install-contract-hook)
- [x] .github/workflows/contract.yml(contract-gate + contract-test の 2 ジョブ)。
      検証: (a) actionlint 1.7.12 指摘0、(b) 同一コマンドのローカル実行、
      (c) act v0.2.89 で 3 ケース実行(破壊的 PR → gate fail / 正常 PR → 成功 /
      contract-test(postgres サービス込み)→ 成功)。GitHub 上の実実行のみ未検証(既知の制約)
- [x] 全デモ動作確認(D-1/D-2/D-5 exit 0、D-3/D-4/D-6 非0)+ 品質・リネージュ回帰 exit 0。
      証跡 verification/phase4/(ログ6 + 端末ログ6 + act 3 + JSON 2 + changelog + export 5)
- [x] docs/guides/contract.md(手順・CI 確認ポイントと検証範囲・長所短所(品質/カタログとの
      守備範囲の違い、D-3 の「raw 汚染は集計で薄まる」実測を含む)・トラブルシュート。
      出力例の機械検証 **12/12 VERBATIM**)
- [x] PROGRESS.md / build-log.md 更新・完了報告

フェーズ3(2026-08-05 完了報告。ブランチ: phase3):
- [x] 公式ドキュメント調査(OM 1.13.3 リリースアセット compose、openmetadata-ingestion
      1.13.3.0 の CLI/ワークフロー YAML、Lineage/Versions API、JWT 取得。build-log.md 参照)
- [x] compose に catalog profile(om-postgresql / om-elasticsearch / om-migrate / om-server、
      内部 DB/ES はホスト非公開)+ .env.example に OM_*_HOST_PORT
- [x] tools イメージに catalog venv(openmetadata-ingestion[postgres,pii-processor]==1.13.3.0)
- [x] catalog/(ingest/lineage/profiler/classify の 4 YAML、om_api.py、run_ingestion.py)
- [x] scenarios/demo_catalog_{ingest,profile,lineage,drift}.sh + Make ターゲット 4 本
      + up-catalog / down-catalog
- [x] 全デモ動作確認(C-1〜C-3 exit 0、C-4 非0 で列削除検知)。品質・リネージュ回帰 exit 0。
      初回起動 186〜218 秒・メモリ約 2.9 GiB 実測(verification/phase3/resource-usage.log)
- [x] UI スクリーンショット 9 点(verification/phase3/ui/)
- [x] 最終 clean-db 通し実行(C-1〜C-3 exit 0 / C-4 非0。証跡 verification/phase3/)
- [x] docs/guides/catalog.md(手順・UI 確認ポイント・Marquez 比較・長所短所・
      トラブルシュート。出力例の機械検証 10/10 VERBATIM)
- [x] PROGRESS.md / build-log.md 更新・完了報告

フェーズ2(2026-08-04 完了報告):
- [x] 公式ドキュメント調査(openlineage-python 1.52.0 の event_v2/facet_v2/設定、
      Marquez 0.51.1 の compose 構成・dev config・entrypoint。参照 URL は build-log.md)
- [x] compose に lineage profile(marquez-db postgres:14 / marquez-api / marquez-web、
      0.51.1 固定・platform amd64 明示・SEARCH_ENABLED=false)+ .env.example に
      MARQUEZ_*_HOST_PORT 追加
- [x] tools イメージ(dgd-tools:phase2)に lineage venv 追加(openlineage-python==1.52.0)
- [x] pipeline/run_pipeline.py に --openlineage 実装(LineageEmitter: START/COMPLETE/FAIL、
      schema/sql/columnLineage/errorMessage facet)+ --simulate-failure
      (pipeline/sql/03_mart_broken.sql)
- [x] lineage/openlineage.yml・lineage/marquez_api.py・scenarios/demo_lineage{,_fail}.sh・
      Make ターゲット(demo-lineage / demo-lineage-fail / up-lineage / down-lineage)
- [x] 検証: clean-db 後 demo-lineage exit 0 / demo-lineage-fail 非0(FAILED 記録を API で確認)/
      品質デモ回帰 exit 0。証跡は verification/phase2/(生ログ・端末出力・API 6本・
      UI スクリーンショット 5点・リソース実測)
- [x] docs/guides/lineage.md(手順・UI 確認ポイント・長所短所・トラブルシュート。
      出力例 6 ブロックの逐語一致を機械検証 6/6 VERBATIM)
- [x] build-log.md(調査・実装・問題4件と解決・検証結果)・PROGRESS.md 更新
- [x] 検収指摘対応: 「UI の URL は .env の MARQUEZ_WEB_HOST_PORT で決まる」ことの
      確認方法をガイド §3 に新設し、§4.1/§7 に「UI が開けない」時の導線を追加
      (build-log.md「検収指摘への対応(フェーズ2)」参照)
- [x] 検収指摘対応その2: Run 履歴が蓄積される仕様(異常系実行後は FAILED が履歴に
      残り続けること・B-1 の成否は exit 0 と最新 Run で判断すること)を §4.1/§7 に明記
      (同「その2」参照)

フェーズ1(2026-08-04 完了報告):
- [x] 公式ドキュメント調査(Soda v4 contract 構文 / CLI、GX 1.x API。参照 URL は build-log.md)
- [x] 基盤: .env.example / docker-compose.yml(profiles: base, tools)/ docker/tools(Python 3.11
      + quality venv: soda-postgres 4.19.0, great_expectations 1.19.1)/ Makefile / scenarios/
- [x] 合成データ生成 data/seed/generate.py(シード固定、--inject email_null,dup_order_id,
      bad_quantity,bad_unit_price,all)+ クリーン CSV コミット(data/seed/csv/)
- [x] パイプライン pipeline/run_pipeline.py(seed → build_staging → build_mart、OL 発行なし版)
- [x] Soda contract 3 ファイル(quality/soda/contracts/)+ ds_config.yml(${env.*} 注入)
- [x] GX quality/gx/run_checks.py(同一4チェック + Data Docs 出力)
- [x] make demo-quality-soda / -ng / demo-quality-gx / -ng の4本を実測
      (正常系 exit 0、異常系 非0。生ログ verification/phase1/ 4本 + gx_data_docs/)
- [x] docs/guides/quality.md(前提・環境構築・手順・比較表・長所短所・トラブルシュート)
- [x] build-log.md(調査記録・遭遇した問題3件と解決・実測仕様)・PROGRESS.md 更新
- [x] 検収指摘対応: §4.3/§4.4 の GX 出力例を生ログからの逐語転記に修正し、
      ガイド内全出力例のログ一致を機械検証(build-log.md「検収指摘への対応」参照)
- [x] 検収指摘対応その2: 「非 0 で終了」表現を廃し、§4.0(成否の判定方法)新設+
      各シナリオに実測の「成功の目印」を掲載。端末出力全体の証跡
      verification/phase1/terminal-demo-quality-*.log 4 本を追加(同「その2」参照)

フェーズ0(2026-08-04 完了報告):
- [x] 環境検証(docker 28.1.1 / compose v2.35.1 / レジストリ接続 / 採用9イメージの pull 成功)
      → 生ログ verification/phase0/01〜04
- [x] バージョン調査(4領域、公式一次情報を Web 確認、調査日 2026-08-04)→ build-log.md に詳細
- [x] docs/plan.md 作成(採用バージョン/リポジトリ構成/アーキテクチャ/デモシナリオ/
      フェーズ計画/リスク。発注者の比較軸5点を反映)
- [x] PROGRESS.md / build-log.md 更新

## 次にやること(セッション再開時はここから)

- **フェーズ4 完了報告済み(2026-08-05。ブランチ: phase4)。検収待ち。**
- 検収合格後: phase4 を main へマージ → フェーズ5(ドキュメント統合・通し検証)の指示待ち。
- 差し戻しの場合: 指摘対応後に demo 再実行 + verify-verbatim 再実行
  (build-log.md「フェーズ4 検証結果」参照)。

