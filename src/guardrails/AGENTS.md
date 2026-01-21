# GUARDRAILS MODULE

Input/output safety: PII masking, injection defense, tone validation.

## STRUCTURE

```
guardrails/
├── input_guards.py   # PII detection, injection blocking
├── output_guards.py  # Sensitive info filtering, tone check
└── pipeline.py       # Unified apply_guards(), price/stock validation
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add PII pattern | `configs/guardrails.yaml` | `pii_patterns` section |
| Add blocked word | `configs/guardrails.yaml` | `blocked_words` list |
| Injection patterns | `configs/guardrails.yaml` | `injection_patterns` |
| Custom guard | `pipeline.py` | Add to `apply_guards()` flow |

## KEY FUNCTIONS

| Function | Purpose |
|----------|---------|
| `apply_input_guards(text)` | Returns `InputGuardResult` |
| `apply_output_guards(text)` | Returns `OutputGuardResult` |
| `apply_guards(response)` | Full pipeline on dict response |
| `detect_pii(text)` | Find PII matches |
| `mask_pii_in_response(text)` | Replace PII with masks |
| `validate_price_stock(resp)` | Check against CSV data |

## PII PATTERNS (Korean)

| Key | Description | Example Mask |
|-----|-------------|--------------|
| `phone_kr` | 휴대폰 번호 | `***-****-****` |
| `email` | 이메일 주소 | `***@***.***` |
| `rrn` | 주민등록번호 | `******-*******` |
| `card` | 카드 번호 | `****-****-****-****` |

## FLOW

```
User input
    ↓
apply_input_guards()
    ├── Length check
    ├── PII detection + masking
    ├── Injection detection
    └── Blocked words
    ↓
InputGuardResult(ok, sanitized_text, warnings, blocked)
```

## CONVENTIONS

- **Mandatory wrapping**: All orchestrator responses through `apply_guards()`
- **Non-blocking PII**: Mask and continue (warn, don't block)
- **Blocking injection**: Reject immediately

## ANTI-PATTERNS

- **Never return raw response** - always guard-wrapped
- **Don't log PII** - only log masked versions
