"""의도 분류기 테스트."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.nodes.intent_classifier import (
    IntentResult,
    classify_intent,
    classify_intent_keyword,
    classify_intent_async,
    classify_intent_llm,
    _extract_order_id,
    _parse_llm_response,
    _build_payload,
)


class TestIntentResult:
    """IntentResult 데이터클래스 테스트."""

    def test_create_basic(self):
        result = IntentResult(
            intent="order",
            sub_intent="list",
            payload={"limit": 10}
        )
        assert result.intent == "order"
        assert result.sub_intent == "list"
        assert result.payload == {"limit": 10}
        assert result.confidence == "high"  # 기본값
        assert result.source == "keyword"   # 기본값
        assert result.reason == ""          # 기본값

    def test_create_with_all_fields(self):
        result = IntentResult(
            intent="policy",
            sub_intent=None,
            payload={"query": "환불"},
            confidence="medium",
            source="llm",
            reason="LLM 분류"
        )
        assert result.intent == "policy"
        assert result.sub_intent is None
        assert result.confidence == "medium"
        assert result.source == "llm"
        assert result.reason == "LLM 분류"


class TestExtractOrderId:
    """주문 ID 추출 테스트."""

    def test_extract_order_id_basic(self):
        assert _extract_order_id("ORD-12345 주문 취소해주세요") == "ORD-12345"

    def test_extract_order_id_with_letters(self):
        assert _extract_order_id("ORD-abc123 상태 알려줘") == "ORD-abc123"

    def test_extract_order_id_not_found(self):
        assert _extract_order_id("주문 취소해주세요") is None

    def test_extract_order_id_multiple(self):
        # 첫 번째 매칭 반환
        result = _extract_order_id("ORD-111 하고 ORD-222")
        assert result == "ORD-111"


class TestClassifyIntentKeyword:
    """키워드 기반 의도 분류 테스트."""

    def test_policy_intent(self):
        result = classify_intent_keyword("환불 정책 알려줘")
        assert result.intent == "policy"
        assert result.source == "keyword"
        assert "query" in result.payload

    def test_policy_intent_faq(self):
        result = classify_intent_keyword("FAQ 보여줘")
        assert result.intent == "policy"

    def test_order_list(self):
        result = classify_intent_keyword("주문 목록 보여줘")
        assert result.intent == "order"
        assert result.sub_intent == "list"

    def test_order_status(self):
        # "알려줘"가 정책 키워드에 포함되므로 다른 표현 사용
        result = classify_intent_keyword("ORD-12345 배송 상태 확인")
        assert result.intent == "order"
        assert result.sub_intent == "status"
        assert result.payload.get("order_id") == "ORD-12345"

    def test_order_cancel(self):
        result = classify_intent_keyword("ORD-ABC 주문 취소해주세요")
        assert result.intent == "order"
        assert result.sub_intent == "cancel"
        assert result.payload.get("order_id") == "ORD-ABC"

    def test_order_detail(self):
        result = classify_intent_keyword("ORD-999 주문 상세 내역")
        assert result.intent == "order"
        assert result.sub_intent == "detail"
        assert result.payload.get("order_id") == "ORD-999"

    def test_claim_refund(self):
        result = classify_intent_keyword("환불 신청합니다")
        assert result.intent == "claim"
        assert result.payload.get("issue_type") == "refund"

    def test_claim_exchange(self):
        result = classify_intent_keyword("교환 요청이요")
        assert result.intent == "claim"
        assert result.payload.get("issue_type") == "exchange"

    def test_claim_defect(self):
        result = classify_intent_keyword("불량품이에요 고장났어요")
        assert result.intent == "claim"
        assert result.payload.get("issue_type") == "defect"

    def test_general_greeting(self):
        result = classify_intent_keyword("안녕하세요")
        assert result.intent == "general"

    def test_general_thanks(self):
        result = classify_intent_keyword("감사합니다")
        assert result.intent == "general"

    def test_unknown_intent(self):
        result = classify_intent_keyword("asdfasdfasdf")
        assert result.intent == "unknown"
        assert result.confidence == "low"


class TestSyncClassifyIntent:
    """동기 의도 분류 함수 테스트 (API 호환성)."""

    def test_returns_tuple(self):
        intent, sub_intent, payload = classify_intent("주문 목록")
        assert isinstance(intent, str)
        assert sub_intent is None or isinstance(sub_intent, str)
        assert isinstance(payload, dict)

    def test_policy_intent(self):
        intent, sub_intent, payload = classify_intent("정책 알려줘")
        assert intent == "policy"
        assert "query" in payload

    def test_order_intent(self):
        intent, sub_intent, payload = classify_intent("주문 상태")
        assert intent == "order"


class TestParseLLMResponse:
    """LLM 응답 파싱 테스트."""

    def test_parse_valid_json(self):
        response = '''
        ```json
        {
            "intent": "order",
            "sub_intent": "cancel",
            "confidence": "high",
            "entities": {"order_id": "ORD-123"},
            "reason": "주문 취소 요청"
        }
        ```
        '''
        result = _parse_llm_response(response, "ORD-123 취소해주세요")
        assert result is not None
        assert result.intent == "order"
        assert result.sub_intent == "cancel"
        assert result.confidence == "high"

    def test_parse_json_without_backticks(self):
        response = '''
        {
            "intent": "policy",
            "sub_intent": null,
            "confidence": "medium",
            "entities": {"query": "환불"},
            "reason": "정책 문의"
        }
        '''
        result = _parse_llm_response(response, "환불 정책")
        assert result is not None
        assert result.intent == "policy"
        assert result.sub_intent is None

    def test_parse_null_sub_intent_string(self):
        response = '{"intent": "general", "sub_intent": "null", "confidence": "high", "entities": {}, "reason": ""}'
        result = _parse_llm_response(response, "안녕")
        assert result is not None
        assert result.sub_intent is None

    def test_parse_invalid_json(self):
        response = "This is not JSON"
        result = _parse_llm_response(response, "test")
        assert result is None

    def test_parse_low_confidence_filtered(self):
        # 기본 threshold가 medium이므로 low confidence는 필터링됨
        response = '{"intent": "order", "sub_intent": null, "confidence": "low", "entities": {}, "reason": ""}'
        result = _parse_llm_response(response, "test")
        assert result is None


class TestBuildPayload:
    """페이로드 빌드 테스트."""

    def test_build_policy_payload(self):
        payload = _build_payload("policy", None, {"query": "환불"}, "환불 정책 알려줘")
        assert "query" in payload
        assert "top_k" in payload

    def test_build_order_cancel_payload(self):
        payload = _build_payload("order", "cancel", {"order_id": "ORD-123"}, "취소")
        assert payload.get("order_id") == "ORD-123"
        assert "reason" in payload

    def test_build_order_status_payload(self):
        payload = _build_payload("order", "status", {"order_id": "ORD-456"}, "상태")
        assert payload.get("order_id") == "ORD-456"

    def test_build_order_list_payload(self):
        payload = _build_payload("order", "list", {}, "목록")
        assert "limit" in payload

    def test_build_claim_payload(self):
        payload = _build_payload("claim", None, {"order_id": "ORD-789", "issue_type": "refund"}, "환불 신청")
        assert payload.get("action") == "create"
        assert payload.get("order_id") == "ORD-789"
        assert payload.get("issue_type") == "refund"

    def test_build_general_payload(self):
        payload = _build_payload("general", None, {}, "안녕하세요")
        assert payload.get("message") == "안녕하세요"

    def test_build_null_order_id_handling(self):
        payload = _build_payload("order", "status", {"order_id": "null"}, "상태")
        assert payload.get("order_id") == ""


class TestClassifyIntentAsync:
    """비동기 의도 분류 테스트."""

    @pytest.mark.asyncio
    async def test_fallback_to_keyword_when_llm_disabled(self):
        """LLM 비활성화 시 키워드 방식으로 폴백."""
        # classify_intent_llm을 직접 mock하여 None 반환하도록 함
        with patch("src.agents.nodes.intent_classifier.classify_intent_llm") as mock_llm:
            mock_llm.return_value = None  # LLM 비활성화 시뮬레이션

            result = await classify_intent_async("정책 문의합니다")
            assert result.source == "keyword"

    @pytest.mark.asyncio
    async def test_fallback_when_llm_fails(self):
        """LLM 실패 시 키워드 방식으로 폴백."""
        with patch("src.agents.nodes.intent_classifier.classify_intent_llm") as mock_llm:
            mock_llm.return_value = None  # LLM 실패 시뮬레이션

            result = await classify_intent_async("주문 목록")
            assert result.source == "keyword"
            assert result.intent == "order"


class TestClassifyIntentLLM:
    """LLM 기반 의도 분류 테스트."""

    @pytest.mark.asyncio
    async def test_llm_disabled_returns_none(self):
        """LLM 비활성화 시 None 반환."""
        with patch("src.agents.nodes.intent_classifier._get_intent_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.llm_classification.enabled = False
            mock_config.return_value = mock_cfg

            result = await classify_intent_llm("테스트")
            assert result is None

    @pytest.mark.asyncio
    async def test_llm_success(self):
        """LLM 성공 시 IntentResult 반환."""
        with patch("src.agents.nodes.intent_classifier._get_intent_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.llm_classification.enabled = True
            mock_cfg.llm_classification.confidence_threshold = "medium"
            mock_cfg.intents = {"policy": {"default_params": {"top_k": 5}}}
            mock_config.return_value = mock_cfg

            # get_client와 load_prompt는 classify_intent_llm 내에서 import되므로
            # src.llm.client 모듈을 직접 patch
            with patch("src.llm.client.get_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_client.chat.return_value = json.dumps({
                    "intent": "policy",
                    "sub_intent": None,
                    "confidence": "high",
                    "entities": {"query": "환불 정책"},
                    "reason": "정책 문의"
                })
                mock_get_client.return_value = mock_client

                with patch("src.llm.client.load_prompt") as mock_load_prompt:
                    mock_load_prompt.return_value = "테스트 프롬프트"

                    result = await classify_intent_llm("환불 정책 알려줘")

                    assert result is not None
                    assert result.intent == "policy"
                    assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self):
        """LLM 예외 발생 시 None 반환."""
        with patch("src.agents.nodes.intent_classifier._get_intent_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.llm_classification.enabled = True
            mock_config.return_value = mock_cfg

            with patch("src.llm.client.get_client") as mock_get_client:
                mock_get_client.side_effect = Exception("API Error")

                result = await classify_intent_llm("테스트")
                assert result is None
