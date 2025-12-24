"""성능 벤치마크.

에이전트 시스템의 성능을 측정합니다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scenarios import TestScenario
from .evaluator import EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """벤치마크 결과."""

    total_scenarios: int = 0
    passed_scenarios: int = 0
    failed_scenarios: int = 0

    # 시간 통계 (ms)
    total_time_ms: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # 점수 통계
    avg_relevance: float = 0.0
    avg_accuracy: float = 0.0
    avg_completeness: float = 0.0
    avg_tone: float = 0.0
    avg_clarity: float = 0.0
    avg_overall: float = 0.0

    # 카테고리별 통과율
    category_pass_rate: Dict[str, float] = field(default_factory=dict)

    # 난이도별 통과율
    difficulty_pass_rate: Dict[str, float] = field(default_factory=dict)

    # 상세 결과
    results: List[EvaluationResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """전체 통과율."""
        if self.total_scenarios == 0:
            return 0.0
        return self.passed_scenarios / self.total_scenarios * 100

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "summary": {
                "total": self.total_scenarios,
                "passed": self.passed_scenarios,
                "failed": self.failed_scenarios,
                "pass_rate": f"{self.pass_rate:.1f}%",
            },
            "latency": {
                "total_ms": round(self.total_time_ms, 2),
                "avg_ms": round(self.avg_latency_ms, 2),
                "min_ms": round(self.min_latency_ms, 2),
                "max_ms": round(self.max_latency_ms, 2),
                "p50_ms": round(self.p50_latency_ms, 2),
                "p90_ms": round(self.p90_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
            },
            "scores": {
                "avg_relevance": round(self.avg_relevance, 2),
                "avg_accuracy": round(self.avg_accuracy, 2),
                "avg_completeness": round(self.avg_completeness, 2),
                "avg_tone": round(self.avg_tone, 2),
                "avg_clarity": round(self.avg_clarity, 2),
                "avg_overall": round(self.avg_overall, 2),
            },
            "by_category": self.category_pass_rate,
            "by_difficulty": self.difficulty_pass_rate,
        }

    def print_report(self) -> str:
        """보고서 출력."""
        lines = [
            "=" * 60,
            "               평가 결과 보고서",
            "=" * 60,
            "",
            "## 요약",
            f"  - 총 시나리오: {self.total_scenarios}",
            f"  - 통과: {self.passed_scenarios}",
            f"  - 실패: {self.failed_scenarios}",
            f"  - 통과율: {self.pass_rate:.1f}%",
            "",
            "## 응답 시간",
            f"  - 평균: {self.avg_latency_ms:.1f}ms",
            f"  - 최소: {self.min_latency_ms:.1f}ms",
            f"  - 최대: {self.max_latency_ms:.1f}ms",
            f"  - P50: {self.p50_latency_ms:.1f}ms",
            f"  - P90: {self.p90_latency_ms:.1f}ms",
            f"  - P99: {self.p99_latency_ms:.1f}ms",
            "",
            "## 품질 점수 (1-5)",
            f"  - 적절성: {self.avg_relevance:.2f}",
            f"  - 정확성: {self.avg_accuracy:.2f}",
            f"  - 완전성: {self.avg_completeness:.2f}",
            f"  - 어조: {self.avg_tone:.2f}",
            f"  - 명확성: {self.avg_clarity:.2f}",
            f"  - 종합: {self.avg_overall:.2f}",
            "",
            "## 카테고리별 통과율",
        ]

        for cat, rate in self.category_pass_rate.items():
            lines.append(f"  - {cat}: {rate:.1f}%")

        lines.extend([
            "",
            "## 난이도별 통과율",
        ])

        for diff, rate in self.difficulty_pass_rate.items():
            lines.append(f"  - {diff}: {rate:.1f}%")

        # 실패 시나리오 목록
        failed = [r for r in self.results if not r.passed]
        if failed:
            lines.extend([
                "",
                "## 실패 시나리오",
            ])
            for r in failed[:10]:  # 최대 10개
                lines.append(f"  - [{r.scenario_id}] {r.scenario_name}")
                if r.issues:
                    for issue in r.issues[:3]:
                        lines.append(f"      * {issue}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


class BenchmarkRunner:
    """벤치마크 실행기."""

    def __init__(
        self,
        evaluator=None,
        concurrent_limit: int = 5,
    ):
        """초기화.

        Args:
            evaluator: 평가기 인스턴스
            concurrent_limit: 동시 실행 제한
        """
        self.evaluator = evaluator
        self.concurrent_limit = concurrent_limit
        self._semaphore = asyncio.Semaphore(concurrent_limit)

    async def run(
        self,
        scenarios: List[TestScenario],
        agent_func,
        user_id: str = "test_user",
    ) -> BenchmarkResult:
        """벤치마크 실행.

        Args:
            scenarios: 테스트 시나리오 목록
            agent_func: 에이전트 함수 (async def agent_func(user_id, message) -> response)
            user_id: 테스트 사용자 ID

        Returns:
            벤치마크 결과
        """
        result = BenchmarkResult()
        result.total_scenarios = len(scenarios)

        start_time = time.time()

        # 시나리오 실행
        tasks = [
            self._run_scenario(scenario, agent_func, user_id)
            for scenario in scenarios
        ]
        eval_results = await asyncio.gather(*tasks, return_exceptions=True)

        result.total_time_ms = (time.time() - start_time) * 1000

        # 결과 집계
        latencies = []
        scores = {
            "relevance": [],
            "accuracy": [],
            "completeness": [],
            "tone": [],
            "clarity": [],
            "overall": [],
        }
        category_results: Dict[str, List[bool]] = {}
        difficulty_results: Dict[str, List[bool]] = {}

        for i, eval_result in enumerate(eval_results):
            if isinstance(eval_result, Exception):
                logger.error(f"시나리오 실행 오류: {eval_result}")
                result.failed_scenarios += 1
                continue

            result.results.append(eval_result)

            if eval_result.passed:
                result.passed_scenarios += 1
            else:
                result.failed_scenarios += 1

            # 레이턴시
            latencies.append(eval_result.latency_ms)

            # 점수
            scores["relevance"].append(eval_result.relevance)
            scores["accuracy"].append(eval_result.accuracy)
            scores["completeness"].append(eval_result.completeness)
            scores["tone"].append(eval_result.tone)
            scores["clarity"].append(eval_result.clarity)
            scores["overall"].append(eval_result.overall)

            # 카테고리별
            scenario = scenarios[i]
            if scenario.category not in category_results:
                category_results[scenario.category] = []
            category_results[scenario.category].append(eval_result.passed)

            # 난이도별
            if scenario.difficulty not in difficulty_results:
                difficulty_results[scenario.difficulty] = []
            difficulty_results[scenario.difficulty].append(eval_result.passed)

        # 레이턴시 통계
        if latencies:
            latencies.sort()
            result.avg_latency_ms = sum(latencies) / len(latencies)
            result.min_latency_ms = min(latencies)
            result.max_latency_ms = max(latencies)
            result.p50_latency_ms = self._percentile(latencies, 50)
            result.p90_latency_ms = self._percentile(latencies, 90)
            result.p99_latency_ms = self._percentile(latencies, 99)

        # 점수 평균
        for key, values in scores.items():
            if values:
                avg = sum(values) / len(values)
                setattr(result, f"avg_{key}", avg)

        # 카테고리별 통과율
        for cat, results_list in category_results.items():
            rate = sum(results_list) / len(results_list) * 100 if results_list else 0
            result.category_pass_rate[cat] = rate

        # 난이도별 통과율
        for diff, results_list in difficulty_results.items():
            rate = sum(results_list) / len(results_list) * 100 if results_list else 0
            result.difficulty_pass_rate[diff] = rate

        return result

    async def _run_scenario(
        self,
        scenario: TestScenario,
        agent_func,
        user_id: str,
    ) -> EvaluationResult:
        """단일 시나리오 실행."""
        async with self._semaphore:
            start_time = time.time()

            try:
                # 시나리오 컨텍스트에서 user_id 가져오기 (있으면)
                scenario_user_id = scenario.context.get("user_id", user_id)

                # 의도 분류 (평가용)
                from src.agents.nodes.intent_classifier import classify_intent_keyword
                intent_result = classify_intent_keyword(scenario.input_message)
                intent = intent_result.intent
                entities = intent_result.payload

                # 에이전트 호출
                response = await agent_func(scenario_user_id, scenario.input_message)
                latency_ms = (time.time() - start_time) * 1000

                # 응답 추출
                if isinstance(response, dict):
                    agent_response = response.get("response", response.get("message", str(response)))
                    # 응답에 의도 정보가 있으면 덮어쓰기
                    if response.get("intent"):
                        intent = response.get("intent")
                    if response.get("entities"):
                        entities = response.get("entities")
                else:
                    agent_response = str(response)

                # 평가
                if self.evaluator:
                    eval_result = await self.evaluator.evaluate(
                        scenario=scenario,
                        agent_response=agent_response,
                        intent_result=intent,
                        entities_result=entities,
                        latency_ms=latency_ms,
                    )
                else:
                    # 기본 평가
                    from .evaluator import RuleBasedEvaluator
                    evaluator = RuleBasedEvaluator()
                    eval_result = await evaluator.evaluate(
                        scenario=scenario,
                        agent_response=agent_response,
                        intent_result=intent,
                        entities_result=entities,
                        latency_ms=latency_ms,
                    )

                return eval_result

            except Exception as e:
                logger.error(f"시나리오 실행 오류 [{scenario.id}]: {e}")
                return EvaluationResult(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    user_message=scenario.input_message,
                    agent_response="",
                    error=str(e),
                    passed=False,
                    latency_ms=(time.time() - start_time) * 1000,
                )

    def _percentile(self, sorted_list: List[float], percent: int) -> float:
        """백분위수 계산."""
        if not sorted_list:
            return 0.0
        k = (len(sorted_list) - 1) * percent / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_list) else f
        return sorted_list[f] + (sorted_list[c] - sorted_list[f]) * (k - f)
