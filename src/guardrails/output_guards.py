"""출력 가드레일 모듈.

기능:
- 응답 품질 검증
- 민감 정보 누출 방지
- 응답 길이 제한
- 톤/말투 검증
- 환각(Hallucination) 기본 검증
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.guardrails.input_guards import mask_pii_in_response
from src.config import get_config


def _get_guardrails_config():
    """가드레일 설정 로드."""
    return get_config().guardrails


@dataclass
class OutputGuardResult:
    """출력 가드 결과."""

    ok: bool
    sanitized_response: str
    original_response: str
    warnings: List[str] = field(default_factory=list)
    modified: bool = False
    modifications: List[str] = field(default_factory=list)


def _get_sensitive_patterns() -> List[str]:
    """민감 정보 패턴 로드."""
    cfg = _get_guardrails_config()
    patterns = cfg.sensitive_patterns
    if patterns:
        return patterns

    # 기본값
    return [
        r"(/etc/|/var/|/home/|/root/|C:\\|D:\\)",
        r"(sk-[a-zA-Z0-9]{20,})",
        r"(api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_-]+)",
        r"(traceback|stack\s*trace|exception\s*in|error\s*at\s*line)",
    ]


def _get_inappropriate_patterns() -> List[str]:
    """부적절한 응답 패턴 로드."""
    cfg = _get_guardrails_config()
    patterns = cfg.inappropriate_patterns
    if patterns:
        return patterns

    # 기본값
    return [
        r"(저는\s*인간입니다|i\s*am\s*human|i\s*am\s*not\s*an?\s*(ai|bot))",
        r"(관리자\s*권한|admin\s*access|root\s*access)",
    ]


def _get_output_length_limits() -> Tuple[int, int]:
    """출력 길이 제한 로드."""
    cfg = _get_guardrails_config()
    return cfg.min_output_length, cfg.max_output_length


def _get_polite_endings() -> List[str]:
    """존댓말 어미 로드."""
    cfg = _get_guardrails_config()
    endings = cfg.polite_endings
    if endings:
        return endings
    return ["니다", "세요", "습니다", "십시오", "시죠", "시요"]


def _get_min_polite_ratio() -> float:
    """최소 존댓말 비율 로드."""
    cfg = _get_guardrails_config()
    return cfg.min_polite_ratio


def validate_response_length(text: str) -> tuple[bool, Optional[str]]:
    """응답 길이 검증."""
    min_length, max_length = _get_output_length_limits()

    if len(text) < min_length:
        return False, "응답이 비어있습니다."

    if len(text) > max_length:
        return False, f"응답이 너무 깁니다. (최대 {max_length}자)"

    return True, None


def detect_sensitive_info(text: str) -> tuple[bool, List[str]]:
    """민감 정보 누출 탐지."""
    detected = []
    text_lower = text.lower()
    sensitive_patterns = _get_sensitive_patterns()

    for pattern in sensitive_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            detected.append(pattern)

    return len(detected) > 0, detected


def detect_inappropriate_content(text: str) -> tuple[bool, List[str]]:
    """부적절한 응답 탐지."""
    detected = []
    text_lower = text.lower()
    inappropriate_patterns = _get_inappropriate_patterns()

    for pattern in inappropriate_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            detected.append(pattern)

    return len(detected) > 0, detected


def check_tone(text: str) -> tuple[bool, str]:
    """톤/말투 검증 (존댓말 체크)."""
    polite_endings = _get_polite_endings()
    min_polite_ratio = _get_min_polite_ratio()

    # 문장 끝 확인
    sentences = re.split(r"[.!?]", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return True, "확인할 문장 없음"

    polite_count = 0
    total_count = len(sentences)

    for sentence in sentences:
        if any(sentence.endswith(ending) for ending in polite_endings):
            polite_count += 1
        # '-요'로 끝나는 경우도 존댓말
        if sentence.endswith("요"):
            polite_count += 1

    polite_ratio = polite_count / total_count if total_count > 0 else 0

    if polite_ratio < min_polite_ratio:
        return False, f"존댓말 비율 낮음 ({polite_ratio:.0%})"

    return True, f"존댓말 비율 적정 ({polite_ratio:.0%})"


def validate_factual_consistency(
    response: str,
    context: Optional[Dict[str, Any]] = None
) -> tuple[bool, List[str]]:
    """사실 정합성 기본 검증.

    컨텍스트 데이터와 응답 내용의 일치 여부를 검증합니다.
    (완전한 환각 탐지는 어려우므로 기본 검증만 수행)
    """
    warnings = []

    if not context:
        return True, []

    # 주문 정보 검증
    if "order" in context or "orders" in context:
        order_data = context.get("order") or context.get("orders", [])
        if isinstance(order_data, dict):
            order_id = order_data.get("order_id", "")
            if order_id and order_id not in response:
                # 주문 ID가 응답에 없어도 괜찮음 (자연어 응답)
                pass

    # 가격 정보 검증 (숫자 패턴)
    if "total_amount" in str(context):
        # 컨텍스트의 금액과 응답의 금액 비교
        context_amounts = re.findall(r"(\d{1,3}(?:,\d{3})*)", str(context))
        response_amounts = re.findall(r"(\d{1,3}(?:,\d{3})*)", response)

        # 응답에 금액이 있지만 컨텍스트에 없는 경우
        for amt in response_amounts:
            if amt not in context_amounts and int(amt.replace(",", "")) > 1000:
                # 1000원 이상의 금액이 컨텍스트에 없으면 경고
                if amt not in str(context):
                    warnings.append(f"검증 필요: 금액 {amt}원이 컨텍스트에 없음")

    return len(warnings) == 0, warnings


def sanitize_response(text: str) -> tuple[str, List[str]]:
    """응답 정제.

    민감 정보, PII 등을 마스킹합니다.
    """
    modifications = []
    sensitive_patterns = _get_sensitive_patterns()

    # PII 마스킹
    sanitized = mask_pii_in_response(text)
    if sanitized != text:
        modifications.append("PII 마스킹 적용")

    # 민감 정보 제거/마스킹
    for pattern in sensitive_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
            modifications.append(f"민감 정보 마스킹: {pattern[:20]}...")

    return sanitized, modifications


def apply_output_guards(
    response: str,
    context: Optional[Dict[str, Any]] = None,
    check_factual: bool = True,
    check_tone_flag: bool = True,
) -> OutputGuardResult:
    """출력 가드 적용.

    Args:
        response: LLM 응답 텍스트
        context: 응답 생성에 사용된 컨텍스트 데이터
        check_factual: 사실 정합성 검증 여부
        check_tone_flag: 톤 검증 여부

    Returns:
        OutputGuardResult
    """
    warnings: List[str] = []
    modifications: List[str] = []

    # 1. 길이 검증
    length_ok, length_error = validate_response_length(response)
    if not length_ok:
        return OutputGuardResult(
            ok=False,
            sanitized_response="죄송합니다. 응답 생성 중 오류가 발생했습니다.",
            original_response=response,
            warnings=[length_error] if length_error else [],
        )

    # 2. 응답 정제 (PII, 민감 정보)
    sanitized, mods = sanitize_response(response)
    modifications.extend(mods)

    # 3. 부적절한 내용 탐지
    has_inappropriate, _ = detect_inappropriate_content(sanitized)
    if has_inappropriate:
        warnings.append("부적절한 응답 패턴 감지됨")

    # 4. 사실 정합성 검증
    if check_factual and context:
        factual_ok, factual_warnings = validate_factual_consistency(sanitized, context)
        if not factual_ok:
            warnings.extend(factual_warnings)

    # 5. 톤 검증
    if check_tone_flag:
        tone_ok, tone_msg = check_tone(sanitized)
        if not tone_ok:
            warnings.append(tone_msg)

    return OutputGuardResult(
        ok=True,  # 경고가 있어도 응답은 반환
        sanitized_response=sanitized,
        original_response=response,
        warnings=warnings,
        modified=len(modifications) > 0,
        modifications=modifications,
    )


def format_safe_response(
    response: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """안전한 응답 포맷팅.

    가드 적용 후 최종 응답을 반환합니다.
    """
    result = apply_output_guards(response, context)
    return result.sanitized_response
