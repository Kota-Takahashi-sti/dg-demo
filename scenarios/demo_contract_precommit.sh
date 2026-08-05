#!/usr/bin/env bash
# シナリオ D-6: GitHub なしの代替 — pre-commit フックによる破壊的変更ゲートの実演
#   フックを導入し、破壊的変更(v2)で契約を上書きしてコミットを試みる。
#   フックがコミットをブロックしたら「検知成功」として非0(exit 1)で終了する。
#   契約ファイル・ステージ・フックはデモ終了時に自動で元へ戻す。
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

setup_log "verification/phase4/demo-contract-precommit.log"

CONTRACT=contracts/daily_sales.yaml
HOOK_SRC=contracts/hooks/pre-commit
HOOK_DST=.git/hooks/pre-commit

# 前提確認: デモが $CONTRACT を一時的に上書きするため、未コミットの変更があれば中止する
if ! git diff --quiet HEAD -- "$CONTRACT" || ! git diff --cached --quiet -- "$CONTRACT"; then
    echo "エラー: $CONTRACT に未コミットの変更があります。コミットまたは退避してから再実行してください。" >&2
    exit 2
fi

# 既存のフックがあれば退避し、終了時に復元する
BACKUP=""
if [ -f "$HOOK_DST" ]; then
    BACKUP="$HOOK_DST.demo-backup"
    mv "$HOOK_DST" "$BACKUP"
    echo "(既存の pre-commit フックを退避しました。終了時に復元します)"
fi

restore() {
    git restore --staged "$CONTRACT" 2>/dev/null || true
    git checkout -- "$CONTRACT" 2>/dev/null || true
    rm -f "$HOOK_DST"
    if [ -n "$BACKUP" ]; then
        mv "$BACKUP" "$HOOK_DST"
    fi
}
trap restore EXIT

echo
echo "--- pre-commit フックを導入(make install-contract-hook と同じ内容)---"
install -m 755 "$HOOK_SRC" "$HOOK_DST"
echo "導入先: $HOOK_DST"

echo
echo "--- 破壊的変更(v2)で契約を上書きし、コミットを試みる ---"
cp contracts/daily_sales.v2-breaking.yaml "$CONTRACT"
git add "$CONTRACT"

echo
if git commit -m "デモ: 破壊的変更を含む契約 v2(このコミットはブロックされるはず)"; then
    echo "エラー: コミットがブロックされなかった(フックが機能していない)" >&2
    git reset --soft HEAD~1
    exit 2
fi

echo
echo "→ pre-commit フックが破壊的変更を検知し、コミットをブロックしました(検知成功)"
echo "(契約ファイル・ステージ・フックは自動で元に戻します)"
exit 1
