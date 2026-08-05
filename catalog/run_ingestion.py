#!/usr/bin/env python3
"""ワークフロー YAML の ${...} を解決して metadata CLI を実行するラッパ。

使い方: run_ingestion.py <ingest|profile|classify> <ワークフローYAML>

catalog/*.yaml には DB 接続情報と JWT のプレースホルダ(${DEMO_DB_USER} 等)が
入っている。実シークレットをリポジトリに置かないため(CLAUDE.md)、このラッパが
実行時に環境変数から解決し、コンテナ内の一時ファイル(ホストへ残らない)に書き出して
`metadata <サブコマンド> -c <一時ファイル>` を実行する。

${OM_JWT}(ingestion-bot の JWT)は環境変数に無ければ om_api.py と同じ手順で
サーバから自動取得する。
"""

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import om_api  # noqa: E402


def resolve(text: str) -> str:
    env = dict(os.environ)
    if "${OM_JWT}" in text and "OM_JWT" not in env:
        bot = om_api.get("/api/v1/bots/name/ingestion-bot")
        mech = om_api.get(f"/api/v1/users/auth-mechanism/{bot['botUser']['id']}")
        env["OM_JWT"] = mech["config"]["JWTToken"]

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in env:
            raise SystemExit(f"エラー: 環境変数 {name} が未設定です({sys.argv[2]})")
        return env[name]

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", sub, text)


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("ingest", "profile", "classify"):
        print(__doc__, file=sys.stderr)
        return 2
    subcmd, workflow_path = sys.argv[1], sys.argv[2]
    with open(workflow_path, encoding="utf-8") as f:
        resolved = resolve(f.read())

    metadata_bin = os.path.join(os.path.dirname(sys.executable), "metadata")
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8") as tmp:
        tmp.write(resolved)
        tmp.flush()
        print(f"実行: metadata {subcmd} -c {workflow_path}(解決済み設定で実行)",
              flush=True)
        # metadata CLI は ANSI 色コード付きでログを出す。証跡ログ・ガイド転記の
        # 可読性のため、色コードだけを除去してそのまま流す(カラー無効化と等価)
        proc = subprocess.Popen([metadata_bin, subcmd, "-c", tmp.name],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            print(ansi.sub("", line), end="", flush=True)
        return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
