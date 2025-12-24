#!/usr/bin/env python3
"""확장된 Mock 데이터 생성 스크립트.

목표 데이터량:
- 100 users
- 500 orders
- 1,500 order items
- 200 support tickets
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

DATA_DIR = Path("data")
MOCK_DIR = DATA_DIR / "mock_csv"
PROCESSED_DIR = DATA_DIR / "processed"

# 한국 이름 데이터
FIRST_NAMES = [
    "민준", "서준", "도윤", "예준", "시우", "하준", "지호", "주원", "지후", "준서",
    "서연", "서윤", "지우", "서현", "하은", "하윤", "민서", "지유", "윤서", "채원",
    "지민", "수빈", "영호", "현우", "성민", "재현", "승현", "정훈", "태현", "영민",
]

LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "신", "서", "권", "황"]

# 한국 지역 데이터
CITIES = ["서울", "부산", "인천", "대구", "대전", "광주", "울산", "세종"]
DISTRICTS = {
    "서울": ["강남구", "서초구", "송파구", "마포구", "용산구", "종로구", "강서구", "영등포구"],
    "부산": ["해운대구", "수영구", "부산진구", "동래구", "남구"],
    "인천": ["남동구", "연수구", "부평구", "계양구"],
    "대구": ["수성구", "달서구", "북구", "중구"],
    "대전": ["유성구", "서구", "중구"],
    "광주": ["광산구", "서구", "북구"],
    "울산": ["남구", "중구", "동구"],
    "세종": ["아름동", "새롬동", "한솔동"],
}

# 주문 상태
ORDER_STATUSES = ["pending", "confirmed", "shipping", "delivered", "cancelled"]
ORDER_STATUS_WEIGHTS = [0.1, 0.15, 0.2, 0.45, 0.1]  # delivered가 가장 많음

# 티켓 타입
TICKET_TYPES = ["refund", "exchange", "shipping", "product_inquiry", "order_inquiry", "complaint"]
TICKET_TYPE_WEIGHTS = [0.25, 0.15, 0.2, 0.15, 0.15, 0.1]

# 티켓 템플릿
TICKET_TEMPLATES = {
    "refund": [
        "상품 불량으로 환불 요청합니다.",
        "단순 변심으로 환불하고 싶습니다.",
        "주문한 상품과 다른 상품이 와서 환불 원합니다.",
        "사이즈가 맞지 않아 환불 신청합니다.",
        "색상이 사진과 달라서 환불해주세요.",
    ],
    "exchange": [
        "사이즈 교환 부탁드립니다.",
        "색상 교환하고 싶습니다.",
        "불량품이라 교환 요청합니다.",
        "다른 상품으로 교환 가능한가요?",
    ],
    "shipping": [
        "배송이 너무 오래 걸립니다.",
        "배송 조회가 안 됩니다.",
        "배송지 변경 가능한가요?",
        "언제 배송되나요?",
        "택배사 연락처 알려주세요.",
    ],
    "product_inquiry": [
        "이 상품 재입고 언제 되나요?",
        "상품 사이즈 정보 알려주세요.",
        "소재가 무엇인가요?",
        "세탁 방법이 궁금합니다.",
    ],
    "order_inquiry": [
        "주문 취소하고 싶습니다.",
        "주문 내역 확인해주세요.",
        "결제가 제대로 됐는지 확인해주세요.",
        "주문 상태가 궁금합니다.",
    ],
    "complaint": [
        "고객센터 연결이 안 됩니다.",
        "환불 처리가 너무 늦습니다.",
        "상담원 태도가 불친절했습니다.",
        "약속한 배송일이 지났는데 아직 안 왔습니다.",
    ],
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    """CSV 파일 읽기."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    """CSV 파일 쓰기."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def generate_korean_name() -> str:
    """랜덤 한국 이름 생성."""
    return random.choice(LAST_NAMES) + random.choice(FIRST_NAMES)


def generate_phone() -> str:
    """한국 휴대폰 번호 생성."""
    return f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def generate_email(user_id: str) -> str:
    """이메일 주소 생성."""
    domains = ["gmail.com", "naver.com", "daum.net", "kakao.com", "hanmail.net"]
    return f"{user_id}@{random.choice(domains)}"


def generate_address() -> str:
    """한국 주소 생성."""
    city = random.choice(CITIES)
    district = random.choice(DISTRICTS.get(city, ["중구"]))
    dong = f"{random.randint(1, 20)}동"
    ho = f"{random.randint(101, 2599)}호"
    return f"{city} {district} {dong} {ho}"


