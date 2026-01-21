# GRAPH MODULE (DEPRECATED)

> **WARNING**: This module is deprecated. Use `src/rdf/` instead.

## MIGRATION

| Old | New |
|-----|-----|
| `get_graph_repository()` | `get_rdf_repository()` |
| Neo4j Cypher | SPARQL |
| NetworkX | RDF + SPARQL |

## WHY DEPRECATED

- Neo4j removed in favor of Apache Jena Fuseki
- All graph operations now via SPARQL
- See `src/rdf/repository.py` for replacement

## DO NOT USE

```python
# WRONG - deprecated
from src.graph import get_graph_repository

# CORRECT - use RDF
from src.rdf import RDFRepository
```
