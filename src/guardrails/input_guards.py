"""입력 가드레일 모듈.

기능:
- PII(개인정보) 탐지 및 마스킹
- 프롬프트 인젝션 탐지 및 차단
- 입력 길이 제한
- 금지어/욕설 필터링
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.config import get_config


def _get_guardrails_config():
    """가드레일 설정 로드."""
    return get_config().guardrails


@dataclass
class InputGuardResult:
    """입력 가드 결과."""

    ok: bool
    sanitized_text: str
    original_text: str
    warnings: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None
    pii_detected: List[Dict[str, str]] = field(default_factory=list)


def _get_pii_patterns() -> Dict[str, Dict[str, str]]:
    """PII 패턴 로드 (설정 기반, 기본값 폴백)."""
    cfg = _get_guardrails_config()
    patterns = cfg.pii_patterns
    if patterns:
        return patterns

    # 기본값 (설정 파일 없는 경우)
    return {
        "phone_kr": {
            "pattern": r"(01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4})",
            "mask": "***-****-****",
            "description": "휴대폰 번호",
        },
        "email": {
            "pattern": r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
            "mask": "***@***.***",
            "description": "이메일 주소",
        },
        "rrn": {
            "pattern": r"(\d{6}[-.\s]?[1-4]\d{6})",
            "mask": "******-*******",
            "description": "주민등록번호",
        },
        "card_number": {
            "pattern": r"(\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4})",
            "mask": "****-****-****-****",
            "description": "카드 번호",
        },
    }


def _get_injection_patterns() -> List[str]:
    """인젝션 패턴 로드 (설정 기반, 기본값 폴백)."""
    cfg = _get_guardrails_config()
    patterns = cfg.injection_patterns
    if patterns:
        return patterns

    # 기본값
    return [
        r"(ignore|disregard|forget)\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)",
        r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as)",
        r"jailbreak",
        r"(이전|위의|모든)\s*(지시|명령|규칙|프롬프트).*?(무시|잊어|버려)",
        r"(disable|bypass)\s+(safety|guardrails|filters)",
        r"(reveal|show)\s+(system\s+prompt|secrets?)",
        r"(exfiltrate|export)\s+(data|keys|credentials)",
        r"RUN\s+|import\s+os|subprocess|eval\(\)|exec\(\)",
    ]


def _get_blocked_words() -> List[str]:
    """금지어 로드 (설정 기반, 기본값 폴백)."""
    cfg = _get_guardrails_config()
    words = cfg.blocked_words
    if words:
        return words
    return [
        "씨발", "씨팔", "시발", "좆", "개새끼", "개새", "병신", "ㅅㅂ", "ㅂㅅ", "꺼져", "닥쳐",
        "fuck", "shit", "bitch", "asshole", "bastard",
    ]


def _get_length_limits() -> Tuple[int, int]:
    """길이 제한 로드."""
    cfg = _get_guardrails_config()
    return cfg.min_input_length, cfg.max_input_length


def detect_pii(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """PII 탐지 및 마스킹.

    Args:
        text: 입력 텍스트

    Returns:
        (마스킹된 텍스트, 탐지된 PII 목록)
    """
    masked_text = text
    detected = []
    pii_patterns = _get_pii_patterns()

    for pii_type, config in pii_patterns.items():
        pattern = config["pattern"]
        matches = re.findall(pattern, masked_text)

        for match in matches:
            detected.append({
                "type": pii_type,
                "description": config.get("description", pii_type),
                "masked": config.get("mask", "***"),
            })
            # 마스킹 적용
            masked_text = masked_text.replace(match, config.get("mask", "***"))

    return masked_text, detected


def detect_injection(text: str) -> Tuple[bool, Optional[str]]:
    """프롬프트 인젝션 탐지.

    Args:
        text: 입력 텍스트

    Returns:
        (인젝션 탐지 여부, 매칭된 패턴)
    """
    text_lower = text.lower()
    injection_patterns = _get_injection_patterns()

    for pattern in injection_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, pattern

    return False, None


def detect_blocked_words(text: str) -> Tuple[bool, List[str]]:
    """금지어 탐지.

    Args:
        text: 입력 텍스트

    Returns:
        (금지어 포함 여부, 탐지된 금지어 목록)
    """
    found = []
    text_lower = text.lower()
    blocked_words = _get_blocked_words()

    for word in blocked_words:
        if word.lower() in text_lower:
            found.append(word)

    return len(found) > 0, found


def validate_length(text: str) -> Tuple[bool, Optional[str]]:
    """입력 길이 검증.

    Args:
        text: 입력 텍스트

    Returns:
        (유효 여부, 오류 메시지)
    """
    min_length, max_length = _get_length_limits()

    if len(text) < min_length:
        return False, "입력이 너무 짧습니다."

    if len(text) > max_length:
        return False, f"입력이 너무 깁니다. (최대 {max_length}자)"

    return True, None


def apply_input_guards(text: str, strict_mode: bool = False) -> InputGuardResult:
    """입력 가드 적용.

    Args:
        text: 사용자 입력 텍스트
        strict_mode: 엄격 모드 (인젝션/금지어 시 차단)

    Returns:
        InputGuardResult
    """
    warnings: List[str] = []
    blocked = False
    block_reason = None

    # 1. 길이 검증
    length_ok, length_error = validate_length(text)
    if not length_ok:
        return InputGuardResult(
            ok=False,
            sanitized_text="",
            original_text=text,
            blocked=True,
            block_reason=length_error,
        )

    # 2. PII 탐지 및 마스킹
    sanitized_text, pii_detected = detect_pii(text)
    if pii_detected:
        warnings.append(f"개인정보 {len(pii_detected)}건 탐지 및 마스킹됨")

    # 3. 프롬프트 인젝션 탐지
    injection_detected, injection_pattern = detect_injection(text)
    if injection_detected:
        if strict_mode:
            blocked = True
            block_reason = "보안 위반이 감지되었습니다."
        else:
            warnings.append("의심스러운 입력 패턴 감지됨")

    # 4. 금지어 탐지
    has_blocked_words, blocked_words = detect_blocked_words(text)
    if has_blocked_words:
        if strict_mode:
            blocked = True
            block_reason = "부적절한 표현이 포함되어 있습니다."
        else:
            warnings.append(f"부적절한 표현 {len(blocked_words)}건 감지됨")

    return InputGuardResult(
        ok=not blocked and length_ok,
        sanitized_text=sanitized_text,
        original_text=text,
        warnings=warnings,
        blocked=blocked,
        block_reason=block_reason,
        pii_detected=pii_detected,
    )


def mask_pii_in_response(text: str) -> str:
    """응답에서 PII 마스킹 (출력 가드용).

    Args:
        text: 응답 텍스트

    Returns:
        마스킹된 텍스트
    """
    masked, _ = detect_pii(text)
    return masked