def generate_users(count: int = 100) -> List[Dict[str, str]]:
    """사용자 데이터 생성."""
    users = []
    now = datetime.utcnow()

    for i in range(1, count + 1):
        user_id = f"user_{i:03d}"
        created_days_ago = random.randint(30, 365)
        created_at = (now - timedelta(days=created_days_ago)).isoformat() + "Z"

        users.append({
            "user_id": user_id,
            "name": generate_korean_name(),
            "email": generate_email(user_id),
            "phone": generate_phone(),
            "address": generate_address(),
            "membership_level": random.choice(["bronze", "silver", "gold", "platinum"]),
            "created_at": created_at,
        })

    return users


def generate_orders(
    users: List[Dict[str, str]],
    products: List[Dict[str, str]],
    order_count: int = 500,
    items_per_order_range: tuple = (1, 5),
) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """주문 및 주문 아이템 데이터 생성."""
    orders = []
    order_items = []
    now = datetime.utcnow()

    for i in range(1, order_count + 1):
        user = random.choice(users)
        user_id = user["user_id"]

        # 주문 날짜 (최근 90일 내)
        order_days_ago = random.randint(1, 90)
        order_date = now - timedelta(days=order_days_ago)

        # 주문 상태 (weighted random)
        status = random.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS)[0]

        # 배송 완료 날짜 (delivered인 경우만)
        if status == "delivered":
            delivery_days = random.randint(2, 7)
            delivery_date = (order_date + timedelta(days=delivery_days)).isoformat() + "Z"
        else:
            delivery_date = ""

        order_id = f"ORD_{order_date.strftime('%Y%m%d')}_{i:04d}"

        # 주문 아이템 생성
        item_count = random.randint(*items_per_order_range)
        total_amount = 0.0

        selected_products = random.sample(products, min(item_count, len(products)))

        for j, product in enumerate(selected_products):
            try:
                price = float(product.get("price", 0))
            except (ValueError, TypeError):
                price = random.uniform(10000, 100000)

            quantity = random.randint(1, 3)
            item_total = price * quantity
            total_amount += item_total

            order_items.append({
                "id": f"{order_id}_{j:02d}",
                "order_id": order_id,
                "product_id": product.get("product_id", ""),
                "quantity": str(quantity),
                "unit_price": f"{price:.0f}",
            })

        orders.append({
            "order_id": order_id,
            "user_id": user_id,
            "status": status,
            "order_date": order_date.isoformat() + "Z",
            "delivery_date": delivery_date,
            "total_amount": f"{total_amount:.0f}",
            "shipping_address": user.get("address", generate_address()),
            "created_at": order_date.isoformat() + "Z",
        })

    return orders, order_items


def generate_tickets(
    users: List[Dict[str, str]],
    orders: List[Dict[str, str]],
    ticket_count: int = 200,
) -> List[Dict[str, str]]:
    """지원 티켓 데이터 생성."""
    tickets = []
    now = datetime.utcnow()

    # 사용자별 주문 매핑
    user_orders = {}
    for order in orders:
        uid = order["user_id"]
        if uid not in user_orders:
            user_orders[uid] = []
        user_orders[uid].append(order)

    for i in range(1, ticket_count + 1):
        # 주문이 있는 사용자 선택 (80%), 없으면 랜덤
        users_with_orders = [u for u in users if u["user_id"] in user_orders]
        if users_with_orders and random.random() < 0.8:
            user = random.choice(users_with_orders)
            user_orders_list = user_orders.get(user["user_id"], [])
            order = random.choice(user_orders_list) if user_orders_list else None
        else:
            user = random.choice(users)
            order = None

        # 티켓 타입
        issue_type = random.choices(TICKET_TYPES, weights=TICKET_TYPE_WEIGHTS)[0]

        # 티켓 설명
        description = random.choice(TICKET_TEMPLATES.get(issue_type, ["문의드립니다."]))

        # 티켓 생성 날짜
        created_days_ago = random.randint(0, 60)
        created_at = now - timedelta(days=created_days_ago)

        # 해결 여부 (60% resolved)
        is_resolved = random.random() < 0.6
        if is_resolved:
            resolved_days = random.randint(0, min(created_days_ago, 7))
            resolved_at = (created_at + timedelta(days=resolved_days)).isoformat() + "Z"
            status = "closed"
        else:
            resolved_at = ""
            status = random.choice(["open", "in_progress"])

        ticket_id = f"TICKET_{int(created_at.timestamp())}"

        tickets.append({
            "ticket_id": ticket_id,
            "user_id": user["user_id"],
            "order_id": order["order_id"] if order else "",
            "issue_type": issue_type,
            "description": description,
            "status": status,
            "priority": random.choice(["low", "normal", "high", "urgent"]),
            "created_at": created_at.isoformat() + "Z",
            "resolved_at": resolved_at,
        })

    return tickets


