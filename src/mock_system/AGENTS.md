# MOCK_SYSTEM MODULE

CSV/SQLite repository abstraction for orders, tickets, users.

## STRUCTURE

```
mock_system/
├── order_service.py    # OrderService: orders/order_items CRUD
├── ticket_service.py   # TicketService: tickets CRUD
└── storage/
    ├── interfaces.py       # Repository protocol, CsvRepoConfig
    ├── csv_repository.py   # CSVRepository: file-based storage
    ├── sqlite_repository.py # SQLiteRepository: DB-based storage
    └── factory.py          # get_repository() factory
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new entity | `storage/interfaces.py` | Add `XxxRepository(Repository, Protocol)` |
| CSV schema | `data/mock_csv/` | One CSV per entity (orders.csv, tickets.csv, etc.) |
| Switch backend | `configs/paths.yaml` | `storage.backend: csv|sqlite` |
| Migrate data | `scripts/05_migrate_to_sqlite.py` | CSV → SQLite |

## CSV SCHEMA

| File | Key Field | JSON Fields |
|------|-----------|-------------|
| `orders.csv` | `order_id` | None |
| `order_items.csv` | `item_id` | None |
| `tickets.csv` | `ticket_id` | `metadata` |
| `users.csv` | `user_id` | None |
| `products_cache.csv` | `product_id` | None |

## CONVENTIONS

- **Thread-safe CSV**: File locking implemented (`fcntl` + threading locks)
- **Thin adapters**: services call repository, minimal business logic
- **Protocol typing**: all repos implement `Repository` protocol (get_by_id, query, create, update, delete)

## ANTI-PATTERNS

- **Don't put business logic in repositories**: keep in services layer
- **Prefer SQLite for heavy writes**: CSV locking has overhead
