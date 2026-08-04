#!/usr/bin/env python3
"""合成 EC データ生成スクリプト(plan.md §3.1)。

- 乱数シード固定(--seed、既定 42)で毎回同じデータを生成する。
- 実在の個人情報は含まない(名前・メール・住所はすべて機械生成)。
- `--inject` で異常系デモ用の品質違反を意図的に混入できる:
    email_null     : raw.customers.email に NULL を混入
    dup_order_id   : raw.orders に order_id 重複行を混入
    bad_quantity   : raw.order_items に quantity <= 0 を混入
    bad_unit_price : raw.order_items に負の unit_price を混入
    all            : 上記すべて

使い方:
    python generate.py --out data/seed/csv                 # クリーンデータ
    python generate.py --out data/seed/csv-injected --inject all   # 汚染データ
"""

import argparse
import csv
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

VIOLATIONS = ["email_null", "dup_order_id", "bad_quantity", "bad_unit_price"]

N_CUSTOMERS = 1000
N_PRODUCTS = 200
N_ORDERS = 5000

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

FAMILY = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
          "吉田", "山田", "松本", "井上", "木村", "林", "斎藤", "清水", "山口", "森"]
GIVEN = ["翔太", "美咲", "健太", "陽菜", "大輝", "さくら", "拓海", "葵", "蓮", "結衣",
         "悠斗", "凛", "陸", "芽依", "颯太", "紬", "湊", "楓", "樹", "杏"]

CATEGORIES = ["家電", "書籍", "食品", "ファッション", "スポーツ"]
PRODUCT_NOUNS = ["ワイヤレスイヤホン", "コーヒーメーカー", "入門書", "小説", "オーガニック紅茶",
                 "クッキー詰合せ", "パーカー", "スニーカー", "ヨガマット", "ランニングウォッチ",
                 "加湿器", "モバイルバッテリー", "図鑑", "レシピ本", "スパイスセット",
                 "トートバッグ", "キャップ", "ダンベル", "テントセット", "ブレンダー"]

ORDER_STATUSES = ["completed", "shipped", "pending", "cancelled"]
STATUS_WEIGHTS = [70, 15, 10, 5]

DATE_FROM = date(2025, 7, 1)
DATE_DAYS = 365  # 2025-07-01 〜 2026-06-30


def gen_customers(rng: random.Random):
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        name = rng.choice(FAMILY) + " " + rng.choice(GIVEN)
        email = f"user{i:04d}@example.com"
        created = datetime(2024, 1, 1) + timedelta(
            days=rng.randint(0, 730), seconds=rng.randint(0, 86399))
        rows.append({
            "customer_id": i,
            "name": name,
            "email": email,
            "prefecture": rng.choice(PREFECTURES),
            "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return rows


def gen_products(rng: random.Random):
    rows = []
    for i in range(1, N_PRODUCTS + 1):
        noun = rng.choice(PRODUCT_NOUNS)
        rows.append({
            "product_id": i,
            "name": f"{noun} タイプ{i:03d}",
            "category": rng.choice(CATEGORIES),
            "price": rng.randrange(100, 50001, 10),
        })
    return rows


def gen_orders(rng: random.Random):
    rows = []
    for i in range(1, N_ORDERS + 1):
        d = DATE_FROM + timedelta(days=rng.randint(0, DATE_DAYS - 1))
        rows.append({
            "order_id": i,
            "customer_id": rng.randint(1, N_CUSTOMERS),
            "order_date": d.isoformat(),
            "status": rng.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0],
        })
    return rows


def gen_order_items(rng: random.Random, products):
    price_by_id = {p["product_id"]: p["price"] for p in products}
    rows = []
    item_id = 0
    for order_id in range(1, N_ORDERS + 1):
        for product_id in rng.sample(range(1, N_PRODUCTS + 1), k=rng.randint(1, 4)):
            item_id += 1
            rows.append({
                "order_item_id": item_id,
                "order_id": order_id,
                "product_id": product_id,
                "quantity": rng.randint(1, 5),
                "unit_price": price_by_id[product_id],
            })
    return rows


def inject(rng: random.Random, violations, customers, orders, order_items):
    """品質違反を混入する。混入内容を標準出力に記録する。"""
    if "email_null" in violations:
        targets = rng.sample(customers, k=30)
        for c in targets:
            c["email"] = ""  # COPY で NULL として投入される
        print(f"[inject] email_null: raw.customers {len(targets)} 行の email を NULL 化")

    if "dup_order_id" in violations:
        targets = rng.sample(orders, k=20)
        for o in targets:
            dup = dict(o)
            dup["order_date"] = (date.fromisoformat(o["order_date"])
                                 + timedelta(days=1)).isoformat()
            orders.append(dup)
        print(f"[inject] dup_order_id: raw.orders に重複 order_id を {len(targets)} 行追加")

    if "bad_quantity" in violations:
        targets = rng.sample(order_items, k=15)
        for it in targets:
            it["quantity"] = rng.choice([0, -1, -2])
        print(f"[inject] bad_quantity: raw.order_items {len(targets)} 行の quantity を 0 以下に変更")

    if "bad_unit_price" in violations:
        targets = rng.sample(order_items, k=10)
        for it in targets:
            it["unit_price"] = rng.choice([-500, -1200, -9800])
        print(f"[inject] bad_unit_price: raw.order_items {len(targets)} 行の unit_price を負値に変更")


def write_csv(out_dir: Path, name: str, rows):
    path = out_dir / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[write] {path} ({len(rows)} 行)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="CSV 出力先ディレクトリ")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード(既定 42)")
    parser.add_argument("--inject", default=None,
                        help="混入する違反(カンマ区切り、または all): "
                             + ",".join(VIOLATIONS))
    args = parser.parse_args()

    violations = []
    if args.inject:
        violations = VIOLATIONS if args.inject == "all" else args.inject.split(",")
        unknown = set(violations) - set(VIOLATIONS)
        if unknown:
            print(f"エラー: 未知の違反名 {sorted(unknown)}", file=sys.stderr)
            return 2

    rng = random.Random(args.seed)
    customers = gen_customers(rng)
    products = gen_products(rng)
    orders = gen_orders(rng)
    order_items = gen_order_items(rng, products)

    if violations:
        inject(rng, violations, customers, orders, order_items)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir, "customers", customers)
    write_csv(out_dir, "products", products)
    write_csv(out_dir, "orders", orders)
    write_csv(out_dir, "order_items", order_items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
