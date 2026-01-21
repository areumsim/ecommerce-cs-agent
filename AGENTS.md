# ECOMMERCE CS AGENT - PROJECT KNOWLEDGE BASE

**Updated:** 2026-01-20 | **Commit:** 5e86900 | **Branch:** main

## OVERVIEW

Korean e-commerce customer service agent PoC. Intent classification → Orchestrator → Tool calls → Response.

**Storage**: Apache Jena Fuseki triple store (~32K triples)  
**RAG**: Hybrid search (FAISS vector + keyword), 63 policy documents  
**UI**: Gradio single-page (5 tabs: Overview, Intelligence, Graph Explorer, Data Tables, Developer Tools) | **API**: FastAPI (port 8000)

## STRUCTURE

```
ecommerce-cs-agent/
├── api.py              # FastAPI server (990 lines) - auth, chat, orders, tickets
├── ui.py               # Gradio UI (1683 lines) - demo page, NL→SPARQL, debug panel
├── src/
│   ├── agents/         # Intent classifier, orchestrator, tools, specialists
│   ├── rdf/            # RDF store + repository (SPARQL over HTTP)
│   ├── rag/            # Policy retriever (keyword/hybrid/embedding)
│   ├── auth/           # JWT auth, rate limiting, bcrypt
│   ├── llm/            # LLM client (OpenAI/Anthropic/local)
│   ├── guardrails/     # PII masking, injection defense
│   ├── conversation/   # Multi-turn session (SQLite)
│   ├── recommendation/ # SPARQL collaborative filtering
│   ├── vision/         # Product image analysis, defect detection
│   ├── mock_system/    # CSV/SQLite repository fallback
│   ├── core/           # Shared: exceptions, logging, tracer (see src/core/AGENTS.md)
│   ├── monitoring/     # Prometheus metrics middleware
│   ├── evaluation/     # Benchmarks, scenarios, evaluator (see src/evaluation/AGENTS.md)
│   └── graph/          # DEPRECATED - use src/rdf/ instead
├── ontology/           # RDF schema + instance data (see ontology/AGENTS.md)
├── scripts/            # Numbered data pipeline (see scripts/AGENTS.md)
├── configs/            # YAML configs (see configs/AGENTS.md)
├── tests/              # pytest suite (see tests/AGENTS.md)
└── data/               # Generated data (mock_csv, indexes) - NOT committed
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| **Add new intent** | `src/agents/nodes/intent_classifier.py` | + `configs/intents.yaml` |
| **Add new tool** | `src/agents/tools/order_tools.py` | Uses RDFRepository |
| **Add API endpoint** | `api.py` | Use `get_current_active_user` dependency |
| **Modify RAG** | `src/rag/retriever.py` | Mode: `configs/rag.yaml` |
| **RDF operations** | `src/rdf/repository.py` | RDFRepository (all CRUD) |
| **Ontology schema** | `ontology/ecommerce.ttl` | OWL classes/properties |
| **SHACL validation** | `ontology/shacl/ecommerce-shapes.ttl` | Data constraints |
| **LLM settings** | `configs/llm.yaml` | Provider, model, tokens |
| **Guardrails config** | `configs/guardrails.yaml` | PII patterns, blocklist |
| **UI modifications** | `ui.py` | Gradio Blocks |
| **Vision pipeline** | `src/vision/pipeline.py` | Image analysis, defect detection |
| **Recommendations** | `src/recommendation/service.py` | SPARQL-based product recs |
| **NL→SPARQL** | `ui.py:34-118`, `ui.py:559-621` | `load_ontology_schema()`, `convert_nl_to_sparql()` |
| **Auth flow** | `src/auth/` | JWT, rate limiting, token blacklist |
| **Session management** | `src/conversation/manager.py` | Multi-turn SQLite persistence |
| **Custom exceptions** | `src/core/exceptions.py` | AppError, AuthError, ValidationError |
| **Config loading** | `src/config.py` | Unified YAML loader with env overrides |
| **Pipeline tracing** | `src/core/tracer.py` | Debug UI, step tracking |
| **Evaluation/benchmark** | `src/evaluation/` | Test scenarios, LLM evaluator |

## LARGE FILES (>500 lines)

| File | Lines | Purpose |
|------|-------|---------|
| `ui.py` | 1683 | Gradio UI, NL→SPARQL conversion |
| `api.py` | 990 | FastAPI endpoints, auth routes |
| `src/rdf/repository.py` | 737 | RDFRepository SPARQL CRUD |
| `src/llm/client.py` | 671 | Multi-provider LLM client |
| `src/graph/inmemory.py` | 627 | DEPRECATED in-memory graph |
| `src/conversation/repository.py` | 567 | SQLite conversation CRUD |
| `src/agents/nodes/intent_classifier.py` | 522 | Intent classification (LLM + keyword) |
| `src/rdf/store.py` | 495 | UnifiedRDFStore, FusekiStore |
| `src/agents/orchestrator.py` | 480 | Agent flow orchestration |
| `src/config.py` | 419 | Unified config loader |
| `src/recommendation/service.py` | 404 | RecommendationService singleton |

## COMMANDS

```bash
# Setup
pip install -r requirements.txt

