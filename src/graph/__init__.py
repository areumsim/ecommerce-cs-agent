"""그래프 데이터베이스 모듈.

.. deprecated:: 2026-01-16
    이 모듈은 더 이상 사용되지 않습니다.
    모든 그래프 연산은 `src.rdf.repository.RDFRepository`를 통해 
    Apache Jena Fuseki SPARQL 엔드포인트로 처리됩니다.
    
    마이그레이션:
        - `get_graph_repository()` → `get_rdf_repository()`
        - Neo4j Cypher → SPARQL
        - NetworkX → RDF + SPARQL
    
    참고: `src/rdf/repository.py`, `docs/rdf_integration.md`

Neo4j 연결 및 그래프 레포지토리를 제공합니다.
인메모리 그래프 폴백도 지원합니다.
"""

import warnings

warnings.warn(
    "src.graph 모듈은 deprecated되었습니다. "
    "src.rdf.repository.get_rdf_repository()를 사용하세요.",
    DeprecationWarning,
    stacklevel=2,
)

from .connection import (
    GraphConnection,
    Neo4jConnection,
    get_graph_connection,
    get_graph_status,
    is_graph_available,
)
from .repository import (
    GraphRepository,
    get_graph_repository,
)
from .inmemory import (
    InMemoryGraph,
    get_inmemory_graph,
    is_inmemory_available,
)

__all__ = [
    "GraphConnection",
    "Neo4jConnection",
    "get_graph_connection",
    "get_graph_status",
    "is_graph_available",
    "GraphRepository",
    "get_graph_repository",
    "InMemoryGraph",
    "get_inmemory_graph",
    "is_inmemory_available",
]
