"""Mock 시스템 모듈 (DEPRECATED).

.. deprecated:: 2026-01-16
    이 모듈은 더 이상 사용되지 않습니다.
    모든 데이터 연산은 `src.rdf.repository.RDFRepository`를 통해
    Apache Jena Fuseki SPARQL 엔드포인트로 처리됩니다.

    마이그레이션:
        - `OrderService` → `order_tools` (src/agents/tools/order_tools.py)
        - `TicketService` → `order_tools.create_ticket()`
        - `CSVRepository` → `RDFRepository`
        - `SqliteDatabase` → Fuseki (SPARQL)

    참고: `src/rdf/repository.py`, `docs/rdf_integration.md`
"""

import warnings

warnings.warn(
    "src.mock_system 모듈은 deprecated되었습니다. "
    "src.agents.tools.order_tools 또는 src.rdf.repository를 사용하세요.",
    DeprecationWarning,
    stacklevel=2,
)