# Data pipeline
python scripts/03_generate_mock_csv.py    # Mock CSV data
python scripts/12_generate_mock_ttl.py    # CSV → TTL
python scripts/15_generate_embeddings.py  # Product embeddings

# Load to Fuseki
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' -u admin:admin123 \
    -H 'Content-Type: text/turtle' --data-binary @"$f"
done

# Run
uvicorn api:app --reload    # API (port 8000)
python ui.py                # UI (port 7860)

# Test
pytest -q                   # All tests
pytest tests/test_rdf.py -q # Specific module

# Docker
docker build -t ecommerce-agent .
docker run -p 8000:8000 -p 7860:7860 ecommerce-agent
```

## DATA COUNTS

| Entity | Count | Source |
|--------|-------|--------|
| Products | 1,492 | Amazon Reviews |
| Orders | 491 | Mock |
| OrderItems | 1,240 | Mock |
| Customers | 100 | Mock |
| Tickets | 60 | Mock |
| Similarities | 4,416 | Auto-generated |
| **Total Triples** | ~32,000 | Fuseki |

## CONVENTIONS

- **Python 3.10+**, PEP 8, type hints
- **RDF-first**: All CRUD through `RDFRepository`
- **Korean UI messages**, English code
- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `docs:`
- **Async-first**: LLM, vision, recommendations are async
- **Singleton pattern**: `get_client()`, `get_recommendation_service()`, `get_pipeline()`

## ANTI-PATTERNS

- **Never commit secrets** - use `.env`
- **Never commit `data/`** - large files, regenerate from scripts
- **Never suppress errors** - use `src/core/exceptions.py`
- **Never bypass RDF** - no direct Fuseki calls outside `store.py`
- **Never bypass guards** - all responses through `apply_guards()`
- **Never hardcode API keys** - use env vars via `configs/*.yaml`
- **Never import CLIP at module level** - use lazy loading

## FUSEKI CONNECTION

```yaml
# configs/rdf.yaml
fuseki:
  endpoint: "http://ar_fuseki:3030/ecommerce"
  user: "admin"
  password: "admin123"
```

External Docker container: `ar_fuseki:3030` (host port 31010)

## CONFIG FILES

| File | Purpose |
|------|---------|
| `configs/llm.yaml` | LLM provider, model, tokens |
| `configs/rag.yaml` | Retrieval mode, hybrid alpha |
| `configs/auth.yaml` | JWT expiry, rate limits |
| `configs/guardrails.yaml` | PII patterns, blocklist |
| `configs/intents.yaml` | Intent keywords |
| `configs/rdf.yaml` | Fuseki endpoint |
| `configs/recommendation.yaml` | Rec settings |
| `configs/paths.yaml` | Data directories |
