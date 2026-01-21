# CORE MODULE

Shared infrastructure: exceptions, structured logging, pipeline tracing.

## STRUCTURE

```
core/
├── exceptions.py   # Custom exception hierarchy
├── logging.py      # JSON logging, request context
└── tracer.py       # Pipeline step tracking (debug UI)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new exception | `exceptions.py` | Extend `AppError`, set status_code/error_code |
| Change log format | `logging.py` | Modify `JSONFormatter.format()` |
| Add trace step type | `tracer.py` | Add to `step_icons` dict |
| Get request context | `logging.py` | `get_request_id()`, `get_user_id()` |

## EXCEPTION HIERARCHY

| Class | Status | Use Case |
|-------|--------|----------|
| `AppError` | 500 | Base class |
| `AuthError` | 401 | Authentication failure |
| `RateLimitError` | 429 | Too many requests |
| `ValidationError` | 400 | Invalid input |
| `NotFoundError` | 404 | Resource not found |
| `PermissionError` | 403 | Authorization failure |
| `ConflictError` | 409 | Resource conflict |
| `ServiceUnavailableError` | 503 | External service down |

## TRACER FLOW

```
start_trace(user_id, message)
    │
add_trace(step_type, name, input, output)  # Repeat per step
    │
end_trace(final_response)
    │
get_trace_display()  # Human-readable for debug UI
```

### Step Types

| Type | Icon | Usage |
|------|------|-------|
| `intent` | 🎯 | Intent classification |
| `llm` | 🤖 | LLM API call |
| `orchestrator` | 🎭 | Routing decision |
| `tool` | 🔧 | Tool execution |
| `guard` | 🛡️ | Guardrail check |
| `sparql` | 📊 | SPARQL query |

## KEY FUNCTIONS

| Function | Purpose |
|----------|---------|
| `get_logger(name)` | ContextLogger with request/user ID |
| `setup_logging()` | Configure JSON logging + rotation |
| `start_trace()` | Begin trace session |
| `add_trace()` | Add step to current session |
| `get_trace_display()` | Format for debug panel |

## CONVENTIONS

- **JSON logs**: All structured, include `request_id`, `user_id`
- **Exception.to_dict()**: Always return API-friendly format
- **Trace sanitization**: Auto-redacts API keys, limits string length

## ANTI-PATTERNS

- **Don't raise generic Exception** - use hierarchy
- **Don't log PII** - sanitized automatically but avoid
- **Don't skip tracer** - all agent steps should trace
