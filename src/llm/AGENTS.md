# LLM MODULE

Multi-provider LLM client (OpenAI, Anthropic, local).

## STRUCTURE

```
llm/
├── client.py   # LLMClient, get_client(), generate_response()
└── router.py   # Intent-based model routing
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Change provider/model | `configs/llm.yaml` | `provider`, `model` |
| Add provider | `client.py` | Add to `base_urls` dict, implement handler |
| Load prompt template | `client.py` | `load_prompt(name)` from `configs/prompts/` |
| Streaming response | `client.py` | `generate_response_stream()` |

## KEY FUNCTIONS

| Function | Purpose |
|----------|---------|
| `get_client()` | Singleton LLMClient instance |
| `get_llm_config()` | Load provider config from yaml |
| `generate_response()` | Async, returns full response |
| `generate_response_stream()` | Async generator for streaming |
| `load_prompt(name)` | Load from `configs/prompts/{name}.txt` |

## SUPPORTED PROVIDERS

| Provider | Base URL |
|----------|----------|
| openai | `https://api.openai.com/v1` |
| anthropic | `https://api.anthropic.com` |
| google | `https://generativelanguage.googleapis.com/v1beta` |
| local | Configurable, default `http://localhost:8080/v1` |

## CONVENTIONS

- **Async only**: All generation functions are `async`
- **Config from YAML**: No hardcoded API keys
- **Timeout**: Configurable in `llm.yaml`, default 30s

## ANTI-PATTERNS

- **Never hardcode API keys** - use env vars via config
- **Never block on LLM** - always use async
- **Don't ignore timeouts** - network failures happen
