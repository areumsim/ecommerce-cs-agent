# CONVERSATION MODULE

Multi-turn session management with SQLite persistence.

## STRUCTURE

```
conversation/
├── models.py      # Conversation, Message, *Create dataclasses
├── repository.py  # ConversationRepository (SQLite CRUD)
└── manager.py     # ConversationManager (session lifecycle)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add message field | `models.py` | Update `Message` dataclass |
| Change DB path | `configs/paths.yaml` | `sqlite_path` |
| Session expiry | `repository.py` | `expires_at` field |
| Get/create session | `manager.py` | `get_or_create_conversation()` |

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `Conversation` | Session with user_id, title, status, metadata |
| `Message` | role, content, metadata, timestamp |
| `ConversationRepository` | SQLite CRUD, auto-migration |
| `ConversationManager` | High-level session operations |

## TABLES

```sql
conversations (id, user_id, title, status, metadata, created_at, updated_at, expires_at)
messages (id, conversation_id, role, content, metadata, created_at)
```

## CONVENTIONS

- **SQLite row_factory**: Returns dict-like rows
- **Auto-migration**: `_ensure_tables()` adds missing columns
- **JSON metadata**: Stored as TEXT, parsed on read
- **UTC timestamps**: ISO 8601 format

## ANTI-PATTERNS

- **Don't access DB directly** - use Repository methods
- **Don't forget cleanup** - expired sessions need pruning
