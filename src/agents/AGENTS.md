# AGENTS MODULE

Intent classification → orchestration → tool execution layer.

## STRUCTURE

```
agents/
├── orchestrator.py       # Main flow: intent → handler → guards → response
├── router.py             # AgentRouter class with graph-like routing
├── state.py              # AgentState dataclass (user_id, intent, sub_intent, payload)
├── nodes/
│   ├── intent_classifier.py  # classify_intent_async(), classify_intent_keyword()
│   ├── order_agent.py        # handle_order_query() for list/detail/status/cancel
│   └── claim_agent.py        # handle_claim() ticket creation
├── specialists/
│   ├── base.py               # BaseAgent ABC, AgentContext, AgentResponse
│   ├── order_specialist.py   # OrderSpecialist(BaseAgent)
│   ├── claim_specialist.py   # ClaimSpecialist(BaseAgent)
│   ├── policy_specialist.py  # PolicySpecialist(BaseAgent)
│   └── product_specialist.py # ProductSpecialist(BaseAgent)
└── tools/
    └── order_tools.py        # get_user_orders, get_order_detail, request_cancel, create_ticket
```

## WHERE TO LOOK

| Task | File | Function/Class |
|------|------|----------------|
| Add new intent | `nodes/intent_classifier.py` | Add to `classify_intent_keyword()`, update `configs/intents.yaml` |
| Add new sub_intent | `nodes/intent_classifier.py` | Add keyword check in intent block |
| Handle new domain | `orchestrator.py` | Add `if state.intent == "new":` block |
| Add tool function | `tools/order_tools.py` | Create async function, import in orchestrator |
| Custom specialist | `specialists/` | Extend `BaseAgent`, implement `handle()` |

## FLOW

```
User message
    ↓
classify_intent_async(message)  # LLM-first, keyword fallback
    ↓
AgentState(intent, sub_intent, payload)
    ↓
orchestrate.run(state)          # Switch on intent
    ├── order → handle_order_query()
    ├── claim → handle_claim()
    ├── policy → retriever.search_policy()
    └── unknown → fallback
    ↓
apply_guards(result)            # PII/policy compliance
    ↓
state.final_response
```

## CONVENTIONS

- IntentResult dataclass: `intent`, `sub_intent`, `payload`, `confidence`, `source`, `reason`
- AgentState: immutable during intent flow, `final_response` set at end
- All handlers are `async`: use `await` for tool calls
- Guard wrapping mandatory: never return raw dict without `apply_guards()`

## ANTI-PATTERNS

- **Never bypass guards**: all responses through `apply_guards()`
- **Never hardcode intents**: use `configs/intents.yaml` for keywords
- **Don't block on LLM**: keyword fallback ensures response even if LLM fails
