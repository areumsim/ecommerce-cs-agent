# CONFIGS MODULE

YAML configuration files with environment variable overrides.

## STRUCTURE

```
configs/
├── llm.yaml           # LLM provider, model selection, routing
├── rdf.yaml           # Fuseki endpoint, prefixes
├── rag.yaml           # Retrieval mode, hybrid alpha
├── auth.yaml          # JWT settings, password policy
├── guardrails.yaml    # PII patterns, injection defense
├── intents.yaml       # Intent keywords, LLM classification settings
├── recommendation.yaml # Rec service config
├── paths.yaml         # Data directories
├── app.yaml           # App-level settings
├── mock.yaml          # Mock data generation
├── neo4j.yaml         # DEPRECATED (use rdf.yaml)
├── crawl.yaml         # Policy crawler settings
└── prompts/           # LLM prompt templates
    ├── system.txt
    ├── order.txt
    ├── claim.txt
    ├── policy.txt
    └── intent_classification.txt
```

## WHERE TO LOOK

| Task | File | Setting |
|------|------|---------|
| Change LLM model | `llm.yaml` | `openai.model`, `provider` |
| Change Fuseki URL | `rdf.yaml` | `fuseki.endpoint` |
| Add PII pattern | `guardrails.yaml` | `pii_patterns` section |
| Add intent keyword | `intents.yaml` | `intents.<name>.keywords` |
| Change JWT expiry | `auth.yaml` | `jwt.access_token_expire_minutes` |
| Adjust RAG alpha | `rag.yaml` | `retrieval.hybrid_alpha` |

## ENV OVERRIDES

All settings support environment variable override via `${VAR}` syntax:

```yaml
# configs/llm.yaml
openai:
  api_key: ${OPENAI_API_KEY}  # From environment
```

## KEY FILES

### llm.yaml
- `provider`: openai | anthropic | google | local
- `routing.rules`: Intent-based model selection
- `prompts`: Path to prompt templates

### rdf.yaml
- `rdf.backend`: fuseki | rdflib
- `fuseki.endpoint`: Fuseki SPARQL endpoint
- `prefixes`: SPARQL namespace prefixes

### auth.yaml
- `jwt.secret_key`: Token signing key (use env var!)
- `password.min_length`: Password policy
- `security.max_login_attempts`: Brute force protection

### guardrails.yaml
- `pii_patterns`: Regex with masks (phone, email, card)
- `injection_patterns`: Prompt injection blocklist
- `blocked_words`: Forbidden terms

### intents.yaml
- `llm_classification.enabled`: Use LLM for intent
- `patterns.order_id`: Order ID regex
- `intents.<name>.keywords`: Keyword fallback

## CONVENTIONS

- **No secrets in YAML** - use `${ENV_VAR}` syntax
- **Korean comments allowed** - for Korean settings
- **Prompt templates in prompts/** - separate .txt files

## ANTI-PATTERNS

- **Don't commit API keys** - even in examples
- **Don't use neo4j.yaml** - deprecated, use rdf.yaml
