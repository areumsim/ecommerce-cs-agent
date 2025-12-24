"""평가 실행기.

전체 평가 파이프라인을 실행합니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scenarios import TestScenario, load_scenarios
from .evaluator import LLMEvaluator, RuleBasedEvaluator, EvaluationResult
from .benchmark import BenchmarkRunner, BenchmarkResult

logger = logging.getLogger(__name__)


async def run_evaluation(
    scenarios: Optional[List[TestScenario]] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    use_llm_judge: bool = False,
    concurrent_limit: int = 5,
    output_dir: Optional[Path] = None,
    user_id: str = "eval_user",
) -> BenchmarkResult:
    """평가 실행.

    Args:
        scenarios: 테스트 시나리오 (없으면 기본값)
        category: 필터링할 카테고리
        difficulty: 필터링할 난이도
        use_llm_judge: LLM 평가 사용 여부
        concurrent_limit: 동시 실행 제한
        output_dir: 결과 저장 디렉토리
        user_id: 테스트 사용자 ID

    Returns:
        벤치마크 결과
    """
    # 시나리오 로드
    if scenarios is None:
        scenarios = load_scenarios(category=category, difficulty=difficulty)

    logger.info(f"평가 시작: {len(scenarios)}개 시나리오")

    # 평가기 생성
    if use_llm_judge:
        evaluator = LLMEvaluator(use_llm=True)
    else:
        evaluator = RuleBasedEvaluator()

    # 벤치마크 러너 생성
    runner = BenchmarkRunner(
        evaluator=evaluator,
        concurrent_limit=concurrent_limit,
    )

    # 에이전트 함수 가져오기
    agent_func = await _get_agent_func()

    # 벤치마크 실행
    result = await runner.run(
        scenarios=scenarios,
        agent_func=agent_func,
        user_id=user_id,
    )

    # 결과 저장
    if output_dir:
        _save_results(result, output_dir)

    # 보고서 출력
    print(result.print_report())

    return result


async def _get_agent_func():
    """에이전트 함수 반환."""
    from src.agents.router import process_message

    async def agent_func(user_id: str, message: str) -> Dict[str, Any]:
        """에이전트 래퍼."""
        try:
            response = await process_message(user_id, message)
            return response
        except Exception as e:
            logger.error(f"에이전트 오류: {e}")
            return {"response": f"오류: {e}", "error": str(e)}

    return agent_func


def _save_results(result: BenchmarkResult, output_dir: Path) -> None:
    """결과 저장."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 요약 저장
    summary_path = output_dir / f"eval_summary_{timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(f"요약 저장: {summary_path}")

    # 상세 결과 저장
    details_path = output_dir / f"eval_details_{timestamp}.jsonl"
    with open(details_path, "w", encoding="utf-8") as f:
        for r in result.results:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    logger.info(f"상세 결과 저장: {details_path}")

    # 보고서 저장
    report_path = output_dir / f"eval_report_{timestamp}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.print_report())
    logger.info(f"보고서 저장: {report_path}")


async def quick_eval(
    messages: List[str],
    user_id: str = "quick_eval_user",
) -> List[Dict[str, Any]]:
    """간단한 평가 실행.

    Args:
        messages: 테스트 메시지 목록
        user_id: 사용자 ID

    Returns:
        응답 목록
    """
    from src.agents.router import process_message

    results = []
    for msg in messages:
        try:
            response = await process_message(user_id, msg)
            results.append({
                "input": msg,
                "response": response.get("response", ""),
                "success": response.get("success", False),
            })
        except Exception as e:
            results.append({
                "input": msg,
                "response": f"오류: {e}",
                "success": False,
            })

    return results


def run_evaluation_sync(
    scenarios: Optional[List[TestScenario]] = None,
    **kwargs,
) -> BenchmarkResult:
    """동기 평가 실행 (스크립트용)."""
    return asyncio.run(run_evaluation(scenarios=scenarios, **kwargs))
