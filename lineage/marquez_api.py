#!/usr/bin/env python3
"""Marquez REST API の取得ヘルパ(デモの証跡保存・起動待ちに使う。標準ライブラリのみ)。

tools コンテナ内(lineage venv)から実行する想定。API のベース URL は
環境変数 MARQUEZ_URL(既定: http://marquez-api:5000)。

使い方:
    marquez_api.py wait                # API が応答するまで待つ(最大120秒)
    marquez_api.py namespaces          # 名前空間一覧
    marquez_api.py jobs                # demo_pipeline 名前空間のジョブ一覧
    marquez_api.py runs <job名>        # 例: runs run_pipeline.build_mart
    marquez_api.py datasets            # デモ DB 名前空間のデータセット一覧
    marquez_api.py dataset <名前>      # 例: dataset demo.mart.daily_sales
    marquez_api.py lineage <名前>      # 例: lineage demo.mart.daily_sales(リネージュグラフ)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("MARQUEZ_URL", "http://marquez-api:5000")
JOB_NAMESPACE = "demo_pipeline"  # pipeline/run_pipeline.py と合わせる


def db_namespace() -> str:
    host = os.environ.get("DEMO_DB_HOST", "postgres-demo")
    port = os.environ.get("DEMO_DB_PORT", "5432")
    return f"postgres://{host}:{port}"


def get(path: str, params: dict | None = None) -> dict:
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def cmd_wait() -> int:
    deadline = time.monotonic() + 120
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            get("/api/v1/namespaces")
            print(f"Marquez API は応答しています({BASE_URL}, {attempt} 回目で成功)")
            return 0
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    print(f"エラー: Marquez API({BASE_URL})が 120 秒以内に応答しませんでした",
          file=sys.stderr)
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = args[0]
    quote = urllib.parse.quote  # namespace に :// を含むため URL エンコード必須

    if cmd == "wait":
        return cmd_wait()
    if cmd == "namespaces":
        data = get("/api/v1/namespaces")
    elif cmd == "jobs":
        data = get(f"/api/v1/namespaces/{quote(JOB_NAMESPACE, safe='')}/jobs")
    elif cmd == "runs":
        data = get(f"/api/v1/namespaces/{quote(JOB_NAMESPACE, safe='')}"
                   f"/jobs/{quote(args[1], safe='')}/runs")
    elif cmd == "datasets":
        data = get(f"/api/v1/namespaces/{quote(db_namespace(), safe='')}/datasets")
    elif cmd == "dataset":
        data = get(f"/api/v1/namespaces/{quote(db_namespace(), safe='')}"
                   f"/datasets/{quote(args[1], safe='')}")
    elif cmd == "lineage":
        data = get("/api/v1/lineage",
                   {"nodeId": f"dataset:{db_namespace()}:{args[1]}"})
    else:
        print(f"未知のコマンド: {cmd}", file=sys.stderr)
        return 2

    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
