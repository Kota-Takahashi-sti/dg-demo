#!/usr/bin/env python3
"""OpenMetadata REST API のヘルパ(起動待ち・JWT 取得・証跡保存・リネージュ手動登録)。

tools コンテナ内(catalog venv)から実行する想定。標準ライブラリのみ使用。
API のベース URL は環境変数 OM_URL(既定: http://om-server:8585)。
管理者は Basic 認証既定の admin@open-metadata.org / admin(デモ専用値)。

使い方:
    om_api.py wait                    # サーバが応答するまで待つ(最大300秒)
    om_api.py bot-jwt                 # ingestion-bot の JWT を出力(ワークフロー認証用)
    om_api.py tables                  # demo_postgres サービスのテーブル一覧(FQN と最新バージョン)
    om_api.py table <FQN>             # テーブル詳細(列・タグ・オーナー・説明)
    om_api.py versions <FQN>          # テーブルのバージョン履歴(JSON)
    om_api.py profile <FQN>           # プロファイル(行数・列統計)付きのテーブル情報
    om_api.py lineage <FQN>           # リネージュグラフ(上流・下流 2 階層)
    om_api.py register-lineage        # staging.stg_orders → mart.daily_sales を Lineage API で手動登録
    om_api.py enrich                  # 説明・オーナー・タグ・用語集を API で付与(C-1 の拡充)
    om_api.py drift-check <FQN> <列名>  # 最新版の changeDescription に列削除が記録されているか検査
                                      # (記録あり → exit 0 / なし → exit 1)
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("OM_URL", "http://om-server:8585")
ADMIN_EMAIL = os.environ.get("OM_ADMIN_EMAIL", "admin@open-metadata.org")
ADMIN_PASSWORD = os.environ.get("OM_ADMIN_PASSWORD", "admin")  # デモ専用の既定値
SERVICE = "demo_postgres"  # catalog/ingest.yaml の serviceName と合わせる


def db_name() -> str:
    return os.environ.get("DEMO_DB_NAME", "demo")


def request(method: str, path: str, body: dict | list | None = None,
            token: str | None = None, content_type: str = "application/json") -> dict:
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", content_type)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


_admin_token: str | None = None


def admin_token() -> str:
    """admin でログインしてアクセストークンを得る(パスワードは base64 必須)。"""
    global _admin_token
    if _admin_token is None:
        body = {
            "email": ADMIN_EMAIL,
            "password": base64.b64encode(ADMIN_PASSWORD.encode()).decode(),
        }
        _admin_token = request("POST", "/api/v1/users/login", body)["accessToken"]
    return _admin_token


def get(path: str, params: dict | None = None) -> dict:
    if params:
        path += "?" + urllib.parse.urlencode(params)
    return request("GET", path, token=admin_token())


def quote_fqn(fqn: str) -> str:
    return urllib.parse.quote(fqn, safe=".")


def get_table(fqn: str, fields: str = "columns,tags,owners") -> dict:
    return get(f"/api/v1/tables/name/{quote_fqn(fqn)}", {"fields": fields})


def cmd_wait() -> int:
    deadline = time.monotonic() + 300
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            request("GET", "/api/v1/system/version")
            print(f"OpenMetadata サーバは応答しています({BASE_URL}, {attempt} 回目で成功)")
            return 0
        except (urllib.error.URLError, OSError):
            time.sleep(5)
    print(f"エラー: OpenMetadata サーバ({BASE_URL})が 300 秒以内に応答しませんでした",
          file=sys.stderr)
    return 1


def cmd_bot_jwt() -> int:
    """ingestion-bot の JWT を出力する(admin ログイン → bot ユーザー → auth-mechanism)。"""
    bot = get("/api/v1/bots/name/ingestion-bot")
    bot_user_id = bot["botUser"]["id"]
    mech = get(f"/api/v1/users/auth-mechanism/{bot_user_id}")
    print(mech["config"]["JWTToken"])
    return 0


def cmd_tables() -> int:
    """demo_postgres サービスのテーブル一覧(FQN・種別・最新バージョン)。"""
    data = get("/api/v1/tables", {"limit": 100, "include": "non-deleted"})
    rows = [t for t in data.get("data", [])
            if t["fullyQualifiedName"].startswith(SERVICE + ".")]
    out = [{"fullyQualifiedName": t["fullyQualifiedName"],
            "tableType": t.get("tableType"),
            "version": t.get("version")} for t in rows]
    print(json.dumps({"count": len(out), "tables": out},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_versions(fqn: str) -> int:
    table = get_table(fqn, fields="columns")
    data = get(f"/api/v1/tables/{table['id']}/versions")
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_lineage(fqn: str) -> int:
    data = get(f"/api/v1/lineage/table/name/{quote_fqn(fqn)}",
               {"upstreamDepth": 2, "downstreamDepth": 2})
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


# mart.daily_sales は CTAS で作られたテーブルで定義 SQL が DB に残らないため、
# ビュー解析(lineage.yaml)では系譜を導出できない。Lineage API で手動登録する。
DAILY_SALES_SQL = """CREATE TABLE mart.daily_sales AS
SELECT
    order_date              AS sales_date,
    count(DISTINCT order_id) AS order_count,
    sum(amount)             AS total_amount
