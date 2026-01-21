# AUTH MODULE

JWT-based authentication with rate limiting and token blacklist.

## STRUCTURE

```
auth/
├── __init__.py         # Public exports: AuthRepository, User, TokenResponse, etc.
├── models.py           # User, UserCreate, UserLogin, TokenResponse, RefreshRequest
├── jwt_handler.py      # create_access_token, create_refresh_token, verify_token
├── password.py         # hash_password, verify_password (bcrypt)
├── repository.py       # AuthRepository: user/token CRUD (SQLite)
├── dependencies.py     # get_current_user, get_current_active_user, get_optional_user
├── rate_limiter.py     # RateLimiter: sliding window per-user/IP
└── token_blacklist.py  # TokenBlacklist: revoked token tracking
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Change token expiry | `jwt_handler.py` | `get_token_expiry_seconds()`, or `configs/auth.yaml` |
| Add new role | `models.py` | Update `User.role` field |
| Modify rate limits | `configs/auth.yaml` | `rate_limit.requests_per_minute` |
| Custom auth dependency | `dependencies.py` | Create new `Depends()` function |

## FLOW

```
POST /auth/register → AuthRepository.create_user() → UserResponse
POST /auth/login → verify_password() → create_access_token() → TokenResponse
GET /protected → get_current_active_user() → User

Token refresh:
POST /auth/refresh → verify_token(refresh) → create_access_token() → new tokens
```

## CONVENTIONS

- **Bearer tokens**: `Authorization: Bearer <token>` header
- **Refresh rotation**: old refresh token revoked on use
- **Rate limiting**: per-user sliding window, configurable in auth.yaml

## ANTI-PATTERNS

- **Never log tokens**: mask in logs
- **Never store plaintext passwords**: bcrypt hash only
- **Don't skip rate limiting**: applies to all auth endpoints
