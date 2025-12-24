"""비전 파이프라인.

여러 분석기를 조합하여 종합적인 이미지 분석을 제공합니다.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from .base import BaseImageAnalyzer, ImageAnalysisResult, encode_image_base64, resize_image

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """파이프라인 분석 결과."""

    success: bool
    image_info: Dict[str, Any]
    analyses: Dict[str, ImageAnalysisResult]
    summary: str
    confidence: float
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisionPipeline:
    """비전 분석 파이프라인.

    여러 이미지 분석기를 조합하여 종합적인 분석을 제공합니다.

    Example:
        pipeline = VisionPipeline()
        pipeline.add_analyzer("product", get_product_analyzer())
        pipeline.add_analyzer("defect", get_defect_detector())
        result = await pipeline.analyze(image_path)
    """

    def __init__(
        self,
        max_image_size: int = 1024,
        parallel: bool = True,
    ):
        """파이프라인 초기화.

        Args:
            max_image_size: 최대 이미지 크기 (리사이즈)
            parallel: 분석기 병렬 실행 여부
        """
        self.max_image_size = max_image_size
        self.parallel = parallel
        self._analyzers: Dict[str, BaseImageAnalyzer] = {}
        self.logger = logging.getLogger(f"{__name__}.VisionPipeline")

    def add_analyzer(self, name: str, analyzer: BaseImageAnalyzer) -> "VisionPipeline":
        """분석기 추가.

        Args:
            name: 분석기 이름
            analyzer: 분석기 인스턴스

        Returns:
            self (체이닝 지원)
        """
        self._analyzers[name] = analyzer
        return self

    def remove_analyzer(self, name: str) -> "VisionPipeline":
        """분석기 제거.

        Args:
            name: 분석기 이름

        Returns:
            self (체이닝 지원)
        """
        self._analyzers.pop(name, None)
        return self

    def list_analyzers(self) -> List[str]:
        """등록된 분석기 목록."""
        return list(self._analyzers.keys())

    def _load_image(self, source: Union[str, Path, bytes, Image.Image]) -> Image.Image:
        """이미지 로드."""
        if isinstance(source, Image.Image):
            return source

        if isinstance(source, bytes):
            import io
            return Image.open(io.BytesIO(source))

        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.exists():
                return Image.open(path)

        raise ValueError(f"이미지를 로드할 수 없습니다: {source}")

    def _get_image_info(self, image: Image.Image) -> Dict[str, Any]:
        """이미지 기본 정보 추출."""
        return {
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
            "aspect_ratio": round(image.width / image.height, 2) if image.height > 0 else 0,
        }

    async def analyze(
        self,
        image: Union[str, Path, bytes, Image.Image],
        analyzers: Optional[List[str]] = None,
        **kwargs,
    ) -> PipelineResult:
        """이미지 종합 분석.

        Args:
            image: 분석할 이미지
            analyzers: 사용할 분석기 목록 (None이면 전체)
            **kwargs: 분석기별 추가 파라미터

        Returns:
            종합 분석 결과
        """
        try:
            # 이미지 로드
            img = self._load_image(image)
            image_info = self._get_image_info(img)

            # 이미지 전처리
            if img.mode != "RGB":
                img = img.convert("RGB")

            if max(img.width, img.height) > self.max_image_size:
                img = resize_image(img, self.max_image_size)
                image_info["resized"] = True

            # 분석기 선택
            target_analyzers = {}
            if analyzers:
                for name in analyzers:
                    if name in self._analyzers:
                        target_analyzers[name] = self._analyzers[name]
            else:
                target_analyzers = self._analyzers

            if not target_analyzers:
                return PipelineResult(
                    success=False,
                    image_info=image_info,
                    analyses={},
                    summary="분석기가 등록되지 않았습니다.",
                    confidence=0.0,
                )

            # 분석 실행
            analyses: Dict[str, ImageAnalysisResult] = {}

            if self.parallel and len(target_analyzers) > 1:
                # 병렬 실행
                tasks = {
                    name: analyzer.analyze(img, **kwargs.get(name, {}))
                    for name, analyzer in target_analyzers.items()
                }
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)

                for name, result in zip(tasks.keys(), results):
                    if isinstance(result, Exception):
                        analyses[name] = ImageAnalysisResult(
                            success=False,
                            analysis_type=name,
                            description=f"분석 실패: {str(result)}",
                            confidence=0.0,
                        )
                    else:
                        analyses[name] = result
            else:
                # 순차 실행
                for name, analyzer in target_analyzers.items():
                    try:
                        result = await analyzer.analyze(img, **kwargs.get(name, {}))
                        analyses[name] = result
                    except Exception as e:
                        analyses[name] = ImageAnalysisResult(
                            success=False,
                            analysis_type=name,
                            description=f"분석 실패: {str(e)}",
                            confidence=0.0,
                        )

            # 결과 집계
            successful = [r for r in analyses.values() if r.success]
            avg_confidence = (
                sum(r.confidence for r in successful) / len(successful)
                if successful else 0.0
            )

            # 요약 생성
            summary = self._generate_summary(analyses)
            recommendations = self._generate_recommendations(analyses)

            return PipelineResult(
                success=len(successful) > 0,
                image_info=image_info,
                analyses=analyses,
                summary=summary,
                confidence=avg_confidence,
                recommendations=recommendations,
                metadata={
                    "analyzers_used": list(analyses.keys()),
                    "successful_count": len(successful),
                    "failed_count": len(analyses) - len(successful),
                },
            )

        except Exception as e:
            self.logger.error(f"파이프라인 분석 실패: {e}")
            return PipelineResult(
                success=False,
                image_info={},
                analyses={},
                summary=f"분석 실패: {str(e)}",
                confidence=0.0,
            )

    def _generate_summary(self, analyses: Dict[str, ImageAnalysisResult]) -> str:
        """분석 결과 요약 생성."""
        summaries = []

        for name, result in analyses.items():
            if result.success:
                summaries.append(f"[{name}] {result.description}")
            else:
                summaries.append(f"[{name}] 분석 실패")

        return " | ".join(summaries) if summaries else "분석 결과 없음"

    def _generate_recommendations(
        self,
        analyses: Dict[str, ImageAnalysisResult],
    ) -> List[str]:
        """분석 결과 기반 권장사항 생성."""
        recommendations = []

        for name, result in analyses.items():
            if not result.success:
                continue

            # 불량 탐지 결과 처리
            if name == "defect" and result.labels:
                if any("scratch" in label.lower() for label in result.labels):
                    recommendations.append("스크래치가 발견되었습니다. 교환을 권장합니다.")
                if any("dent" in label.lower() for label in result.labels):
                    recommendations.append("찌그러짐이 발견되었습니다. 반품을 고려해 주세요.")
                if any("stain" in label.lower() for label in result.labels):
                    recommendations.append("오염이 발견되었습니다. 세척 후 재확인해 주세요.")

            # 상품 분석 결과 처리
            if name == "product":
                condition = result.attributes.get("condition", "")
                if condition == "damaged":
                    recommendations.append("상품 상태가 불량입니다. 클레임 접수를 권장합니다.")
                elif condition == "used":
                    recommendations.append("사용 흔적이 있습니다. 중고 상품으로 분류됩니다.")

        return recommendations


# 기본 파이프라인 인스턴스 (지연 로딩)
_pipeline: Optional[VisionPipeline] = None


def get_pipeline(
    include_product: bool = True,
    include_defect: bool = True,
    use_clip: bool = False,
) -> VisionPipeline:
    """기본 파이프라인 인스턴스 반환.

    Args:
        include_product: 상품 분석기 포함 여부
        include_defect: 불량 탐지기 포함 여부
        use_clip: CLIP 모델 사용 여부

    Returns:
        VisionPipeline 인스턴스
    """
    global _pipeline

    if _pipeline is None:
        from . import get_product_analyzer, get_defect_detector

        _pipeline = VisionPipeline()

        if include_product:
            _pipeline.add_analyzer("product", get_product_analyzer(use_clip))

        if include_defect:
            _pipeline.add_analyzer("defect", get_defect_detector(use_clip))

    return _pipeline


def reset_pipeline() -> None:
    """파이프라인 리셋 (테스트용)."""
    global _pipeline
    _pipeline = None
