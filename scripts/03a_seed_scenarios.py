#!/usr/bin/env python3
from __future__ import annotations

"""Scenario-focused seeding using real processed data.

Creates only the minimal CSVs needed for PRD Phase 1 scenarios:
- products_cache.csv: must exist (seed via 03_generate_mock_csv.py beforehand)
- orders.csv: 3 orders for one user (cancellable, shipping, delivered)
- order_items.csv: 2 items per order, linked to products_cache
- support_tickets.csv: 1 open ticket (optional)
"""

import csv
from pathlib import Path
from typing import Dict, List
import random
import pandas as pd

DATA_DIR = Path("data")
MOCK_DIR = DATA_DIR / "mock_csv"


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def ensure_products_cache(sample: int = 100) -> List[Dict[str, str]]:
    cache_path = MOCK_DIR / "products_cache.csv"
    rows = read_csv(cache_path)
    if rows:
        return rows
    # Try to seed from processed/products.parquet (real data)
    proc = Path("data/processed/products.parquet")
    if not proc.exists():
        raise SystemExit("products_cache.csv missing and processed/products.parquet not found. Run 03_generate_mock_csv.py first.")
    df = pd.read_parquet(proc)
    take = df.head(sample).copy()
    take["stock_quantity"] = [random.randint(10, 200) for _ in range(len(take))]
    fieldnames = [
        "product_id","title","brand","category","price","image_url","avg_rating","stock_quantity",
    ]
    out: List[Dict[str, str]] = []
    for _, r in take.iterrows():
        out.append({
            "product_id": str(r.get("product_id", "")),
            "title": str(r.get("title", "")),
            "brand": str(r.get("brand", "")),
            "category": str(r.get("category", "")),
            "price": str(r.get("price", "")),
            "image_url": str(r.get("image_url", "")),
            "avg_rating": str(r.get("avg_rating", "")),
            "stock_quantity": str(r.get("stock_quantity", "")),
        })
    write_csv(cache_path, out, fieldnames)
    return out


def seed_orders_items(user_id: str = "user_001") -> None:
    products = ensure_products_cache()
    if len(products) < 6:
        raise SystemExit("Need at least 6 products in products_cache.csv to seed scenarios.")
    pids = [p["product_id"] for p in products[:6]]
    now = pd.Timestamp.utcnow().floor("s")
    orders: List[Dict[str, str]] = []
    items: List[Dict[str, str]] = []

    scenarios = [
        ("ORD-CANCEL-OK", "confirmed"),     # cancellable
        ("ORD-CANCEL-NO", "shipping"),      # not cancellable
        ("ORD-DELIVERED", "delivered"),     # delivered
    ]
    pid_idx = 0
    for oid, status in scenarios:
        order_id = oid
        order_date = (now - pd.Timedelta(days=1)).isoformat()
        delivery_date = "" if status in ("pending","confirmed","shipping") else now.isoformat()
        total_amount = 0.0
        for ii in range(2):
            pid = pids[pid_idx]; pid_idx += 1
            price = 0.0
            for p in products:
                if p.get("product_id") == pid:
                    try:
                        price = float(p.get("price") or 0)
                    except Exception:
                        price = 0.0
                    break
            qty = 1
            items.append({
                "id": f"{order_id}-{ii}",
                "order_id": order_id,
                "product_id": pid,
                "quantity": str(qty),
                "unit_price": str(price),
            })
            total_amount += price * qty
        orders.append({
            "order_id": order_id,
            "user_id": user_id,
            "status": status,
            "order_date": order_date,
            "delivery_date": delivery_date,
            "total_amount": f"{total_amount:.2f}",
            "shipping_address": "Seoul, KR",
            "created_at": now.isoformat(),
        })

    write_csv(MOCK_DIR / "orders.csv", orders, [
        "order_id","user_id","status","order_date","delivery_date","total_amount","shipping_address","created_at"
    ])
    write_csv(MOCK_DIR / "order_items.csv", items, [
        "id","order_id","product_id","quantity","unit_price"
    ])
    print("Seeded scenario orders/order_items:", [o["order_id"] for o in orders])


def seed_ticket(user_id: str = "user_001", order_id: str = "ORD-DELIVERED") -> None:
    path = MOCK_DIR / "support_tickets.csv"
    rows = read_csv(path)
    ticket_id = f"TICKET-{int(pd.Timestamp.utcnow().timestamp())}"
    rows.append({
        "ticket_id": ticket_id,
        "user_id": user_id,
        "order_id": order_id,
        "issue_type": "refund",
        "description": "배송 지연으로 환불 문의",
        "status": "open",
        "priority": "normal",
        "created_at": pd.Timestamp.utcnow().isoformat(),
        "resolved_at": "",
    })
    write_csv(path, rows, [
        "ticket_id","user_id","order_id","issue_type","description","status","priority","created_at","resolved_at"
    ])
    print("Seeded support_tickets:", ticket_id)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Seed minimal scenario data using real processed sources")
    ap.add_argument("--user", type=str, default="user_001")
    ap.add_argument("--with-ticket", action="store_true")
    args = ap.parse_args()

    seed_orders_items(user_id=args.user)
    if args.with_ticket:
        seed_ticket(user_id=args.user)


if __name__ == "__main__":
    main()