def main() -> None:
    parser = argparse.ArgumentParser(description="확장된 Mock 데이터 생성")
    parser.add_argument("--users", type=int, default=100, help="생성할 사용자 수")
    parser.add_argument("--orders", type=int, default=500, help="생성할 주문 수")
    parser.add_argument("--tickets", type=int, default=200, help="생성할 티켓 수")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--force", action="store_true", help="기존 데이터 덮어쓰기")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 50)
    print("확장된 Mock 데이터 생성")
    print("=" * 50)

    # 기존 데이터 확인
    users_path = MOCK_DIR / "users.csv"
    orders_path = MOCK_DIR / "orders.csv"

    if not args.force:
        existing_users = read_csv(users_path)
        existing_orders = read_csv(orders_path)
        if len(existing_users) >= args.users and len(existing_orders) >= args.orders:
            print(f"이미 충분한 데이터 존재 (users: {len(existing_users)}, orders: {len(existing_orders)})")
            print("--force 옵션으로 덮어쓸 수 있습니다.")
            return

    # 상품 데이터 로드
    products_path = MOCK_DIR / "products_cache.csv"
    products = read_csv(products_path)
    if not products:
        print(f"[ERROR] 상품 데이터 없음: {products_path}")
        print("먼저 python scripts/03_generate_mock_csv.py 실행하세요.")
        return

    print(f"[INFO] 상품 데이터 로드: {len(products)}개")

    # 1. 사용자 생성
    print(f"\n[1/4] 사용자 {args.users}명 생성 중...")
    users = generate_users(args.users)
    write_csv(users_path, users, [
        "user_id", "name", "email", "phone", "address", "membership_level", "created_at"
    ])
    print(f"      → {len(users)}명 생성 완료: {users_path}")

    # 2. 주문 및 주문 아이템 생성
    print(f"\n[2/4] 주문 {args.orders}개 생성 중...")
    orders, order_items = generate_orders(users, products, args.orders)

    orders_path = MOCK_DIR / "orders.csv"
    write_csv(orders_path, orders, [
        "order_id", "user_id", "status", "order_date", "delivery_date",
        "total_amount", "shipping_address", "created_at"
    ])
    print(f"      → {len(orders)}개 주문 생성 완료: {orders_path}")

    items_path = MOCK_DIR / "order_items.csv"
    write_csv(items_path, order_items, [
        "id", "order_id", "product_id", "quantity", "unit_price"
    ])
    print(f"      → {len(order_items)}개 주문 아이템 생성 완료: {items_path}")

    # 3. 지원 티켓 생성
    print(f"\n[3/4] 지원 티켓 {args.tickets}개 생성 중...")
    tickets = generate_tickets(users, orders, args.tickets)

    tickets_path = MOCK_DIR / "support_tickets.csv"
    write_csv(tickets_path, tickets, [
        "ticket_id", "user_id", "order_id", "issue_type", "description",
        "status", "priority", "created_at", "resolved_at"
    ])
    print(f"      → {len(tickets)}개 티켓 생성 완료: {tickets_path}")

    # 4. 요약
    print("\n[4/4] 생성 완료")
    print("=" * 50)
    print(f"사용자:      {len(users):>6}명")
    print(f"주문:        {len(orders):>6}개")
    print(f"주문 아이템: {len(order_items):>6}개")
    print(f"지원 티켓:   {len(tickets):>6}개")
    print("=" * 50)

    # 상태별 통계
    print("\n[통계]")

    # 주문 상태 분포
    order_status_count = {}
    for order in orders:
        status = order["status"]
        order_status_count[status] = order_status_count.get(status, 0) + 1
    print("  주문 상태:")
    for status, count in sorted(order_status_count.items()):
        print(f"    - {status}: {count}")

    # 티켓 타입 분포
    ticket_type_count = {}
    for ticket in tickets:
        issue_type = ticket["issue_type"]
        ticket_type_count[issue_type] = ticket_type_count.get(issue_type, 0) + 1
    print("  티켓 타입:")
    for issue_type, count in sorted(ticket_type_count.items()):
        print(f"    - {issue_type}: {count}")


if __name__ == "__main__":
    main()
