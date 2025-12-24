"""LLM-as-Judge 평가기.

LLM을 사용하여 에이전트 응답을 평가합니다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scenarios import TestScenario

logger = logging.getLogger(__name__)


# 평가 프롬프트
EVALUATION_PROMPT = """당신은 한국어 전자상거래 고객 서비스 에이전트의 응답을 평가하는 전문가입니다.

## 평가 기준

다음 5가지 기준으로 응답을 평가하세요 (각 1-5점):

1. **적절성 (Relevance)**: 사용자 질문에 적절히 답변했는가?
2. **정확성 (Accuracy)**: 정보가 정확하고 사실에 기반하는가?
3. **완전성 (Completeness)**: 필요한 정보를 모두 제공했는가?
4. **톤/어조 (Tone)**: 친절하고 전문적인 어조인가?
5. **명확성 (Clarity)**: 응답이 명확하고 이해하기 쉬운가?

## 입력

### 사용자 메시지
{user_message}

### 에이전트 응답
{agent_response}

### 기대 사항
- 예상 의도: {expected_intent}
- 포함해야 할 내용: {expected_contains}
- 포함하지 말아야 할 내용: {expected_not_contains}

## 출력 형식

반드시 다음 JSON 형식으로만 응답하세요:

```json
{{
  "relevance": <1-5>,
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "tone": <1-5>,
  "clarity": <1-5>,
  "overall": <1-5>,
  "passed": <true/false>,
  "issues": ["문제점1", "문제점2"],
  "feedback": "전체적인 피드백"
}}
```
"""


@dataclass
class EvaluationResult:
    """평가 결과."""

    scenario_id: str
    scenario_name: str
    user_message: str
    agent_response: str

    # 점수 (1-5)
    relevance: float = 0.0
    accuracy: float = 0.0
    completeness: float = 0.0
    tone: float = 0.0
    clarity: float = 0.0
    overall: float = 0.0

    # 결과
    passed: bool = False
    issues: List[str] = field(default_factory=list)
    feedback: str = ""

    # 규칙 기반 평가
    intent_matched: bool = False
    entities_matched: bool = False
    contains_matched: bool = False
    not_contains_matched: bool = True

    # 메타
    latency_ms: float = 0.0
    error: Optional[str] = None

    @property
    def average_score(self) -> float:
        """평균 점수."""
        scores = [self.relevance, self.accuracy, self.completeness, self.tone, self.clarity]
        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "user_message": self.user_message,
            "agent_response": self.agent_response,
            "scores": {
                "relevance": self.relevance,
                "accuracy": self.accuracy,
                "completeness": self.completeness,
                "tone": self.tone,
                "clarity": self.clarity,
                "overall": self.overall,
                "average": self.average_score,
            },
            "passed": self.passed,
            "issues": self.issues,
            "feedback": self.feedback,
            "rule_based": {
                "intent_matched": self.intent_matched,
                "entities_matched": self.entities_matched,
                "contains_matched": self.contains_matched,
                "not_contains_matched": self.not_contains_matched,
            },
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class LLMEvaluator:
    """LLM 기반 평가기."""

    def __init__(self, use_llm: bool = True):
        """초기화.

        Args:
            use_llm: LLM 평가 사용 여부 (False면 규칙 기반만)
        """
        self.use_llm = use_llm
        self._client = None

    def _get_client(self):
        """LLM 클라이언트 지연 로딩."""
        if self._client is None:
            try:
                from src.llm.client import get_client
                self._client = get_client()
            except Exception as e:
                logger.warning(f"LLM 클라이언트 로드 실패: {e}")
                self._client = None
        return self._client

    async def evaluate(
        self,
        scenario: TestScenario,
        agent_response: str,
        intent_result: Optional[str] = None,
        entities_result: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
    ) -> EvaluationResult:
        """시나리오에 대해 에이전트 응답 평가.

        Args:
            scenario: 테스트 시나리오
            agent_response: 에이전트 응답
            intent_result: 실제 분류된 의도
            entities_result: 실제 추출된 엔티티
            latency_ms: 응답 지연 시간

        Returns:
            평가 결과
        """
        result = EvaluationResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            user_message=scenario.input_message,
            agent_response=agent_response,
            latency_ms=latency_ms,
        )

        try:
            # 1. 규칙 기반 평가
            self._rule_based_evaluation(scenario, agent_response, intent_result, entities_result, result)

            # 2. LLM 기반 평가 (선택적)
            if self.use_llm:
                await self._llm_evaluation(scenario, agent_response, result)
            else:
                # 규칙 기반만 사용 시 점수 계산
                self._calculate_rule_based_scores(result)

            # 3. 최종 통과 여부 결정
            result.passed = self._determine_pass(result)

        except Exception as e:
            logger.error(f"평가 오류: {e}")
            result.error = str(e)
            result.passed = False

        return result

    def _rule_based_evaluation(
        self,
        scenario: TestScenario,
        response: str,
        intent: Optional[str],
        entities: Optional[Dict[str, Any]],
        result: EvaluationResult,
    ) -> None:
        """규칙 기반 평가."""
        # 의도 매칭
        if intent:
            result.intent_matched = intent == scenario.expected_intent

        # 엔티티 매칭
        if entities and scenario.expected_entities:
            matched = all(
                entities.get(k) == v
                for k, v in scenario.expected_entities.items()
            )
            result.entities_matched = matched
        elif not scenario.expected_entities:
            result.entities_matched = True

        # 포함 키워드 체크
        if scenario.expected_response_contains:
            result.contains_matched = all(
                kw.lower() in response.lower()
                for kw in scenario.expected_response_contains
            )
            if not result.contains_matched:
                missing = [kw for kw in scenario.expected_response_contains if kw.lower() not in response.lower()]
                result.issues.append(f"누락된 키워드: {missing}")
        else:
            result.contains_matched = True

        # 제외 키워드 체크
        if scenario.expected_response_not_contains:
            result.not_contains_matched = all(
                kw.lower() not in response.lower()
                for kw in scenario.expected_response_not_contains
            )
            if not result.not_contains_matched:
                found = [kw for kw in scenario.expected_response_not_contains if kw.lower() in response.lower()]
                result.issues.append(f"포함되면 안 되는 키워드 발견: {found}")
        else:
            result.not_contains_matched = True

    async def _llm_evaluation(
        self,
        scenario: TestScenario,
        response: str,
        result: EvaluationResult,
    ) -> None:
        """LLM 기반 평가."""
        client = self._get_client()
        if client is None:
            logger.warning("LLM 클라이언트 없음, 규칙 기반 점수 사용")
            self._calculate_rule_based_scores(result)
            return

        prompt = EVALUATION_PROMPT.format(
            user_message=scenario.input_message,
            agent_response=response,
            expected_intent=scenario.expected_intent,
            expected_contains=", ".join(scenario.expected_response_contains) or "없음",
            expected_not_contains=", ".join(scenario.expected_response_not_contains) or "없음",
        )

        try:
            llm_response = await client.generate(prompt, temperature=0.0)
            eval_data = self._parse_llm_response(llm_response)

            if eval_data:
                result.relevance = eval_data.get("relevance", 0)
                result.accuracy = eval_data.get("accuracy", 0)
                result.completeness = eval_data.get("completeness", 0)
                result.tone = eval_data.get("tone", 0)
                result.clarity = eval_data.get("clarity", 0)
                result.overall = eval_data.get("overall", 0)
                result.feedback = eval_data.get("feedback", "")

                if eval_data.get("issues"):
                    result.issues.extend(eval_data["issues"])

        except Exception as e:
            logger.warning(f"LLM 평가 실패: {e}")
            self._calculate_rule_based_scores(result)

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """LLM 응답 파싱."""
        try:
            # JSON 블록 추출
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # 직접 JSON 파싱 시도
            return json.loads(response)

        except json.JSONDecodeError:
            logger.warning(f"LLM 응답 JSON 파싱 실패: {response[:200]}")
            return None

    def _calculate_rule_based_scores(self, result: EvaluationResult) -> None:
        """규칙 기반 점수 계산."""
        score = 0
        max_score = 0

        # 의도 매칭 (2점)
        max_score += 2
        if result.intent_matched:
            score += 2

        # 엔티티 매칭 (1점)
        max_score += 1
        if result.entities_matched:
            score += 1

        # 포함 키워드 (1점)
        max_score += 1
        if result.contains_matched:
            score += 1

        # 제외 키워드 (1점)
        max_score += 1
        if result.not_contains_matched:
            score += 1

        # 1-5 점수로 변환
        normalized = (score / max_score) * 4 + 1 if max_score > 0 else 1

        result.relevance = normalized
        result.accuracy = normalized
        result.completeness = normalized
        result.tone = 3.0  # 기본값
        result.clarity = 3.0  # 기본값
        result.overall = normalized

    def _determine_pass(self, result: EvaluationResult) -> bool:
        """통과 여부 결정."""
        # 필수 조건
        if not result.not_contains_matched:
            return False

        # 점수 기준 (평균 3점 이상)
        if result.average_score < 3.0:
            return False

        # 규칙 기반 조건
        rule_score = sum([
            result.intent_matched,
            result.entities_matched,
            result.contains_matched,
            result.not_contains_matched,
        ])

        return rule_score >= 3


class RuleBasedEvaluator(LLMEvaluator):
    """규칙 기반 평가기 (LLM 없이)."""

    def __init__(self):
        super().__init__(use_llm=False)
