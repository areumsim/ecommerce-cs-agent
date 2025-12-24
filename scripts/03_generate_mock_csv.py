#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from typing import Dict, List

import pandas as pd


DATA_DIR = Path("data")
MOCK_DIR = DATA_DIR / "mock_csv"
PROCESSED_DIR = DATA_DIR / "processed"


def load_jsonl(path: Path) -> List[dict]:
    out: List[dict] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def merge_product_features() -> None:
    cache_path = MOCK_DIR / "products_cache.csv"
    features_path = PROCESSED_DIR / "product_features.jsonl"

    cache = read_csv(cache_path)
    features = load_jsonl(features_path)
    if not cache or not features:
        print("No merge needed (missing cache or features)")
        return

    by_id: Dict[str, dict] = {r.get("product_id", ""): r for r in cache}
    by_title: Dict[str, dict] = {r.get("title", "").lower(): r for r in cache if r.get("title")}

    updated = 0
    for feat in features:
        pid = feat.get("product_id")
        title = (feat.get("title") or "").lower()
        target = by_id.get(pid) if pid else None
        if not target and title:
            target = by_title.get(title)
        if not target:
            continue
        if feat.get("avg_rating") and not target.get("avg_rating"):
            target["avg_rating"] = str(feat["avg_rating"])
        if feat.get("stock_quantity") and not target.get("stock_quantity"):
            target["stock_quantity"] = str(feat["stock_quantity"])
        updated += 1

    if updated:
        fieldnames = list(cache[0].keys())
        write_csv(cache_path, list(by_id.values()), fieldnames)
        print(f"Updated products_cache.csv records: {updated}")
    else:
        print("No products updated")


def seed_products_cache_from_processed(limit: int | None = 200, force: bool = False) -> None:
    """Seed products_cache.csv from processed/products.parquet if cache missing or empty.

    Columns: product_id,title,brand,category,price,image_url,avg_rating,stock_quantity
    """
    cache_path = MOCK_DIR / "products_cache.csv"
    if cache_path.exists() and not force:
        rows = read_csv(cache_path)
        if rows:
            print(f"Skip seeding products_cache.csv (already has {len(rows)} rows). Use --force to overwrite.")
            return
    prod_path = PROCESSED_DIR / "products.parquet"
    if not prod_path.exists():
        print(f"Skip seeding products_cache.csv (missing {prod_path})")
        return
    df = pd.read_parquet(prod_path)
    take = df.copy() if (limit is None or limit <= 0) else df.head(limit).copy()
    take["stock_quantity"] = [random.randint(10, 200) for _ in range(len(take))]
    fieldnames = [
        "product_id","title","brand","category","price","image_url","avg_rating","stock_quantity",
    ]
    rows: List[Dict[str, str]] = []
    for _, r in take.iterrows():
        rows.append({
            "product_id": str(r.get("product_id", "")),
            "title": str(r.get("title", "")),
            "brand": str(r.get("brand", "")),
            "category": str(r.get("category", "")),
            "price": str(r.get("price", "")),
            "image_url": str(r.get("image_url", "")),
            "avg_rating": str(r.get("avg_rating", "")),
            "stock_quantity": str(r.get("stock_quantity", "")),
        })
    write_csv(cache_path, rows, fieldnames)
    print(f"Seeded products_cache.csv with {len(rows)} rows from processed/products.parquet")


def seed_orders_and_items(user_id: str = "user_001", orders: int = 3, items_per_order: int = 2) -> None:
    """Create minimal orders.csv and order_items.csv if empty, referencing products_cache.csv."""
    orders_path = MOCK_DIR / "orders.csv"
    items_path = MOCK_DIR / "order_items.csv"
    products_path = MOCK_DIR / "products_cache.csv"
    if orders_path.exists() and read_csv(orders_path):
        print("Skip seeding orders.csv (already populated)")
        return
    prows = read_csv(products_path)
    if not prows:
        print("Skip seeding orders (products_cache.csv is empty)")
        return
    # Pick distinct product_ids
    pids = [r.get("product_id", "") for r in prows if r.get("product_id")][: max(1, orders * items_per_order)]
    now = pd.Timestamp.utcnow().floor("s")
    order_rows: List[Dict[str, str]] = []
    item_rows: List[Dict[str, str]] = []
    pid_idx = 0
    for oi in range(orders):
        order_id = f"ORD-{user_id}-{int(now.timestamp())}-{oi}"
        status = random.choice(["pending", "confirmed", "shipping"]) if oi == 0 else random.choice(["confirmed","shipping","delivered"])
        order_date = (now - pd.Timedelta(days=oi+1)).isoformat()
        delivery_date = "" if status in ("pending","confirmed","shipping") else (now + pd.Timedelta(days=1)).isoformat()
        shipping_address = "Seoul, KR"
        total_amount = 0.0
        for ii in range(items_per_order):
            if pid_idx >= len(pids):
                break
            pid = pids[pid_idx]; pid_idx += 1
            price = 0.0
            for pr in prows:
                if pr.get("product_id") == pid:
                    try:
                        price = float(pr.get("price") or 0)
                    except Exception:
                        price = 0.0
                    break
            qty = random.randint(1, 2)
            item_rows.append({
                "id": f"{order_id}-{ii}",
                "order_id": order_id,
                "product_id": pid,
                "quantity": str(qty),
                "unit_price": str(price),
            })
            total_amount += price * qty
        order_rows.append({
            "order_id": order_id,
            "user_id": user_id,
            "status": status,
            "order_date": order_date,
            "delivery_date": delivery_date,
            "total_amount": f"{total_amount:.2f}",
            "shipping_address": shipping_address,
            "created_at": now.isoformat(),
        })
    write_csv(orders_path, order_rows, [
        "order_id","user_id","status","order_date","delivery_date","total_amount","shipping_address","created_at"
    ])
    write_csv(items_path, item_rows, [
        "id","order_id","product_id","quantity","unit_price"
    ])
    print(f"Seeded orders.csv ({len(order_rows)}) and order_items.csv ({len(item_rows)}) for {user_id}")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Seed/merge mock CSVs from processed data")
    p.add_argument("--limit", type=int, default=200, help="Rows to seed for products_cache (0=all)")
    p.add_argument("--no-orders", action="store_true", help="Skip creating orders/order_items")
    p.add_argument("--force", action="store_true", help="Force re-seed products_cache.csv even if it exists")
    p.add_argument("--user", type=str, default="user_001", help="User ID for seeded orders")
    p.add_argument("--orders", type=int, default=3, help="Number of orders to seed")
    p.add_argument("--items-per-order", type=int, default=2, help="Items per order")
    args = p.parse_args()

    # 1) Seed products cache from processed data if empty (0 → all rows)
    lim = None if args.limit == 0 else args.limit
    seed_products_cache_from_processed(limit=lim, force=args.force)
    # 2) Merge policy/product features if available
    merge_product_features()
    # 3) Seed minimal orders/items for quick E2E (optional)
    if not args.no_orders:
        seed_orders_and_items(user_id=args.user, orders=args.orders, items_per_order=args.items_per_order)


if __name__ == "__main__":
    main()
