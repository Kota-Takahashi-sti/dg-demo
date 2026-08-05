#!/usr/bin/env python3
"""ODCS データコントラクト 2 版の schema セクションを比較し、破壊的変更を判定する。

datacontract-cli には破壊的変更を判定するコマンドがない(`breaking` は v0.11.1 で削除、
`changelog` はテキスト表示のみで常に exit 0)。そのため本スクリプトが契約 YAML 同士を
直接比較して判定する(設計判断は docs/build-log.md 参照)。

使い方:
    python check_breaking.py <変更前のcontract.yaml> <変更後のcontract.yaml>

判定基準(消費者視点):
    破壊的   : スキーマオブジェクト削除 / 列削除 / 型変更(logicalType・physicalType)/
               既存列の required 化(NULL を返さない前提が変わるため)
    非破壊的 : スキーマオブジェクト追加 / 列追加 / その他のメタデータ変更

exit code: 0 = 破壊的変更なし / 1 = 破壊的変更を検知 / 2 = 引数・読込エラー
"""

import sys

import yaml


def load_schema_objects(path):
    """契約 YAML を読み、{オブジェクト名: {列名: 列定義}} と生の schema リストを返す。"""
    with open(path, encoding="utf-8") as f:
        contract = yaml.safe_load(f)
    if not isinstance(contract, dict) or "schema" not in contract:
        raise ValueError(f"{path}: ODCS 契約として解釈できません(schema セクションがない)")
    objects = {}
    for obj in contract["schema"]:
        props = {p["name"]: p for p in obj.get("properties", [])}
        objects[obj["name"]] = props
    return contract, objects


def compare(old_objects, new_objects):
    """破壊的変更・非破壊的変更のリスト(表示用文字列)を返す。"""
    breaking = []
    info = []

    for obj_name, old_props in old_objects.items():
        if obj_name not in new_objects:
            breaking.append(f"スキーマオブジェクト削除: {obj_name}")
            continue
        new_props = new_objects[obj_name]
        for prop_name, old_p in old_props.items():
            if prop_name not in new_props:
                breaking.append(f"列削除: {obj_name}.{prop_name}")
                continue
            new_p = new_props[prop_name]
            for type_key in ("logicalType", "physicalType"):
                old_t, new_t = old_p.get(type_key), new_p.get(type_key)
                if old_t != new_t:
                    breaking.append(
                        f"型変更: {obj_name}.{prop_name} {type_key} '{old_t}' → '{new_t}'"
                    )
            if not old_p.get("required", False) and new_p.get("required", False):
                breaking.append(
                    f"制約強化: {obj_name}.{prop_name} が required になった"
                )
        for prop_name in new_props:
            if prop_name not in old_props:
                info.append(f"列追加(非破壊): {obj_name}.{prop_name}")

    for obj_name in new_objects:
        if obj_name not in old_objects:
            info.append(f"スキーマオブジェクト追加(非破壊): {obj_name}")

    return breaking, info


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    old_path, new_path = argv[1], argv[2]
    try:
        old_contract, old_objects = load_schema_objects(old_path)
        new_contract, new_objects = load_schema_objects(new_path)
    except (OSError, yaml.YAMLError, ValueError, KeyError, TypeError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2

    print(f"変更前: {old_path} (version: {old_contract.get('version', '不明')})")
    print(f"変更後: {new_path} (version: {new_contract.get('version', '不明')})")
    print()

    breaking, info = compare(old_objects, new_objects)

    for line in breaking:
        print(f"[BREAKING] {line}")
    for line in info:
        print(f"[OK]       {line}")

    print()
    if breaking:
        print(f"判定: 破壊的変更 {len(breaking)} 件を検知(非破壊的変更 {len(info)} 件)")
        return 1
    print(f"判定: 破壊的変更なし(非破壊的変更 {len(info)} 件)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
