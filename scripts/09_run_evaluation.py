#!/usr/bin/env python
"""평가 자동화 실행 스크립트.

에이전트 시스템의 성능을 자동으로 평가합니다.

사용법:
    # 전체 평가 (규칙 기반)
    python scripts/09_run_evaluation.py

    # LLM 평가 포함
    python scripts/09_run_evaluation.py --use-llm

    # 카테고리별 평가
    python scripts/09_run_evaluation.py --category order
    python scripts/09_run_evaluation.py --category claim

    # 난이도별 평가
    python scripts/09_run_evaluation.py --difficulty easy
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import (
    load_scenarios,
    run_evaluation,
    BenchmarkRunner,
    RuleBasedEvaluator,
    LLMEvaluator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """메인 함수."""
    parser = argparse.ArgumentParser(description="에이전트 평가 자동화")
    parser.add_argument(
        "--category",
        choices=["order", "claim", "policy", "product"],
        help="평가할 카테고리",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        help="평가할 난이도",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="LLM 기반 평가 사용",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=3,
        help="동시 실행 수 (기본: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./outputs/evaluation",
        help="결과 저장 디렉토리",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="빠른 평가 (easy 난이도만)",
    )

    args = parser.parse_args()

    # 빠른 평가 모드
    if args.quick:
        args.difficulty = "easy"
        args.use_llm = False

    print("=" * 60)
    print("       한국어 전자상거래 에이전트 평가")
    print("=" * 60)
    print()
    print(f"  카테고리: {args.category or '전체'}")
    print(f"  난이도: {args.difficulty or '전체'}")
    print(f"  LLM 평가: {'사용' if args.use_llm else '미사용'}")
    print(f"  동시 실행: {args.concurrent}")
    print(f"  출력 디렉토리: {args.output_dir}")
    print()

    # 시나리오 로드
    scenarios = load_scenarios(
        category=args.category,
        difficulty=args.difficulty,
    )

    print(f"로드된 시나리오: {len(scenarios)}개")
    print()

    # 카테고리별 분포
    category_counts = {}
    for s in scenarios:
        category_counts[s.category] = category_counts.get(s.category, 0) + 1
    print("카테고리별 분포:")
    for cat, count in sorted(category_counts.items()):
        print(f"  - {cat}: {count}개")
    print()

    # 난이도별 분포
    difficulty_counts = {}
    for s in scenarios:
        difficulty_counts[s.difficulty] = difficulty_counts.get(s.difficulty, 0) + 1
    print("난이도별 분포:")
    for diff, count in sorted(difficulty_counts.items()):
        print(f"  - {diff}: {count}개")
    print()

    print("-" * 60)
    print("평가 시작...")
    print()

    # 평가 실행
    result = await run_evaluation(
        scenarios=scenarios,
        use_llm_judge=args.use_llm,
        concurrent_limit=args.concurrent,
        output_dir=Path(args.output_dir),
    )

    # 결과 요약
    print()
    print("-" * 60)
    print("평가 완료!")
    print()
    print(f"  총 시나리오: {result.total_scenarios}")
    print(f"  통과: {result.passed_scenarios}")
    print(f"  실패: {result.failed_scenarios}")
    print(f"  통과율: {result.pass_rate:.1f}%")
    print()

    # 실패 시나리오 상세
    failed = [r for r in result.results if not r.passed]
    if failed:
        print("실패 시나리오:")
        for r in failed[:5]:
            print(f"  - [{r.scenario_id}] {r.scenario_name}")
            print(f"      입력: {r.user_message[:50]}...")
            if r.issues:
                print(f"      문제: {', '.join(r.issues[:2])}")
        if len(failed) > 5:
            print(f"  ... 외 {len(failed) - 5}개")
    print()

    return result


if __name__ == "__main__":
    result = asyncio.run(main())

    # 종료 코드 (실패율에 따라)
    if result.pass_rate < 50:
        sys.exit(2)  # 심각한 실패
    elif result.pass_rate < 70:
        sys.exit(1)  # 개선 필요
    else:
        sys.exit(0)  # 성공