FROM staging.stg_orders
GROUP BY order_date
ORDER BY order_date;"""

# daily_sales 列 ← stg_orders 列 の対応(03_mart.sql の SELECT と一致させる)
DAILY_SALES_COLUMN_MAP = [
    ("sales_date", ["order_date"], None),
    ("order_count", ["order_id"], "count"),
    ("total_amount", ["amount"], "sum"),
]


def column_fqn(table: dict, name: str) -> str:
    for col in table["columns"]:
        if col["name"] == name:
            return col["fullyQualifiedName"]
    raise SystemExit(f"エラー: 列 {name} が {table['fullyQualifiedName']} に見つかりません")


def cmd_register_lineage() -> int:
    src = get_table(f"{SERVICE}.{db_name()}.staging.stg_orders")
    dst = get_table(f"{SERVICE}.{db_name()}.mart.daily_sales")
    columns_lineage = []
    for to_col, from_cols, func in DAILY_SALES_COLUMN_MAP:
        entry = {
            "fromColumns": [column_fqn(src, c) for c in from_cols],
            "toColumn": column_fqn(dst, to_col),
        }
        if func:
            entry["function"] = func
        columns_lineage.append(entry)
    edge = {
        "edge": {
            "fromEntity": {"id": src["id"], "type": "table"},
            "toEntity": {"id": dst["id"], "type": "table"},
            "lineageDetails": {
                "sqlQuery": DAILY_SALES_SQL,
                "source": "Manual",
                "columnsLineage": columns_lineage,
            },
        }
    }
    request("PUT", "/api/v1/lineage", edge, token=admin_token())
    print("Lineage API で手動登録しました:")
    print(f"  {src['fullyQualifiedName']} → {dst['fullyQualifiedName']}")
    for entry in columns_lineage:
        print(f"  列: {', '.join(entry['fromColumns'])} → {entry['toColumn']}"
              + (f"({entry['function']})" if "function" in entry else ""))
    return 0


def patch_table(table_id: str, ops: list) -> dict:
    return request("PATCH", f"/api/v1/tables/{table_id}", ops,
                   token=admin_token(), content_type="application/json-patch+json")


def exists(path: str) -> bool:
    try:
        get(path)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def cmd_enrich() -> int:
    """カタログの手入力メタデータ(説明・オーナー・タグ・用語集)を API で付与する。

    再実行しても壊れないよう、付与済みの項目はスキップする。
    """
    # 1) mart.daily_sales に説明とオーナー(admin)
    daily = get_table(f"{SERVICE}.{db_name()}.mart.daily_sales")
    if not daily.get("description"):
        patch_table(daily["id"], [{
            "op": "add", "path": "/description",
            "value": "日次売上集計テーブル。staging.stg_orders を日付で集計して作成される"
                     "(フェーズ4 のデータコントラクトの対象)。",
        }])
        print("説明を付与: mart.daily_sales")
    else:
        print("説明は付与済み: mart.daily_sales")
    if not daily.get("owners"):
        admin_user = get("/api/v1/users/name/admin")
        patch_table(daily["id"], [{
            "op": "add", "path": "/owners/0",
            "value": {"id": admin_user["id"], "type": "user"},
        }])
        print("オーナーを付与: mart.daily_sales ← admin")
    else:
        print("オーナーは付与済み: mart.daily_sales")

    # 2) raw.customers.email 列に個人データのタグ(既定分類 PersonalData.Personal)
    customers = get_table(f"{SERVICE}.{db_name()}.raw.customers")
    email_idx = next(i for i, c in enumerate(customers["columns"])
                     if c["name"] == "email")
    email_col = customers["columns"][email_idx]
    if not any(t["tagFQN"] == "PersonalData.Personal"
               for t in email_col.get("tags", [])):
        patch_table(customers["id"], [{
            "op": "add", "path": f"/columns/{email_idx}/tags/0",
            "value": {"tagFQN": "PersonalData.Personal", "source": "Classification",
                      "labelType": "Manual", "state": "Confirmed"},
        }])
        print("タグを付与: raw.customers.email ← PersonalData.Personal")
    else:
        print("タグは付与済み: raw.customers.email")

    # 3) 用語集(1 用語)を作成し、mart.daily_sales.total_amount に割り当て
    # (重複 POST はバージョンにより 409/400 が返るため、存在確認してから作成する)
    if not exists("/api/v1/glossaries/name/demo_glossary"):
        request("POST", "/api/v1/glossaries", {
            "name": "demo_glossary", "displayName": "デモ用語集",
            "description": "デモ用のビジネス用語集(フェーズ3)。",
        }, token=admin_token())
        print("用語集を作成: demo_glossary(デモ用語集)")
    else:
        print("用語集は作成済み: demo_glossary")
    if not exists("/api/v1/glossaryTerms/name/demo_glossary.uriage_kingaku"):
        request("POST", "/api/v1/glossaryTerms", {
            "glossary": "demo_glossary", "name": "uriage_kingaku",
            "displayName": "売上金額",
            "description": "税抜の受注金額合計。キャンセル済み注文(status=cancelled)は含まない。",
        }, token=admin_token())
        print("用語を作成: demo_glossary.uriage_kingaku(売上金額)")
    else:
        print("用語は作成済み: demo_glossary.uriage_kingaku")

    daily = get_table(f"{SERVICE}.{db_name()}.mart.daily_sales")
    amount_idx = next(i for i, c in enumerate(daily["columns"])
                      if c["name"] == "total_amount")
    amount_col = daily["columns"][amount_idx]
    if not any(t["tagFQN"] == "demo_glossary.uriage_kingaku"
               for t in amount_col.get("tags", [])):
        patch_table(daily["id"], [{
            "op": "add", "path": f"/columns/{amount_idx}/tags/0",
            "value": {"tagFQN": "demo_glossary.uriage_kingaku", "source": "Glossary",
                      "labelType": "Manual", "state": "Confirmed"},
        }])
        print("用語を割り当て: mart.daily_sales.total_amount ← 売上金額")
    else:
        print("用語は割り当て済み: mart.daily_sales.total_amount")
    return 0


def cmd_drift_check(fqn: str, column: str) -> int:
    """最新版の changeDescription に指定列の削除が記録されているか検査する。

    列削除は fieldsDeleted に name="columns" のエントリとして記録され、
    oldValue(JSON 文字列)に削除された列の定義一式が残る(1.13.3 実測)。
    """
    table = get_table(fqn, fields="columns")
    change = table.get("changeDescription") or {}
    deleted_columns: list[str] = []
    for field in change.get("fieldsDeleted", []):
        name = field.get("name", "")
        if name == f"columns.{column}":
            deleted_columns.append(column)
        elif name == "columns":
            try:
                old = json.loads(field.get("oldValue") or "[]")
                deleted_columns += [c.get("name") for c in old]
            except (TypeError, ValueError):
                pass
    print(f"テーブル: {table['fullyQualifiedName']}")
    print(f"現在のバージョン: {table.get('version')}"
          f"(直前: {change.get('previousVersion', '-')}。列削除は破壊的変更として"
          f"メジャーバージョンが +1.0 される)")
    print(f"変更履歴に記録された削除列: {deleted_columns or 'なし'}")
    if column in deleted_columns:
        print(f"→ 列削除がカタログに記録されています: {column}")
        return 0
    print(f"→ 列 {column} の削除は最新版の変更履歴に記録されていません", file=sys.stderr)
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "wait":
        return cmd_wait()
    if cmd == "bot-jwt":
        return cmd_bot_jwt()
    if cmd == "tables":
        return cmd_tables()
    if cmd == "table":
        print(json.dumps(get_table(args[1], fields="columns,tags,owners"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if cmd == "versions":
        return cmd_versions(args[1])
    if cmd == "profile":
        # 最新プロファイルは専用エンドポイントで取得する(fields=profile では返らない)
        data = get(f"/api/v1/tables/{quote_fqn(args[1])}/tableProfile/latest")
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if cmd == "lineage":
        return cmd_lineage(args[1])
    if cmd == "register-lineage":
        return cmd_register_lineage()
    if cmd == "enrich":
        return cmd_enrich()
    if cmd == "drift-check":
        return cmd_drift_check(args[1], args[2])
    print(f"未知のコマンド: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
