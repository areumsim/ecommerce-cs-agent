# RECOMMENDATION MODULE

SPARQL-based product recommendations via RDFRepository.

## STRUCTURE

```
recommendation/
├── models.py    # Pydantic models: RecommendationType, ProductRecommendation, *Request/*Response
└── service.py   # RecommendationService singleton with all recommendation methods
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add recommendation type | `models.py` | Add to `RecommendationType` enum |
| Add recommendation method | `service.py` | Add `async def get_xxx()` method |
| Change fallback logic | `service.py` | `_fallback_personalized()` |
| Modify scoring | `service.py` | `_rdf_product_to_recommendation()` |
| Config settings | `configs/recommendation.yaml` | Loaded by `_load_recommendation_config()` |

## RECOMMENDATION TYPES

| Type | Method | SPARQL Source |
|------|--------|---------------|
| `SIMILAR` | `get_similar_products()` | `ecom:similarTo` relations |
| `PERSONALIZED` | `get_personalized()` | Collaborative filtering via purchase history |
| `TRENDING` | `get_trending()` | Rating * review_count popularity score |
| `BOUGHT_TOGETHER` | `get_bought_together()` | `ecom:similarTo` (same as similar) |
| `CATEGORY` | `get_category_recommendations()` | Category filter + rating sort |

## FLOW

```
RecommendationRequest
    |
RecommendationService.get_xxx()
    |
    +-- Try RDF query (primary)
    |   +-- rdf_repo.get_collaborative_recommendations()
    |   +-- rdf_repo.get_similar_products()
    |   +-- rdf_repo.get_products()
    |
    +-- If RDF fails → fallback to popularity-based
    |
RecommendationResponse(products, is_fallback, method_used)
```

## USAGE

```python
from src.recommendation import get_recommendation_service

svc = get_recommendation_service()

# Personalized (collaborative filtering)
resp = await svc.get_personalized(user_id="CUST-001", top_k=10)

# Similar products
resp = await svc.get_similar_products(product_id="B0001", top_k=5)

# Trending/popular
resp = await svc.get_trending(period="week", category_id="Electronics")
```

## CONVENTIONS

- **Singleton**: Use `get_recommendation_service()`, not direct instantiation
- **Lazy RDF**: RDFRepository loaded on first use
- **Fallback-first**: Always return response, even if empty (with `is_fallback=True`)
- **Korean reasons**: `reason` field in Korean for UI display

## ANTI-PATTERNS

- **Never instantiate RecommendationService directly** - use `get_instance()`
- **Don't assume RDF available** - always check `is_available()`
- **Don't forget fallback handling** - check `is_fallback` in responses
