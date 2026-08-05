#!/usr/bin/env python3
"""ガイドの出力例ブロックが証跡ログと逐語一致するかを機械検証する。

使い方:
    python3 verify_verbatim.py <ガイド.md> <証跡ディレクトリ>... [--langs text,json]

規約:
    - ガイド中の ```text / ```json フェンスブロックを「出力例」とみなし検証する
      (コマンド例は ```console を使うこと。検証対象外)。
    - ラベルなしフェンス(```)を対象にするには --langs に plain を含める
      (例: --langs plain,text,json。quality.md はフェーズ1時点の規約でラベルなし)。
    - ブロック直前行の HTML コメントで挙動を制御できる(描画には現れない):
        <!-- verbatim: skip -->                     … このブロックは検証しない
        <!-- verbatim: file=verification/... -->    … このファイルとだけ照合する
    - 一致判定は (1) 完全一致 (2) 行末空白のみ無視、の順に試す。それ以外は NG。

終了コード: 0=全ブロック一致 / 1=不一致あり / 2=引数・入力エラー
"""

import argparse
import re
import sys
from pathlib import Path

MARKER_RE = re.compile(r"<!--\s*verbatim:\s*(.+?)\s*-->")
MAX_FILE_BYTES = 5 * 1024 * 1024


def read_text(path: Path):
    """テキストとして読む。バイナリ・巨大ファイルは None。改行は LF に正規化。"""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def norm(text: str) -> str:
    """行末空白のみ無視する正規化。"""
    return "\n".join(line.rstrip() for line in text.split("\n"))


def extract_blocks(guide_text: str, langs):
    """フェンスブロックを (開始行番号, 言語, 内容, マーカー) で列挙する。"""
    lines = guide_text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        m = re.match(r"^```([A-Za-z0-9_-]*)\s*$", lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1) or "plain"
        start = i
        i += 1
        body = []
        while i < len(lines) and not lines[i].startswith("```"):
            body.append(lines[i])
            i += 1
        i += 1  # 閉じフェンス
        if lang not in langs:
            continue
        # 直前の非空行が verbatim マーカーなら拾う
        marker = None
        j = start - 1
        while j >= 0 and lines[j].strip() == "":
            j -= 1
        if j >= 0:
            mm = MARKER_RE.search(lines[j])
            if mm:
                marker = mm.group(1).strip()
        blocks.append((start + 1, lang, "\n".join(body), marker))
    return blocks


def collect_evidence(dirs):
    """証跡ディレクトリ配下の全テキストファイルを読み込む。"""
    evidence = {}
    for d in dirs:
        root = Path(d)
        if not root.exists():
            print(f"エラー: 証跡ディレクトリが存在しません: {d}", file=sys.stderr)
            sys.exit(2)
        paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in paths:
            text = read_text(p)
            if text is not None:
                evidence[str(p)] = text
    return evidence


def find_match(block: str, evidence: dict):
    """(判定ラベル, ファイル名) を返す。見つからなければ (None, None)。"""
    for name, text in evidence.items():
        if block in text:
            return "完全一致", name
    nblock = norm(block)
    for name, text in evidence.items():
        if nblock in norm(text):
            return "行末空白差のみ", name
    return None, None


def diagnose(block: str, evidence: dict) -> str:
    """不一致ブロックについて、最も近い箇所と最初の差分行を報告する。"""
    block_lines = [l.rstrip() for l in block.split("\n")]
    first = next((l for l in block_lines if l.strip()), None)
    if first is None:
        return "    (空ブロック)"
    best = None  # (一致行数, ファイル, 開始行, 差分説明)
    for name, text in evidence.items():
        file_lines = [l.rstrip() for l in text.split("\n")]
        for idx, line in enumerate(file_lines):
            if line != first:
                continue
            offset = block_lines.index(first)
            matched = 0
            detail = "末尾まで一致(ブロックが証跡より長い)"
            for k, bl in enumerate(block_lines[offset:]):
                if idx + k >= len(file_lines):
                    detail = f"証跡が先に終了(ブロック {offset + k + 1} 行目以降が証跡にない)"
                    break
                if file_lines[idx + k] != bl:
                    detail = (
                        f"{name}:{idx + k + 1} で相違\n"
                        f"      ガイド: {bl!r}\n"
                        f"      証跡  : {file_lines[idx + k]!r}"
                    )
                    break
                matched += 1
            if best is None or matched > best[0]:
                best = (matched, name, idx + 1, detail)
    if best is None:
        return f"    先頭行 {first!r} がどの証跡ファイルにも見つかりません"
    return f"    最接近: {best[1]}:{best[2]}(連続一致 {best[0]} 行)\n    {best[3]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guide", help="検証対象のガイド Markdown")
    ap.add_argument("evidence", nargs="+", help="証跡ディレクトリ(複数可)")
    ap.add_argument("--langs", default="text,json", help="検証対象のフェンス言語(カンマ区切り。既定: text,json)")
    args = ap.parse_args()

    guide_path = Path(args.guide)
    guide_text = read_text(guide_path)
    if guide_text is None:
        print(f"エラー: ガイドを読めません: {args.guide}", file=sys.stderr)
        sys.exit(2)

    langs = {s.strip() for s in args.langs.split(",") if s.strip()}
    blocks = extract_blocks(guide_text, langs)
    evidence_all = collect_evidence(args.evidence)

    if not blocks:
        print(f"{args.guide}: 対象ブロック({','.join(sorted(langs))})がありません")
        sys.exit(0)

    print(f"{args.guide}: {len(blocks)} ブロックを検証(対象言語: {','.join(sorted(langs))}、証跡ファイル {len(evidence_all)} 件)")
    ok = ng = skipped = 0
    failures = []
    for n, (line, lang, body, marker) in enumerate(blocks, 1):
        snippet = next((l for l in body.split("\n") if l.strip()), "(空)")[:48]
        if marker == "skip":
            skipped += 1
            print(f"  #{n} L{line} [{lang}] {snippet} … SKIP(マーカー指定)")
            continue
        evidence = evidence_all
        if marker and marker.startswith("file="):
            target = marker[len("file="):].strip()
            evidence = {k: v for k, v in evidence_all.items() if Path(k) == Path(target) or k.endswith(target)}
            if not evidence:
                text = read_text(Path(target))
                if text is not None:
                    evidence = {target: text}
        label, fname = find_match(body, evidence)
        if label:
            ok += 1
            print(f"  #{n} L{line} [{lang}] {snippet} … OK({label})→ {fname}")
        else:
            ng += 1
            print(f"  #{n} L{line} [{lang}] {snippet} … NG")
            failures.append((n, line, diagnose(body, evidence)))

    total = ok + ng
    print(f"\n結果: {ok}/{total} VERBATIM" + (f"(SKIP {skipped})" if skipped else ""))
    for n, line, detail in failures:
        print(f"\nNG #{n}(ガイド L{line}):\n{detail}")
    sys.exit(0 if ng == 0 else 1)


if __name__ == "__main__":
    main()
