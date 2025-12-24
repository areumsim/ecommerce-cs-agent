#!/usr/bin/env python3
"""CSV 데이터를 SQLite로 마이그레이션하는 스크립트.

사용법:
    python scripts/05_migrate_to_sqlite.py [--db-path PATH] [--dry-run]

옵션:
    --db-path PATH  SQLite DB 경로 (기본: data/ecommerce.db)
    --dry-run       실제 마이그레이션 없이 확인만
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.mock_system.storage.sqlite_repository import SqliteDatabase


CSV_DIR = Path("data/mock_csv")
DEFAULT_DB_PATH = Path("data/ecommerce.db")

# CSV 파일 → 테이블 매핑
CSV_TABLE_MAPPING = {
    "users.csv": ("users", "user_id"),
    "orders.csv": ("orders", "order_id"),
    "order_items.csv": ("order_items", "id"),
    "products_cache.csv": ("products_cache", "product_id"),
    "support_tickets.csv": ("support_tickets", "ticket_id"),
    "cart.csv": ("cart", "id"),
    "wishlist.csv": ("wishlist", "id"),
    "conversations.csv": ("conversations", "id"),
}


def read_csv(path: Path) -> list[dict]:
    """CSV 파일 읽기."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def migrate_table_batch(
    db_path: str,
    csv_path: Path,
    table_name: str,
    key_field: str,
    limit: int = 0,
    dry_run: bool = False,
) -> int:
    """배치 삽입으로 테이블 마이그레이션 (대량 데이터용)."""
    import sqlite3

    records = read_csv(csv_path)
    if not records:
        print(f"  [SKIP] {csv_path.name}: 레코드 없음")
        return 0

    # 제한 적용
    if limit > 0:
        records = records[:limit]
        print(f"  [INFO] {csv_path.name}: {limit}개로 제한")

    if dry_run:
        print(f"  [DRY-RUN] {csv_path.name}: {len(records)}개 레코드 예정")
        return len(records)

    # 컬럼 추출
    if not records:
        return 0

    columns = list(records[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    columns_str = ", ".join(columns)

    conn = sqlite3.connect(db_path)
    try:
        # 기존 데이터 확인
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing = cursor.fetchone()[0]
        if existing > 0:
            print(f"  [INFO] {table_name}: 기존 {existing}개 존재, 스킵")
            return 0

        # 배치 삽입
        batch_size = 1000
        migrated = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            values = [tuple(r.get(c, "") for c in columns) for r in batch]

            conn.executemany(
                f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})",
                values
            )
            migrated += len(batch)

            if migrated % 10000 == 0:
                print(f"    진행: {migrated}/{len(records)}")

        conn.commit()
        print(f"  [OK] {csv_path.name} → {table_name}: {migrated}개 마이그레이션")
        return migrated
    finally:
        conn.close()


def migrate_table(
    db: SqliteDatabase,
    csv_path: Path,
    table_name: str,
    key_field: str,
    dry_run: bool = False,
) -> int:
    """단일 테이블 마이그레이션 (소량 데이터용)."""
    records = read_csv(csv_path)
    if not records:
        print(f"  [SKIP] {csv_path.name}: 레코드 없음")
        return 0

    if dry_run:
        print(f"  [DRY-RUN] {csv_path.name}: {len(records)}개 레코드 예정")
        return len(records)

    repo = db.get_repository(table_name, key_field)

    # 기존 데이터 확인
    existing_count = repo.count()
    if existing_count > 0:
        print(f"  [INFO] {table_name}: 기존 {existing_count}개 레코드 존재, 스킵")
        return 0

    migrated = 0
    skipped = 0

    for record in records:
        key = record.get(key_field)
        if not key:
            skipped += 1
            continue

        try:
            repo.create(record)
            migrated += 1
        except Exception as e:
            skipped += 1

    print(f"  [OK] {csv_path.name} → {table_name}: {migrated}개 마이그레이션")
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV → SQLite 마이그레이션")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite DB 경로 (기본: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 마이그레이션 없이 확인만",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)

    print("=" * 60)
    print("CSV → SQLite 마이그레이션")
    print("=" * 60)
    print(f"소스: {CSV_DIR}")
    print(f"대상: {db_path}")
    if args.dry_run:
        print("[DRY-RUN 모드]")
    print()

    # 소스 CSV 확인
    print("[1/3] CSV 파일 확인")
    total_records = 0
    for csv_file in CSV_TABLE_MAPPING.keys():
        csv_path = CSV_DIR / csv_file
        if csv_path.exists():
            records = read_csv(csv_path)
            total_records += len(records)
            print(f"  ✓ {csv_file}: {len(records)}개 레코드")
        else:
            print(f"  ✗ {csv_file}: 없음")

    print(f"\n총 {total_records}개 레코드\n")

    # 데이터베이스 초기화
    print("[2/3] 데이터베이스 초기화")
    if not args.dry_run:
        db = SqliteDatabase(str(db_path))
        print(f"  ✓ 스키마 생성 완료: {db_path}")
    else:
        print(f"  [DRY-RUN] 스키마 생성 예정: {db_path}")
        db = None

    # 마이그레이션 실행
    print("\n[3/3] 데이터 마이그레이션")
    migrated_total = 0

    # 대량 데이터 테이블은 배치로 처리
    LARGE_TABLES = {"products_cache.csv"}
    PRODUCT_LIMIT = 10000  # PoC용 상품 제한

    for csv_file, (table_name, key_field) in CSV_TABLE_MAPPING.items():
        csv_path = CSV_DIR / csv_file
        if not csv_path.exists():
            continue

        if args.dry_run:
            records = read_csv(csv_path)
            count = min(len(records), PRODUCT_LIMIT) if csv_file in LARGE_TABLES else len(records)
            print(f"  [DRY-RUN] {csv_file} → {table_name}: {count}개 예정")
            migrated_total += count
        else:
            if csv_file in LARGE_TABLES:
                # 대량 데이터: 배치 삽입 사용
                migrated = migrate_table_batch(
                    str(db_path),
                    csv_path,
                    table_name,
                    key_field,
                    limit=PRODUCT_LIMIT,
                )
            else:
                # 소량 데이터: 일반 삽입
                migrated = migrate_table(db, csv_path, table_name, key_field)
            migrated_total += migrated

    # 결과 출력
    print("\n" + "=" * 60)
    print("마이그레이션 완료")
    print("=" * 60)

    if not args.dry_run and db:
        stats = db.get_stats()
        print("\n테이블별 레코드 수:")
        for table, count in stats.items():
            print(f"  {table}: {count}")
        print(f"\n총: {sum(stats.values())}개 레코드")
    else:
        print(f"\n[DRY-RUN] 총 {migrated_total}개 레코드 마이그레이션 예정")


if __name__ == "__main__":
    main()
