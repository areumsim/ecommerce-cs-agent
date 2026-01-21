# TESTS MODULE

pytest test suite with async support and fixtures.

## STRUCTURE

```
tests/
├── conftest.py           # Fixtures: client, test_user_id, sample payloads
├── test_api.py           # FastAPI endpoint tests
├── test_auth.py          # JWT, login, register, token refresh
├── test_config.py        # Config loading, env overrides
├── test_conversation.py  # Conversation CRUD, session management
├── test_conversation_manager.py  # Multi-turn session tests
├── test_csv_repository.py        # CSV storage backend
├── test_dependencies.py  # FastAPI dependencies
├── test_evaluation.py    # Evaluation metrics
├── test_guardrails.py    # PII masking, injection detection
├── test_intent_classifier.py     # Intent classification (22 tests)
├── test_logging.py       # Structured logging
├── test_monitoring.py    # Prometheus metrics
├── test_orchestrator.py  # Agent orchestration flow
├── test_rag.py           # RAG retrieval (keyword/hybrid/embedding)
├── test_rate_limiter.py  # Rate limiting behavior
├── test_rdf.py           # SPARQL queries, RDF repository
├── test_recommendation.py        # Recommendation service
├── test_routing.py       # Intent routing
├── test_token_blacklist.py       # Token revocation
├── test_vision.py        # Vision pipeline, defect detection
└── load/
    └── locustfile.py     # Load testing (Locust)
```

## RUN TESTS

```bash
# All tests
pytest -q

# Specific module
pytest tests/test_rdf.py -q
pytest tests/test_auth.py -v

# With coverage
pytest --cov=src --cov-report=html

# Load tests
cd tests/load && locust -f locustfile.py
```

## KEY FIXTURES (conftest.py)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `setup_test_database` | session | Auto-migrate SQLite if missing |
| `reset_config` | function | Reset Config singleton between tests |
| `reset_conversation_repo` | function | Reset conversation repo singleton |
| `client` | function | FastAPI TestClient |
| `test_user_id` | function | Returns `"user_001"` |
| `sample_policy_query` | function | Returns `"환불"` |
| `sample_order_payload` | function | Order dict with user_id, order_id |
| `sample_ticket_payload` | function | Ticket creation dict |
| `sample_chat_payload` | function | Chat dict with message |

## CONVENTIONS

- **pytest-asyncio**: Use `@pytest.mark.asyncio` for async tests
- **Fixture reset**: Singletons reset between tests via `reset_config`, `reset_conversation_repo`
- **No external deps**: Tests mock Fuseki, don't require live server
- **Korean test data**: Sample payloads use Korean text

## WHERE TO LOOK

| Task | File |
|------|------|
| Add API test | `test_api.py` |
| Add auth test | `test_auth.py` |
| Add RAG test | `test_rag.py` |
| Add RDF test | `test_rdf.py` |
| Add fixture | `conftest.py` |
| Load testing | `load/locustfile.py` |

## ANTI-PATTERNS

- **Don't skip fixture reset** - causes singleton leakage
- **Don't depend on Fuseki** - mock or use local rdflib
- **Don't hardcode paths** - use `PROJECT_ROOT` from conftest
