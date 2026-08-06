---
name: verify-verbatim
description: ガイド(docs/guides/*.md)の出力例ブロックが verification/ の生ログ・証跡と逐語一致するかを機械検証する(VERBATIM 検証)。ガイドの新規作成・出力例の修正・フェーズ完了報告前・検収指摘対応後に必ず実行する。
argument-hint: <ガイド.md> <証跡ディレクトリ>
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/verify_verbatim.py *)
---

# 逐語一致(VERBATIM)検証

ガイドの出力例を目視で照合してはならない。必ずスクリプトで機械検証する
(フェーズ1検収差し戻しの再発防止策)。ログ全文を読む必要はない —
スクリプトが判定と差分箇所だけを出力する。

## 実行方法

```
python3 ${CLAUDE_SKILL_DIR}/scripts/verify_verbatim.py <ガイド.md> <証跡ディレクトリ>...
```

実績のある呼び出し例(いずれも全ブロック一致を確認済み):

```
python3 ${CLAUDE_SKILL_DIR}/scripts/verify_verbatim.py docs/guides/B-lineage.md verification/phase2
python3 ${CLAUDE_SKILL_DIR}/scripts/verify_verbatim.py docs/guides/A-quality.md verification/phase1 --langs plain,text,json
```

## ガイド執筆の規約(フェーズ2以降)

- コマンド例は ```console、出力例は ```text、API レスポンス等は ```json のフェンスにする。
  スクリプトは text/json を既定で検証対象とする(console は対象外)。
- quality.md のみフェーズ1時点の規約でラベルなしフェンスに出力例がある。
  `--langs plain,text,json` を付けて検証する。
- 出力例は必ず verification/ に保存した生ログから**コピーして**貼る。手打ち・記憶からの
  再構成・整形は逐語不一致の原因になるため禁止。
- 証跡に基づかない説明用ブロック(架空の例など)を text/json フェンスで書く場合は、
  直前の行に `<!-- verbatim: skip -->` を置く(描画には現れない)。
- 特定ファイルとだけ照合したい場合は `<!-- verbatim: file=verification/phaseN/xxx.log -->`。

## 判定

- `結果: N/N VERBATIM` + exit 0 が合格。フェーズ完了報告にはこの結果を記載する。
- NG が出たら: スクリプトが示す差分箇所を確認し、**ガイド側を生ログからの逐語コピーで
  修正する**(ログ側を書き換えない)。修正後に再実行して全件一致を確認する。
- ブロック番号は追記でずれるため、ガイドに章・注記を追加した場合も再実行すること
  (フェーズ2検収対応で実際に発生したパターン)。
