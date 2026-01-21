"""의도 분류기 모듈.

LLM 기반 의도 분류를 지원하며, 실패 시 키워드 기반 폴백을 제공합니다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """의도 분류 결과."""

    intent: str
    sub_intent: Optional[str]
    payload: Dict[str, Any]
    confidence: str = "high"
    source: str = "keyword"  # "llm" or "keyword"
    reason: str = ""


def _get_intent_config():
    """의도 분류 설정 로드."""
    return get_config().intents


def _compile_order_pattern():
    """주문 ID 패턴 컴파일."""
    cfg = _get_intent_config()
    return re.compile(cfg.order_id_pattern)


def _extract_order_id(message: str) -> Optional[str]:
    """메시지에서 주문 ID 추출."""
    pattern = _compile_order_pattern()
    match = pattern.search(message)
    return match.group(0) if match else None


# ============================================
# 키워드 기반 의도 분류 (폴백)
# ============================================

def classify_intent_keyword(message: str) -> IntentResult:
    """키워드 기반 의도 분류 (기존 방식)."""
    cfg = _get_intent_config()
    intents_cfg = cfg.intents
    m = message.lower()
    order_id = _extract_order_id(message)

    # 주문 ID가 있으면 주문 의도 우선 체크
    if order_id:
        order_cfg = intents_cfg.get("order", {})
        sub_intents = order_cfg.get("sub_intents", {})

        # 취소
        cancel_cfg = sub_intents.get("cancel", {})
        cancel_keywords = cancel_cfg.get("keywords", ["취소"])
        if any(k in m for k in cancel_keywords):
            default_reason = cancel_cfg.get("default_reason", "사용자 요청")
            return IntentResult(
                intent="order",
                sub_intent="cancel",
                payload={"order_id": order_id, "reason": default_reason},
                confidence="high",
                source="keyword",
                reason="주문 ID + 취소 키워드 탐지"
            )

        # 상태
        status_cfg = sub_intents.get("status", {})
        status_keywords = status_cfg.get("keywords", ["상태", "배송", "어디", "어떻게"])
        if any(k in m for k in status_keywords):
            return IntentResult(
                intent="order",
                sub_intent="status",
                payload={"order_id": order_id},
                confidence="high",
                source="keyword",
                reason="주문 ID + 상태 키워드 탐지"
            )

        # 상세
        detail_cfg = sub_intents.get("detail", {})
        detail_keywords = detail_cfg.get("keywords", ["상세", "내역", "정보"])
        if any(k in m for k in detail_keywords):
            return IntentResult(
                intent="order",
                sub_intent="detail",
                payload={"order_id": order_id},
                confidence="high",
                source="keyword",
                reason="주문 ID + 상세 키워드 탐지"
            )

        # 주문 ID만 있고 다른 키워드가 없으면 상세 조회로 처리
        return IntentResult(
            intent="order",
            sub_intent="detail",
            payload={"order_id": order_id},
            confidence="medium",
            source="keyword",
            reason="주문 ID 탐지, 기본 상세 조회"
        )

    # 정책 질의 체크 (일반적인 정책/안내 질문)
    policy_cfg = intents_cfg.get("policy", {})
    policy_keywords = policy_cfg.get("keywords", ["정책", "faq", "알려", "어떻게", "방법", "규정"])

    # 일반적인 배송/교환/환불 정책 질문 패턴
    policy_question_patterns = ["얼마나", "며칠", "기간", "언제", "어디", "무엇", "뭐", "왜"]
    is_policy_question = any(p in m for p in policy_question_patterns)

    if any(k in m for k in policy_keywords) or is_policy_question:
        default_params = policy_cfg.get("default_params", {"top_k": 5})
        return IntentResult(
            intent="policy",
            sub_intent=None,
            payload={"query": message, **default_params},
            confidence="medium",
            source="keyword",
            reason="키워드 매칭: 정책 관련 키워드 탐지"
        )

    # 주문 관련 (주문 ID 없이)
    order_cfg = intents_cfg.get("order", {})
    order_keywords = order_cfg.get("keywords", ["주문", "배송", "취소"])
    if any(k in m for k in order_keywords):
        sub_intents = order_cfg.get("sub_intents", {})

        # 취소
        cancel_cfg = sub_intents.get("cancel", {})
        cancel_keywords = cancel_cfg.get("keywords", ["취소"])
        if any(k in m for k in cancel_keywords):
            default_reason = cancel_cfg.get("default_reason", "사용자 요청")
            return IntentResult(
                intent="order",
                sub_intent="cancel",
                payload={"order_id": order_id or "", "reason": default_reason},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 주문 취소"
            )

        # 상태
        status_cfg = sub_intents.get("status", {})
        status_keywords = status_cfg.get("keywords", ["상태", "배송", "어디"])
        if any(k in m for k in status_keywords):
            return IntentResult(
                intent="order",
                sub_intent="status",
                payload={"order_id": order_id or ""},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 배송 상태"
            )

        # 상세
        detail_cfg = sub_intents.get("detail", {})
        detail_keywords = detail_cfg.get("keywords", ["상세", "내역", "정보"])
        if any(k in m for k in detail_keywords):
            return IntentResult(
                intent="order",
                sub_intent="detail",
                payload={"order_id": order_id or ""},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 주문 상세"
            )

        # 목록 (기본값)
        list_cfg = sub_intents.get("list", {})
        default_limit = list_cfg.get("default_limit", 10)
        return IntentResult(
            intent="order",
            sub_intent="list",
            payload={"limit": default_limit},
            confidence="medium",
            source="keyword",
            reason="키워드 매칭: 주문 목록"
        )

    # 클레임 (환불/교환 요청)
    claim_cfg = intents_cfg.get("claim", {})
    claim_keywords = claim_cfg.get("keywords", ["환불", "교환", "불량", "클레임", "고장", "신청", "요청"])
    if any(k in m for k in claim_keywords):
        issue_types = claim_cfg.get("issue_types", {})
        issue_type = "other"
        for itype, itype_cfg in issue_types.items():
            type_keywords = itype_cfg.get("keywords", [])
            if any(k in m for k in type_keywords):
                issue_type = itype
                break
        return IntentResult(
            intent="claim",
            sub_intent=None,
            payload={
                "action": "create",
                "order_id": order_id or "",
                "issue_type": issue_type,
                "description": message
            },
            confidence="medium",
            source="keyword",
            reason=f"키워드 매칭: 클레임 ({issue_type})"
        )

    # 추천 의도 체크
    recommend_cfg = intents_cfg.get("recommend", {})
    recommend_keywords = recommend_cfg.get("keywords", [
        "추천", "비슷한", "유사한", "같은", "인기", "트렌드", "베스트",
        "함께", "같이", "많이", "뭐가", "어떤"
    ])
    if any(k in m for k in recommend_keywords):
        sub_intents = recommend_cfg.get("sub_intents", {})
        
        # 유사 상품
        similar_cfg = sub_intents.get("similar", {})
        similar_keywords = similar_cfg.get("keywords", ["비슷한", "유사한", "같은 종류", "이런 거"])
        if any(k in m for k in similar_keywords):
            # 메시지에서 상품 ID 추출 시도
            from .recommend_agent import extract_product_id_from_message
            product_id = extract_product_id_from_message(message) or ""
            return IntentResult(
                intent="recommend",
                sub_intent="similar",
                payload={"product_id": product_id, "query": message},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 유사 상품 추천"
            )
        
        # 함께 구매
        together_cfg = sub_intents.get("together", {})
        together_keywords = together_cfg.get("keywords", ["함께", "같이 사는", "같이 구매", "세트"])
        if any(k in m for k in together_keywords):
            from .recommend_agent import extract_product_id_from_message
            product_id = extract_product_id_from_message(message) or ""
            return IntentResult(
                intent="recommend",
                sub_intent="together",
                payload={"product_id": product_id, "query": message},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 함께 구매 추천"
            )
        
        # 인기/트렌딩
        trending_cfg = sub_intents.get("trending", {})
        trending_keywords = trending_cfg.get("keywords", ["인기", "트렌드", "베스트", "많이 팔리는", "핫한"])
        if any(k in m for k in trending_keywords):
            from .recommend_agent import extract_category_from_message
            category = extract_category_from_message(message)
            return IntentResult(
                intent="recommend",
                sub_intent="trending",
                payload={"category_id": category or "", "query": message},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 인기 상품 추천"
            )
        
        # 카테고리 추천
        category_cfg = sub_intents.get("category", {})
        category_keywords = category_cfg.get("keywords", ["카테고리", "분야", "종류"])
        if any(k in m for k in category_keywords):
            from .recommend_agent import extract_category_from_message
            category = extract_category_from_message(message)
            return IntentResult(
                intent="recommend",
                sub_intent="category",
                payload={"category_id": category or "", "query": message},
                confidence="medium",
                source="keyword",
                reason="키워드 매칭: 카테고리 추천"
            )
        
        # 기본: 개인화 추천
        return IntentResult(
            intent="recommend",
            sub_intent="personal",
            payload={"query": message},
            confidence="medium",
            source="keyword",
            reason="키워드 매칭: 개인화 추천"
        )

    # 일반 대화
    general_cfg = intents_cfg.get("general", {})
    general_keywords = general_cfg.get("keywords", ["안녕", "고마워", "감사", "도움"])
    if any(k in m for k in general_keywords):
        return IntentResult(
            intent="general",
            sub_intent=None,
            payload={"message": message},
            confidence="medium",
            source="keyword",
            reason="키워드 매칭: 일반 대화"
        )

    return IntentResult(
        intent=cfg.fallback_intent,
        sub_intent=None,
        payload={},
        confidence="low",
        source="keyword",
        reason="키워드 매칭 실패"
    )


# ============================================
# LLM 기반 의도 분류
# ============================================

async def classify_intent_llm(message: str) -> Optional[IntentResult]:
    """LLM 기반 의도 분류.

    Returns:
        IntentResult or None if LLM call fails
    """
    from src.llm.client import get_client, load_prompt

    cfg = _get_intent_config()
    llm_cfg = cfg.llm_classification

    if not llm_cfg.enabled:
        return None

    try:
        client = get_client()
        prompt = load_prompt("intent_classification")

        if not prompt:
            logger.warning("의도 분류 프롬프트를 찾을 수 없습니다.")
            return None

        messages = [{"role": "user", "content": message}]
        response = await client.chat(messages, system_prompt=prompt)

        # JSON 파싱
        result = _parse_llm_response(response, message)
        if result:
            result.source = "llm"
            logger.info(f"LLM 의도 분류 성공: {result.intent}/{result.sub_intent} (confidence: {result.confidence})")
            return result

    except Exception as e:
        logger.warning(f"LLM 의도 분류 실패: {e}")
        return None

    return None


def _parse_llm_response(response: str, original_message: str) -> Optional[IntentResult]:
    """LLM 응답 파싱."""
    try:
        # JSON 블록 추출
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            logger.warning(f"LLM 응답에서 JSON을 찾을 수 없습니다: {response[:100]}")
            return None

        data = json.loads(json_match.group())

        intent = data.get("intent", "unknown")
        sub_intent = data.get("sub_intent")
        confidence = data.get("confidence", "medium")
        entities = data.get("entities", {})
        reason = data.get("reason", "")

        # sub_intent가 "null" 문자열이면 None으로 변환
        if sub_intent == "null" or sub_intent == "":
            sub_intent = None

        # 신뢰도 검증
        cfg = _get_intent_config()
        threshold = cfg.llm_classification.confidence_threshold
        confidence_order = {"low": 0, "medium": 1, "high": 2}

        if confidence_order.get(confidence, 0) < confidence_order.get(threshold, 1):
            logger.info(f"LLM 신뢰도 부족: {confidence} < {threshold}")
            return None

        # 의도별 payload 구성
        payload = _build_payload(intent, sub_intent, entities, original_message)

        return IntentResult(
            intent=intent,
            sub_intent=sub_intent,
            payload=payload,
            confidence=confidence,
            source="llm",
            reason=reason
        )

    except json.JSONDecodeError as e:
        logger.warning(f"LLM 응답 JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM 응답 처리 실패: {e}")
        return None


def _build_payload(
    intent: str,
    sub_intent: Optional[str],
    entities: Dict[str, Any],
    original_message: str
) -> Dict[str, Any]:
    """의도별 payload 구성."""
    order_id = entities.get("order_id") or ""
    if order_id == "null":
        order_id = ""

    issue_type = entities.get("issue_type") or "other"
    if issue_type == "null":
        issue_type = "other"

    query = entities.get("query") or original_message

    if intent == "policy":
        cfg = _get_intent_config()
        policy_cfg = cfg.intents.get("policy", {})
        default_params = policy_cfg.get("default_params", {"top_k": 5})
        return {"query": query, **default_params}

    elif intent == "order":
        if sub_intent == "cancel":
            return {"order_id": order_id, "reason": "사용자 요청"}
        elif sub_intent in ("status", "detail"):
            return {"order_id": order_id}
        else:  # list
            cfg = _get_intent_config()
            order_cfg = cfg.intents.get("order", {})
            sub_intents = order_cfg.get("sub_intents", {})
            list_cfg = sub_intents.get("list", {})
            payload = {"limit": list_cfg.get("default_limit", 10)}
            include_items = entities.get("include_items")
            if isinstance(include_items, bool):
                payload["include_items"] = include_items
            return payload

    elif intent == "claim":
        return {
            "action": "create",
            "order_id": order_id,
            "issue_type": issue_type,
            "description": original_message
        }

    elif intent == "general":
        return {"message": original_message}

    return {}


# ============================================
# 통합 의도 분류 함수
# ============================================

async def classify_intent_async(message: str) -> IntentResult:
    """비동기 의도 분류 (LLM 우선, 키워드 폴백)."""
    cfg = _get_intent_config()
    llm_cfg = cfg.llm_classification

    logger.info(f"[intent_classifier] 분류 시작: '{message[:50]}...'")

    # LLM 분류 시도
    if llm_cfg.enabled:
        logger.debug("[intent_classifier] LLM 분류 시도...")
        result = await classify_intent_llm(message)
        if result:
            logger.info(
                f"[intent_classifier] LLM 분류 성공: "
                f"intent={result.intent}, sub_intent={result.sub_intent}, "
                f"confidence={result.confidence}"
            )
            return result

        logger.info("[intent_classifier] LLM 분류 실패, 키워드 폴백 확인...")

        # 폴백 설정 확인
        if not llm_cfg.fallback_to_keyword:
            logger.warning("[intent_classifier] 키워드 폴백 비활성화, unknown 반환")
            return IntentResult(
                intent="unknown",
                sub_intent=None,
                payload={},
                confidence="low",
                source="llm",
                reason="LLM 분류 실패, 폴백 비활성화"
            )

    # 키워드 기반 폴백
    logger.info("[intent_classifier] 키워드 기반 분류 수행...")
    result = classify_intent_keyword(message)
    logger.info(
        f"[intent_classifier] 키워드 분류 완료: "
        f"intent={result.intent}, sub_intent={result.sub_intent}, "
        f"confidence={result.confidence}, reason={result.reason}"
    )
    return result


def classify_intent(message: str) -> Tuple[str, Optional[str], Dict[str, Any]]:
    """동기 의도 분류 (기존 API 호환).

    Returns:
        (intent, sub_intent, payload) 튜플
    """
    # 동기 함수에서는 키워드 분류만 사용
    result = classify_intent_keyword(message)
    return (result.intent, result.sub_intent, result.payload)
