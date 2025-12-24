"""가드레일 파이프라인 (PoC).

기능:
- 입력 검증: PII 마스킹, 프롬프트 인젝션 방어, 길이 제한
- 출력 검증: 민감 정보 필터링, 톤 검증, 사실 정합성 체크
- 가격/재고 검증: Mock CSV 데이터와 일치 확인
- 정책 준수 체크: 응답이 정책과 일치하는지 검증

사용:
- orchestrator에서 입/출력 시 apply_input_guards(), apply_output_guards() 호출
- 최종 응답에 guard 필드 추가하여 반환
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.mock_system.storage.csv_repository import CSVRepository
from src.mock_system.storage.interfaces import CsvRepoConfig

from .input_guards import InputGuardResult, apply_input_guards
from .output_guards import OutputGuardResult, apply_output_guards


def _products_repo() -> CSVRepository:
    """제품 저장소 인스턴스."""
    return CSVRepository(
        CsvRepoConfig(
            data_dir="data/mock_csv",
            filename="products_cache.csv",
            key_field="product_id"
        )
    )


def validate_price_stock(resp: Dict[str, Any]) -> Dict[str, Any]:
    """가격/재고 검증.

    응답에 포함된 상품 가격/재고가 Mock CSV와 일치하는지 점검합니다.
    """
    repo = _products_repo()
    mismatches: List[Dict[str, Any]] = []

    def check_item(it: Dict[str, Any]) -> None:
        pid = str(it.get("product_id") or "")
        if not pid:
            return
        prod = repo.get_by_id(pid)
        if not prod:
            return
        price_resp = str(it.get("price") or "")
        price_db = str(prod.get("price") or "")
        stock_resp = str(it.get("stock_quantity") or "")
        stock_db = str(prod.get("stock_quantity") or "")
        item_mismatch: Dict[str, Any] = {"product_id": pid}
        has = False
        if price_resp and price_db and price_resp != price_db:
            item_mismatch["price_resp"] = price_resp
            item_mismatch["price_db"] = price_db
            has = True
        if stock_resp and stock_db and stock_resp != stock_db:
            item_mismatch["stock_resp"] = stock_resp
            item_mismatch["stock_db"] = stock_db
            has = True
        if has:
            mismatches.append(item_mismatch)

    # 주문 상세 응답
    if "detail" in resp:
        for it in resp["detail"].get("items", []):
            if isinstance(it, dict):
                check_item(it)

    return {
        "ok": len(mismatches) == 0,
        "mismatches": mismatches,
    }


# 정책 관련 키워드 매핑
POLICY_KEYWORDS = {
    "refund": ["환불", "반품", "취소", "교환", "7일", "수령"],
    "shipping": ["배송", "택배", "영업일", "발송", "도착", "무료배송", "배송비"],
    "payment": ["결제", "카드", "할부", "무이자", "페이", "계좌이체"],
    "membership": ["회원", "등급", "VIP", "적립", "포인트", "쿠폰"],
    "privacy": ["개인정보", "정보보호", "동의", "수집", "이용"],
}

# 금지된 응답 패턴 (정책 위반)
POLICY_VIOLATIONS = [
    # 잘못된 환불 기간
    (r"(\d+)일\s*이내.*환불", lambda m: int(m.group(1)) > 30, "환불 기간 30일 초과 불가"),
    # 100% 환불 약속 (조건 없이)
    (r"100%\s*환불", lambda m: True, "무조건 100% 환불 약속은 정책 위반"),
    # 즉시 처리 약속
    (r"즉시\s*(환불|입금|처리)", lambda m: True, "즉시 처리 약속은 정책 위반"),
]


def check_policy_compliance(
    resp: Dict[str, Any],
    response_text: Optional[str] = None,
) -> Dict[str, Any]:
    """정책 준수 체크.

    Args:
        resp: 응답 데이터 (hits 필드 포함 가능)
        response_text: LLM 응답 텍스트

    Returns:
        정책 준수 검증 결과
    """
    result: Dict[str, Any] = {
        "has_policy_context": False,
        "policy_types_matched": [],
        "violations": [],
        "ok": True,
    }

    # 1. 정책 컨텍스트 존재 여부
    hits = resp.get("hits", [])
    if hits:
        result["has_policy_context"] = True
        result["policy_count"] = len(hits)

        # 어떤 정책 유형이 매칭되었는지 확인
        for hit in hits:
            title = hit.get("title", "").lower()
            content = hit.get("content", "").lower()
            text = title + " " + content

            for policy_type, keywords in POLICY_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    if policy_type not in result["policy_types_matched"]:
                        result["policy_types_matched"].append(policy_type)

    # 2. 응답 텍스트 정책 위반 검사
    if response_text:
        for pattern, condition, message in POLICY_VIOLATIONS:
            matches = re.finditer(pattern, response_text)
            for match in matches:
                if condition(match):
                    result["violations"].append({
                        "pattern": pattern,
                        "matched_text": match.group(0),
                        "message": message,
                    })
                    result["ok"] = False

    # 3. 정책 응답에 근거가 없는 경우 경고
    if response_text and not result["has_policy_context"]:
        # 정책 관련 키워드가 응답에 있지만 정책 컨텍스트가 없는 경우
        policy_keywords_in_response = []
        for policy_type, keywords in POLICY_KEYWORDS.items():
            if any(kw in response_text for kw in keywords):
                policy_keywords_in_response.append(policy_type)

        if policy_keywords_in_response:
            result["warning"] = "응답에 정책 관련 내용이 있지만 정책 검색 결과가 없음"
            result["policy_keywords_in_response"] = policy_keywords_in_response

    return result


def apply_guards(
    resp: Dict[str, Any],
    response_text: Optional[str] = None,
) -> Dict[str, Any]:
    """전체 가드 적용.

    Args:
        resp: 응답 데이터
        response_text: LLM 응답 텍스트 (별도 전달 시)

    Returns:
        guard 필드가 추가된 응답
    """
    guards: Dict[str, Any] = {}

    # 응답 텍스트 추출
    text = response_text or resp.get("response", "")

    # 1. 가격/재고 검증
    try:
        guards["price_stock"] = validate_price_stock(resp)
    except Exception as e:
        guards["price_stock_error"] = str(e)

    # 2. 정책 준수 체크
    try:
        guards["policy"] = check_policy_compliance(resp, text)
    except Exception as e:
        guards["policy_error"] = str(e)

    # 3. 출력 가드 (응답 텍스트가 있는 경우)
    if text:
        try:
            output_result = apply_output_guards(text, context=resp)
            guards["output"] = {
                "ok": output_result.ok,
                "modified": output_result.modified,
                "warnings": output_result.warnings,
                "modifications": output_result.modifications,
            }
            # 정제된 응답으로 교체
            if output_result.modified:
                resp = dict(resp)
                resp["response"] = output_result.sanitized_response
        except Exception as e:
            guards["output_error"] = str(e)

    out = dict(resp)
    out["guard"] = guards
    return out


def process_input(
    user_input: str,
    strict_mode: bool = False,
) -> InputGuardResult:
    """입력 처리.

    사용자 입력에 대해 가드레일을 적용합니다.

    Args:
        user_input: 사용자 입력 텍스트
        strict_mode: 엄격 모드

    Returns:
        InputGuardResult
    """
    return apply_input_guards(user_input, strict_mode=strict_mode)


def process_output(
    response: str,
    context: Optional[Dict[str, Any]] = None,
) -> OutputGuardResult:
    """출력 처리.

    LLM 응답에 대해 가드레일을 적용합니다.

    Args:
        response: LLM 응답 텍스트
        context: 컨텍스트 데이터

    Returns:
        OutputGuardResult
    """
    return apply_output_guards(response, context=context)


# 편의를 위한 단순화 함수들
def sanitize_input(text: str) -> str:
    """입력 텍스트 정제 (PII 마스킹)."""
    result = apply_input_guards(text)
    return result.sanitized_text


def sanitize_output(text: str, context: Optional[Dict[str, Any]] = None) -> str:
    """출력 텍스트 정제."""
    result = apply_output_guards(text, context=context)
    return result.sanitized_response


def is_safe_input(text: str) -> bool:
    """입력이 안전한지 확인."""
    result = apply_input_guards(text, strict_mode=True)
    return result.ok and not result.blocked


def get_guard_summary(guards: Dict[str, Any]) -> str:
    """가드 결과 요약 문자열 반환."""
    issues = []

    if not guards.get("price_stock", {}).get("ok", True):
        issues.append("가격/재고 불일치")

    if not guards.get("policy", {}).get("ok", True):
        violations = guards.get("policy", {}).get("violations", [])
        issues.append(f"정책 위반 {len(violations)}건")

    if guards.get("output", {}).get("warnings"):
        warnings = guards.get("output", {}).get("warnings", [])
        issues.append(f"출력 경고 {len(warnings)}건")

    if not issues:
        return "모든 가드 통과"

    return ", ".join(issues)
