"""테스트 시나리오 정의.

에이전트 평가를 위한 테스트 시나리오를 정의합니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestScenario:
    """테스트 시나리오."""

    id: str
    name: str
    category: str  # order, claim, policy, product
    input_message: str
    expected_intent: str
    expected_sub_intent: Optional[str] = None
    expected_entities: Dict[str, Any] = field(default_factory=dict)
    expected_response_contains: List[str] = field(default_factory=list)
    expected_response_not_contains: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    difficulty: str = "medium"  # easy, medium, hard
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "input_message": self.input_message,
            "expected_intent": self.expected_intent,
            "expected_sub_intent": self.expected_sub_intent,
            "expected_entities": self.expected_entities,
            "expected_response_contains": self.expected_response_contains,
            "expected_response_not_contains": self.expected_response_not_contains,
            "context": self.context,
            "difficulty": self.difficulty,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestScenario":
        """딕셔너리에서 생성."""
        return cls(**data)


# 기본 테스트 시나리오
DEFAULT_SCENARIOS: List[TestScenario] = [
    # ===== 주문 관련 =====
    TestScenario(
        id="order_001",
        name="주문 목록 조회",
        category="order",
        input_message="내 주문 내역 보여줘",
        expected_intent="order",
        expected_sub_intent="list",
        expected_response_contains=["주문"],
        difficulty="easy",
        tags=["order", "list"],
    ),
    TestScenario(
        id="order_002",
        name="주문 상태 확인",
        category="order",
        input_message="ORD_20250927_0001 주문 상태가 어떻게 돼?",
        expected_intent="order",
        expected_sub_intent="status",
        expected_entities={"order_id": "ORD_20250927_0001"},
        expected_response_contains=["상태"],
        context={"user_id": "user_037"},  # 해당 주문 소유자
        difficulty="easy",
        tags=["order", "status"],
    ),
    TestScenario(
        id="order_003",
        name="주문 상세 조회",
        category="order",
        input_message="ORD_20250927_0001 주문 상세 정보 알려줘",
        expected_intent="order",
        expected_sub_intent="detail",
        expected_entities={"order_id": "ORD_20250927_0001"},
        expected_response_contains=["주문"],
        context={"user_id": "user_037"},  # 해당 주문 소유자
        difficulty="easy",
        tags=["order", "detail"],
    ),
    TestScenario(
        id="order_004",
        name="주문 취소 요청",
        category="order",
        input_message="ORD_20250927_0001 주문 취소하고 싶어요",
        expected_intent="order",
        expected_sub_intent="cancel",
        expected_entities={"order_id": "ORD_20250927_0001"},
        expected_response_contains=["취소"],
        difficulty="medium",
        tags=["order", "cancel"],
    ),
    TestScenario(
        id="order_005",
        name="주문번호 없이 취소",
        category="order",
        input_message="주문 취소하고 싶은데요",
        expected_intent="order",
        expected_sub_intent="cancel",
        expected_response_contains=["주문번호"],
        difficulty="medium",
        tags=["order", "cancel", "missing_id"],
    ),

    # ===== 클레임 관련 =====
    TestScenario(
        id="claim_001",
        name="환불 요청",
        category="claim",
        input_message="환불받고 싶어요",
        expected_intent="claim",
        expected_response_contains=["환불", "접수"],
        difficulty="easy",
        tags=["claim", "refund"],
    ),
    TestScenario(
        id="claim_002",
        name="교환 요청",
        category="claim",
        input_message="상품 교환하고 싶습니다",
        expected_intent="claim",
        expected_response_contains=["교환", "접수"],
        difficulty="easy",
        tags=["claim", "exchange"],
    ),
    TestScenario(
        id="claim_003",
        name="불량품 신고",
        category="claim",
        input_message="받은 상품이 불량이에요. 파손되어 있어요.",
        expected_intent="claim",
        expected_response_contains=["불량", "접수"],
        difficulty="medium",
        tags=["claim", "defect"],
    ),
    TestScenario(
        id="claim_004",
        name="주문번호와 함께 환불",
        category="claim",
        input_message="ORD_20250927_0001 환불 신청합니다",
        expected_intent="claim",
        expected_entities={"order_id": "ORD_20250927_0001"},
        expected_response_contains=["환불", "접수"],
        difficulty="medium",
        tags=["claim", "refund", "with_order"],
    ),

    # ===== 정책 관련 =====
    TestScenario(
        id="policy_001",
        name="환불 정책 문의",
        category="policy",
        input_message="환불 정책이 어떻게 되나요?",
        expected_intent="policy",
        expected_response_contains=["환불", "정책"],
        difficulty="easy",
        tags=["policy", "refund"],
    ),
    TestScenario(
        id="policy_002",
        name="배송 정책 문의",
        category="policy",
        input_message="배송은 얼마나 걸리나요?",
        expected_intent="policy",
        expected_response_contains=["배송", "일"],  # 배송 + 영업일/일 등
        difficulty="easy",
        tags=["policy", "shipping"],
    ),
    TestScenario(
        id="policy_003",
        name="교환 정책 문의",
        category="policy",
        input_message="교환은 언제까지 가능한가요?",
        expected_intent="policy",
        expected_response_contains=["교환"],
        difficulty="easy",
        tags=["policy", "exchange"],
    ),
    TestScenario(
        id="policy_004",
        name="반품 기한 문의",
        category="policy",
        input_message="반품 기한이 며칠인지 알려주세요",
        expected_intent="policy",
        expected_response_contains=["반품"],
        difficulty="medium",
        tags=["policy", "return"],
    ),

    # ===== 상품 관련 =====
    TestScenario(
        id="product_001",
        name="상품 정보 문의",
        category="product",
        input_message="이 상품 사이즈가 어떻게 되나요?",
        expected_intent="product",
        expected_response_contains=["상품"],
        difficulty="easy",
        tags=["product", "info"],
    ),
    TestScenario(
        id="product_002",
        name="재고 확인",
        category="product",
        input_message="재고 있나요?",
        expected_intent="product",
        expected_response_contains=["재고"],
        difficulty="easy",
        tags=["product", "stock"],
    ),

    # ===== 복합/어려운 시나리오 =====
    TestScenario(
        id="complex_001",
        name="복합 문의 (환불+정책)",
        category="claim",
        input_message="ORD_20250927_0001 환불하고 싶은데 정책상 가능한가요?",
        expected_intent="claim",
        expected_entities={"order_id": "ORD_20250927_0001"},
        expected_response_contains=["환불"],
        difficulty="hard",
        tags=["complex", "claim", "policy"],
    ),
    TestScenario(
        id="complex_002",
        name="불명확한 의도",
        category="policy",
        input_message="이거 어떻게 해요?",
        expected_intent="policy",
        expected_response_not_contains=["오류"],
        difficulty="hard",
        tags=["complex", "ambiguous"],
    ),
    TestScenario(
        id="complex_003",
        name="감정적 표현",
        category="claim",
        input_message="정말 화가 나요! 상품이 엉망이에요! 환불해주세요!",
        expected_intent="claim",
        expected_response_contains=["환불"],
        expected_response_not_contains=["오류", "에러"],
        difficulty="hard",
        tags=["complex", "emotional"],
    ),

    # ===== 엣지 케이스 =====
    TestScenario(
        id="edge_001",
        name="빈 메시지 처리",
        category="policy",
        input_message="...",
        expected_intent="policy",
        difficulty="hard",
        tags=["edge", "empty"],
    ),
    TestScenario(
        id="edge_002",
        name="영어 메시지",
        category="policy",
        input_message="I want a refund",
        expected_intent="claim",
        difficulty="hard",
        tags=["edge", "english"],
    ),
    TestScenario(
        id="edge_003",
        name="특수문자 포함",
        category="order",
        input_message="주문번호 ORD_20250927_0001!!! 확인해주세요~",
        expected_intent="order",
        expected_entities={"order_id": "ORD_20250927_0001"},
        difficulty="medium",
        tags=["edge", "special_chars"],
    ),
]


def load_scenarios(
    path: Optional[Path] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[TestScenario]:
    """테스트 시나리오 로드.

    Args:
        path: 시나리오 파일 경로 (없으면 기본값 사용)
        category: 필터링할 카테고리
        difficulty: 필터링할 난이도
        tags: 필터링할 태그 (OR 조건)

    Returns:
        테스트 시나리오 목록
    """
    scenarios = DEFAULT_SCENARIOS.copy()

    # 파일에서 추가 로드
    if path and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    scenarios.append(TestScenario.from_dict(item))
            logger.info(f"시나리오 로드: {path} ({len(data)}개)")
        except Exception as e:
            logger.warning(f"시나리오 파일 로드 실패: {e}")

    # 필터링
    if category:
        scenarios = [s for s in scenarios if s.category == category]

    if difficulty:
        scenarios = [s for s in scenarios if s.difficulty == difficulty]

    if tags:
        scenarios = [s for s in scenarios if any(t in s.tags for t in tags)]

    return scenarios


def save_scenarios(scenarios: List[TestScenario], path: Path) -> None:
    """시나리오를 파일로 저장."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in scenarios], f, ensure_ascii=False, indent=2)
    logger.info(f"시나리오 저장: {path} ({len(scenarios)}개)")
