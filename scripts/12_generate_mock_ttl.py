#!/usr/bin/env python3
"""
CSV mock 데이터를 RDF/TTL 형식으로 변환하는 스크립트.

사용법:
    python scripts/12_generate_mock_ttl.py
    python scripts/12_generate_mock_ttl.py --limit 50  # 고객/상품 각 50개만
"""

import argparse
import csv
import random
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime


def escape_ttl_string(s: str) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def generate_customers_ttl(users_csv: Path, limit: int = 0) -> str:
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '',
    ]
    
    with open(users_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if limit > 0 and count >= limit:
                break
            
            user_id = row["user_id"]
            name = escape_ttl_string(row["name"])
            email = escape_ttl_string(row["email"])
            phone = escape_ttl_string(row.get("phone", ""))
            address = escape_ttl_string(row.get("address", ""))
            level = row.get("membership_level", "bronze")
            created = row.get("created_at", "")
            
            lines.append(f'ecom:customer_{user_id} a ecom:Customer ;')
            lines.append(f'    ecom:customerId "{user_id}" ;')
            lines.append(f'    ecom:name "{name}" ;')
            lines.append(f'    ecom:email "{email}" ;')
            if phone:
                lines.append(f'    ecom:phone "{phone}" ;')
            if address:
                lines.append(f'    ecom:address "{address}" ;')
            lines.append(f'    ecom:membershipLevel "{level}" ;')
            if created:
                lines.append(f'    ecom:createdAt "{created}"^^xsd:dateTime ;')
            
            lines[-1] = lines[-1].rstrip(' ;') + ' .'
            lines.append('')
            count += 1
    
    return '\n'.join(lines)


def generate_products_ttl(products_csv: Path, limit: int = 0) -> str:
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
        '',
    ]
    
    category_map = {
        "Electronics": "ecom:Electronics",
        "General": "ecom:General",
    }
    
    with open(products_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if limit > 0 and count >= limit:
                break
            
            product_id = row["product_id"]
            title = escape_ttl_string(row["title"])
            brand = escape_ttl_string(row.get("brand", ""))
            category = row.get("category", "General")
            price = row.get("price", "0")
            rating = row.get("average_rating", "0")
            rating_num = row.get("rating_number", "0")
            stock = row.get("stock_status", "in_stock")
            
            cat_uri = category_map.get(category, "ecom:General")
            
            safe_id = product_id.replace("-", "_").replace(" ", "_")
            
            lines.append(f'ecom:product_{safe_id} a ecom:Product ;')
            lines.append(f'    ecom:productId "{product_id}" ;')
            lines.append(f'    ecom:title "{title}" ;')
            if brand:
                lines.append(f'    ecom:brand "{brand}" ;')
            lines.append(f'    ecom:inCategory {cat_uri} ;')
            lines.append(f'    ecom:price {price} ;')
            lines.append(f'    ecom:averageRating {rating} ;')
            lines.append(f'    ecom:ratingNumber {rating_num} ;')
            lines.append(f'    ecom:stockStatus "{stock}" ;')
            
            lines[-1] = lines[-1].rstrip(' ;') + ' .'
            lines.append('')
            count += 1
    
    return '\n'.join(lines)


def generate_orders_ttl(orders_csv: Path, order_items_csv: Path, limit: int = 0) -> str:
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '',
    ]
    
    order_items: Dict[str, List[Dict]] = {}
    with open(order_items_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = row["order_id"]
            if oid not in order_items:
                order_items[oid] = []
            order_items[oid].append(row)
    
    with open(orders_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if limit > 0 and count >= limit:
                break
            
            order_id = row["order_id"]
            user_id = row["user_id"]
            status = row["status"]
            order_date = row["order_date"]
            delivery_date = row.get("delivery_date", "")
            total = row["total_amount"]
            address = escape_ttl_string(row.get("shipping_address", ""))
            
            safe_order_id = order_id.replace("-", "_").replace(" ", "_")
            
            lines.append(f'ecom:order_{safe_order_id} a ecom:Order ;')
            lines.append(f'    ecom:orderId "{order_id}" ;')
            lines.append(f'    ecom:status "{status}" ;')
            lines.append(f'    ecom:orderDate "{order_date}"^^xsd:dateTime ;')
            if delivery_date:
                lines.append(f'    ecom:deliveryDate "{delivery_date}"^^xsd:dateTime ;')
            lines.append(f'    ecom:totalAmount {total} ;')
            if address:
                lines.append(f'    ecom:shippingAddress "{address}" ;')
            
            lines[-1] = lines[-1].rstrip(' ;') + ' .'
            lines.append('')
            
            lines.append(f'ecom:customer_{user_id} ecom:placedOrder ecom:order_{safe_order_id} .')
            lines.append('')
            
            if order_id in order_items:
                for idx, item in enumerate(order_items[order_id]):
                    item_id = f"{safe_order_id}_item_{idx}"
                    product_id = item["product_id"]
                    safe_product_id = product_id.replace("-", "_").replace(" ", "_")
                    qty = item["quantity"]
                    unit_price = item["unit_price"]
                    
                    lines.append(f'ecom:orderitem_{item_id} a ecom:OrderItem ;')
                    lines.append(f'    ecom:quantity {qty} ;')
                    lines.append(f'    ecom:unitPrice {unit_price} ;')
                    lines.append(f'    ecom:hasProduct ecom:product_{safe_product_id} .')
                    lines.append('')
                    
                    lines.append(f'ecom:order_{safe_order_id} ecom:containsItem ecom:orderitem_{item_id} .')
                    lines.append('')
                    
                    lines.append(f'ecom:customer_{user_id} ecom:purchased ecom:product_{safe_product_id} .')
                    lines.append('')
            
            count += 1
    
    return '\n'.join(lines)


def generate_tickets_ttl(tickets_csv: Path, limit: int = 0) -> str:
    """티켓 데이터를 TTL로 변환"""
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '',
    ]
    
    with open(tickets_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if limit > 0 and count >= limit:
                break
            
            ticket_id = row["ticket_id"]
            user_id = row["user_id"]
            order_id = row.get("order_id", "")
            issue_type = row.get("issue_type", "other")
            description = escape_ttl_string(row.get("description", ""))
            status = row.get("status", "open")
            priority = row.get("priority", "normal")
            created_at = row.get("created_at", "")
            resolved_at = row.get("resolved_at", "")
            
            safe_ticket_id = ticket_id.replace("-", "_").replace(" ", "_")
            safe_order_id = order_id.replace("-", "_").replace(" ", "_") if order_id else ""
            
            lines.append(f'ecom:ticket_{safe_ticket_id} a ecom:Ticket ;')
            lines.append(f'    ecom:ticketId "{ticket_id}" ;')
            lines.append(f'    ecom:issueType "{issue_type}" ;')
            if description:
                lines.append(f'    ecom:description "{description}" ;')
            lines.append(f'    ecom:status "{status}" ;')
            lines.append(f'    ecom:priority "{priority}" ;')
            if created_at:
                lines.append(f'    ecom:createdAt "{created_at}"^^xsd:dateTime ;')
            if resolved_at:
                lines.append(f'    ecom:resolvedAt "{resolved_at}"^^xsd:dateTime ;')
            
            lines[-1] = lines[-1].rstrip(' ;') + ' .'
            lines.append('')
            
            # Customer -> Ticket 관계
            lines.append(f'ecom:customer_{user_id} ecom:hasTicket ecom:ticket_{safe_ticket_id} .')
            lines.append('')
            
            # Ticket -> Order 관계 (order_id가 있는 경우)
            if order_id:
                lines.append(f'ecom:ticket_{safe_ticket_id} ecom:relatedToOrder ecom:order_{safe_order_id} .')
                lines.append('')
            
            count += 1
    
    return '\n'.join(lines)


def generate_similar_products_ttl(products_csv: Path, similarity_count: int = 3) -> str:
    """상품 간 유사도 관계 생성 (같은 카테고리 + 브랜드 기반)"""
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '',
    ]
    
    products_by_category: Dict[str, List[str]] = {}
    products_by_brand: Dict[str, List[str]] = {}
    
    with open(products_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row["product_id"]
            category = row.get("category", "General")
            brand = row.get("brand", "")
            
            safe_id = product_id.replace("-", "_").replace(" ", "_")
            
            if category not in products_by_category:
                products_by_category[category] = []
            products_by_category[category].append(safe_id)
            
            if brand:
                if brand not in products_by_brand:
                    products_by_brand[brand] = []
                products_by_brand[brand].append(safe_id)
    
    added_pairs: Set[tuple] = set()
    
    for category, products in products_by_category.items():
        if len(products) < 2:
            continue
        
        for product in products:
            candidates = [p for p in products if p != product]
            if not candidates:
                continue
            
            similar = random.sample(candidates, min(similarity_count, len(candidates)))
            for sim_product in similar:
                pair = tuple(sorted([product, sim_product]))
                if pair not in added_pairs:
                    added_pairs.add(pair)
                    lines.append(f'ecom:product_{product} ecom:similarTo ecom:product_{sim_product} .')
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate TTL files from CSV mock data")
    parser.add_argument("--limit", type=int, default=0, help="Limit records (0=all)")
    parser.add_argument("--csv-dir", default="data/mock_csv", help="CSV directory")
    parser.add_argument("--output-dir", default="ontology/instances", help="Output directory")
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    csv_dir = project_root / args.csv_dir
    output_dir = project_root / args.output_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Mock CSV to TTL Converter")
    print(f"{'='*60}")
    print(f"CSV Dir: {csv_dir}")
    print(f"Output Dir: {output_dir}")
    print(f"Limit: {args.limit if args.limit > 0 else 'unlimited'}")
    print(f"{'='*60}\n")
    
    users_csv = csv_dir / "users.csv"
    if users_csv.exists():
        print("[1/4] Generating customers.ttl...")
        customers_ttl = generate_customers_ttl(users_csv, args.limit)
        (output_dir / "customers.ttl").write_text(customers_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'customers.ttl'}")
    else:
        print(f"[SKIP] users.csv not found")
    
    products_csv = csv_dir / "products_cache.csv"
    if products_csv.exists():
        print("[2/4] Generating products.ttl...")
        products_ttl = generate_products_ttl(products_csv, args.limit)
        (output_dir / "products.ttl").write_text(products_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'products.ttl'}")
        
        print("[3/4] Generating similarities.ttl...")
        similarities_ttl = generate_similar_products_ttl(products_csv)
        (output_dir / "similarities.ttl").write_text(similarities_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'similarities.ttl'}")
    else:
        print(f"[SKIP] products_cache.csv not found")
    
    orders_csv = csv_dir / "orders.csv"
    order_items_csv = csv_dir / "order_items.csv"
    if orders_csv.exists() and order_items_csv.exists():
        print("[4/5] Generating orders.ttl...")
        orders_ttl = generate_orders_ttl(orders_csv, order_items_csv, args.limit)
        (output_dir / "orders.ttl").write_text(orders_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'orders.ttl'}")
    else:
        print(f"[SKIP] orders.csv or order_items.csv not found")
    
    tickets_csv = csv_dir / "support_tickets.csv"
    if tickets_csv.exists():
        print("[5/5] Generating tickets.ttl...")
        tickets_ttl = generate_tickets_ttl(tickets_csv, args.limit)
        (output_dir / "tickets.ttl").write_text(tickets_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'tickets.ttl'}")
    else:
        print(f"[SKIP] support_tickets.csv not found")
    
    print(f"\n{'='*60}")
    print(f"Done! TTL files generated in: {output_dir}")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("  1. Start Fuseki: docker-compose up fuseki -d")
    print("  2. Load data: python scripts/11_load_ontology_to_fuseki.py")


if __name__ == "__main__":
    main()
