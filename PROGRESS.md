# PROGRESS.md — 進捗状態(常に最新を保つこと)

## フェーズ状況

| フェーズ | 内容 | 状態 | 検収 |
|---|---|---|---|
| 0 | 調査・設計(docs/plan.md) | 完了報告済み | 合格(フェーズ1指示により承認とみなす) |
| 1 | 基盤 + データ品質(Soda Core / GX) | 完了報告済み | - |
| 2 | リネージュ(OpenLineage / Marquez) | 未着手 | - |
| 3 | カタログ(OpenMetadata) | 未着手 | - |
| 4 | コントラクト(datacontract-cli / CI) | 未着手 | - |
| 5 | ドキュメント統合・通し検証 | 未着手 | - |

状態: 未着手 / 作業中 / 完了報告済み / 差し戻し対応中
検収: - / 合格 / 差し戻し

## 現在のフェーズの詳細タスク

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

- **フェーズ1 の発注者検収待ち。検収前にフェーズ2へ進まないこと。**
- 検収後: フェーズ2(リネージュ: Marquez 0.51.1 + openlineage-python 1.52.0)。
  tools イメージに lineage venv 追加、compose に lineage profile 追加、
  pipeline/run_pipeline.py に OL イベント発行(カラム facet 含む)を実装(plan.md §5)。

## 未解決の問題・発注者への確認事項

- Marquez のバージョン: Docker Hub 最新の 0.51.1 を採用予定(GitHub Release は 0.50.0 止まり)。
  異議があればレビュー時に指摘いただきたい(plan.md §1・R3)。
- openmetadata-ingestion のライセンスは 1.6 以降 Collate Community License(OSI 外・無料利用可)。
  CLAUDE.md の「ソース公開・無料利用可能」の範囲内と判断した(plan.md R5)。要確認。
- 本環境は amd64(WSL2)のため arm64(Apple Silicon)実機検証は不可。Marquez は arm64
  イメージ未提供でエミュレーション動作になる(plan.md R2・R11)。
