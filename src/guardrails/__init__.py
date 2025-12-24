"""가드레일 모듈.

기능:
- 입력 가드: PII 마스킹, 프롬프트 인젝션 방어
- 출력 가드: 민감 정보 필터링, 톤 검증
- 파이프라인: 전체 가드 통합 적용
"""

from .input_guards import (
    InputGuardResult,
    apply_input_guards,
    detect_pii,
    detect_injection,
    mask_pii_in_response,
)
from .output_guards import (
    OutputGuardResult,
    apply_output_guards,
    format_safe_response,
)
from .pipeline import (
    apply_guards,
    check_policy_compliance,
    validate_price_stock,
    process_input,
    process_output,
    sanitize_input,
    sanitize_output,
    is_safe_input,
    get_guard_summary,
)

__all__ = [
    # Input guards
    "InputGuardResult",
    "apply_input_guards",
    "detect_pii",
    "detect_injection",
    "mask_pii_in_response",
    # Output guards
    "OutputGuardResult",
    "apply_output_guards",
    "format_safe_response",
    # Pipeline
    "apply_guards",
    "check_policy_compliance",
    "validate_price_stock",
    "process_input",
    "process_output",
    "sanitize_input",
    "sanitize_output",
    "is_safe_input",
    "get_guard_summary",
]
