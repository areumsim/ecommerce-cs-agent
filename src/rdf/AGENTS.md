# RDF MODULE

SPARQL-based data layer via Apache Jena Fuseki.

## STRUCTURE

```
rdf/
├── store.py       # UnifiedRDFStore, FusekiStore, get_store()
└── repository.py  # RDFRepository (all entity CRUD)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add SPARQL query | `repository.py` | Follow existing query patterns |
| Change Fuseki endpoint | `configs/rdf.yaml` | `fuseki.endpoint` |
| Local RDF fallback | `store.py` | `UnifiedRDFStore` uses rdflib |
| Add new entity type | `repository.py` | Add dataclass + CRUD methods |

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `UnifiedRDFStore` | Local rdflib graph + TTL loading |
| `FusekiStore` | HTTP client for Fuseki SPARQL endpoint |
| `RDFRepository` | Business-level CRUD for all entities |

## DATACLASSES

`repository.py` defines: `Customer`, `Product`, `Order`, `OrderItem`, `OrderDetail`, `OrderStatus`, `Ticket`

## SPARQL PATTERNS

```python
# Standard query template
query = f'''
    SELECT ?var1 ?var2
    WHERE {{
        ?s a ecom:Customer ;
           ecom:customerId "{customer_id}" ;
           ecom:name ?var1 .
    }}
    LIMIT 1
'''
results = self.store.sparql_query(query)
```

## CONVENTIONS

- **Parameterized queries**: Escape strings, use f-strings carefully
- **PREFIXES**: Defined in `store.py`, auto-prepended
- **Namespace**: `ecom:` = `http://example.org/ecommerce#`
- **Error handling**: Return `None` or empty list, log errors

## ANTI-PATTERNS

- **Never raw Fuseki HTTP calls** - use `FusekiStore` methods
- **Never modify ontology from code** - TTL files only
- **Don't cache query results** - Fuseki handles caching
