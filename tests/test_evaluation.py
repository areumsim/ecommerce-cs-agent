"""평가 모듈 테스트."""

import pytest
from src.evaluation import (
    TestScenario,
    load_scenarios,
    EvaluationResult,
    RuleBasedEvaluator,
    BenchmarkResult,
)


class TestTestScenario:
    """TestScenario 테스트."""

    def test_create_scenario(self):
        """시나리오 생성."""
        scenario = TestScenario(
            id="test_001",
            name="테스트 시나리오",
            category="order",
            input_message="주문 확인해주세요",
            expected_intent="order",
        )
        assert scenario.id == "test_001"
        assert scenario.category == "order"

    def test_scenario_to_dict(self):
        """딕셔너리 변환."""
        scenario = TestScenario(
            id="test_001",
            name="테스트",
            category="order",
            input_message="테스트",
            expected_intent="order",
        )
        data = scenario.to_dict()
        assert data["id"] == "test_001"
        assert "expected_response_contains" in data

    def test_scenario_from_dict(self):
        """딕셔너리에서 생성."""
        data = {
            "id": "test_001",
            "name": "테스트",
            "category": "order",
            "input_message": "테스트",
            "expected_intent": "order",
        }
        scenario = TestScenario.from_dict(data)
        assert scenario.id == "test_001"


class TestLoadScenarios:
    """시나리오 로드 테스트."""

    def test_load_default_scenarios(self):
        """기본 시나리오 로드."""
        scenarios = load_scenarios()
        assert len(scenarios) > 0

    def test_filter_by_category(self):
        """카테고리 필터."""
        scenarios = load_scenarios(category="order")
        assert all(s.category == "order" for s in scenarios)

    def test_filter_by_difficulty(self):
        """난이도 필터."""
        scenarios = load_scenarios(difficulty="easy")
        assert all(s.difficulty == "easy" for s in scenarios)

    def test_filter_by_tags(self):
        """태그 필터."""
        scenarios = load_scenarios(tags=["refund"])
        assert all(any("refund" in s.tags for s in scenarios) for s in scenarios)


class TestEvaluationResult:
    """EvaluationResult 테스트."""

    def test_create_result(self):
        """결과 생성."""
        result = EvaluationResult(
            scenario_id="test_001",
            scenario_name="테스트",
            user_message="테스트 메시지",
            agent_response="테스트 응답",
        )
        assert result.scenario_id == "test_001"
        assert result.passed is False

    def test_average_score(self):
        """평균 점수 계산."""
        result = EvaluationResult(
            scenario_id="test_001",
            scenario_name="테스트",
            user_message="테스트",
            agent_response="응답",
            relevance=4.0,
            accuracy=5.0,
            completeness=3.0,
            tone=4.0,
            clarity=4.0,
        )
        assert result.average_score == 4.0

    def test_to_dict(self):
        """딕셔너리 변환."""
        result = EvaluationResult(
            scenario_id="test_001",
            scenario_name="테스트",
            user_message="테스트",
            agent_response="응답",
        )
        data = result.to_dict()
        assert "scores" in data
        assert "rule_based" in data


class TestRuleBasedEvaluator:
    """RuleBasedEvaluator 테스트."""

    @pytest.fixture
    def evaluator(self):
        return RuleBasedEvaluator()

    @pytest.mark.asyncio
    async def test_evaluate_with_matching_keywords(self, evaluator):
        """키워드 매칭 평가."""
        scenario = TestScenario(
            id="test_001",
            name="환불 테스트",
            category="claim",
            input_message="환불해주세요",
            expected_intent="claim",
            expected_response_contains=["환불", "접수"],
        )
        result = await evaluator.evaluate(
            scenario=scenario,
            agent_response="환불 요청이 접수되었습니다.",
            intent_result="claim",
        )
        assert result.contains_matched is True
        assert result.intent_matched is True

    @pytest.mark.asyncio
    async def test_evaluate_with_missing_keywords(self, evaluator):
        """누락 키워드 평가."""
        scenario = TestScenario(
            id="test_001",
            name="환불 테스트",
            category="claim",
            input_message="환불해주세요",
            expected_intent="claim",
            expected_response_contains=["환불", "티켓번호"],
        )
        result = await evaluator.evaluate(
            scenario=scenario,
            agent_response="요청이 접수되었습니다.",
            intent_result="claim",
        )
        assert result.contains_matched is False
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_evaluate_forbidden_keywords(self, evaluator):
        """금지 키워드 평가."""
        scenario = TestScenario(
            id="test_001",
            name="오류 테스트",
            category="policy",
            input_message="정책 알려주세요",
            expected_intent="policy",
            expected_response_not_contains=["오류", "에러"],
        )
        result = await evaluator.evaluate(
            scenario=scenario,
            agent_response="오류가 발생했습니다.",
            intent_result="policy",
        )
        assert result.not_contains_matched is False

    @pytest.mark.asyncio
    async def test_evaluate_entity_matching(self, evaluator):
        """엔티티 매칭 평가."""
        scenario = TestScenario(
            id="test_001",
            name="주문 상세",
            category="order",
            input_message="ORD-001 확인",
            expected_intent="order",
            expected_entities={"order_id": "ORD-001"},
        )
        result = await evaluator.evaluate(
            scenario=scenario,
            agent_response="주문을 확인했습니다.",
            intent_result="order",
            entities_result={"order_id": "ORD-001"},
        )
        assert result.entities_matched is True


class TestBenchmarkResult:
    """BenchmarkResult 테스트."""

    def test_pass_rate(self):
        """통과율 계산."""
        result = BenchmarkResult(
            total_scenarios=10,
            passed_scenarios=7,
            failed_scenarios=3,
        )
        assert result.pass_rate == 70.0

    def test_pass_rate_zero_total(self):
        """시나리오 없을 때."""
        result = BenchmarkResult(
            total_scenarios=0,
            passed_scenarios=0,
            failed_scenarios=0,
        )
        assert result.pass_rate == 0.0

    def test_to_dict(self):
        """딕셔너리 변환."""
        result = BenchmarkResult(
            total_scenarios=10,
            passed_scenarios=7,
            failed_scenarios=3,
        )
        data = result.to_dict()
        assert "summary" in data
        assert "latency" in data
        assert "scores" in data

    def test_print_report(self):
        """보고서 출력."""
        result = BenchmarkResult(
            total_scenarios=10,
            passed_scenarios=7,
            failed_scenarios=3,
            avg_latency_ms=100.0,
            avg_overall=4.0,
        )
        report = result.print_report()
        assert "통과율" in report
        assert "70.0%" in report
