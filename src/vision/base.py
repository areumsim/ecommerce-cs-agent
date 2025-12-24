"""비전 모듈 기본 클래스.

이미지 분석을 위한 기본 인터페이스를 제공합니다.
"""

from __future__ import annotations

import base64
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisResult:
    """이미지 분석 결과."""

    success: bool
    analysis_type: str  # product, defect, receipt, general
    description: str
    confidence: float = 0.0
    labels: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    bounding_boxes: List[Dict[str, Any]] = field(default_factory=list)
    raw_output: Dict[str, Any] = field(default_factory=dict)


class BaseImageAnalyzer(ABC):
    """기본 이미지 분석기.

    모든 이미지 분석기가 상속받는 베이스 클래스입니다.
    """

    name: str = "base"
    supported_formats: List[str] = ["jpg", "jpeg", "png", "webp", "gif"]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    def load_image(self, source: Union[str, Path, bytes, Image.Image]) -> Image.Image:
        """다양한 소스에서 이미지 로드.

        Args:
            source: 파일 경로, 바이트, 또는 PIL Image

        Returns:
            PIL Image 객체
        """
        if isinstance(source, Image.Image):
            return source

        if isinstance(source, bytes):
            return Image.open(io.BytesIO(source))

        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.exists():
                return Image.open(path)

            # base64 인코딩된 문자열 처리
            if isinstance(source, str) and source.startswith("data:image"):
                # data:image/jpeg;base64,... 형식
                header, data = source.split(",", 1)
                return Image.open(io.BytesIO(base64.b64decode(data)))

            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {source}")

        raise ValueError(f"지원하지 않는 이미지 소스 타입: {type(source)}")

    def validate_image(self, image: Image.Image) -> bool:
        """이미지 유효성 검증.

        Args:
            image: PIL Image

        Returns:
            유효 여부
        """
        if image is None:
            return False

        # 최소 크기 검증
        if image.width < 10 or image.height < 10:
            return False

        # 최대 크기 검증 (메모리 보호)
        if image.width > 4096 or image.height > 4096:
            self.logger.warning("이미지가 너무 큽니다. 리사이즈합니다.")
            image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)

        return True

    def preprocess(self, image: Image.Image) -> Image.Image:
        """이미지 전처리.

        Args:
            image: 원본 이미지

        Returns:
            전처리된 이미지
        """
        # RGB로 변환
        if image.mode != "RGB":
            image = image.convert("RGB")

        return image

    @abstractmethod
    async def analyze(
        self,
        image: Union[str, Path, bytes, Image.Image],
        **kwargs,
    ) -> ImageAnalysisResult:
        """이미지 분석.

        Args:
            image: 분석할 이미지
            **kwargs: 추가 파라미터

        Returns:
            분석 결과
        """
        pass

    def _create_error_result(self, error: str) -> ImageAnalysisResult:
        """에러 결과 생성."""
        return ImageAnalysisResult(
            success=False,
            analysis_type=self.name,
            description=f"분석 실패: {error}",
            confidence=0.0,
        )


def encode_image_base64(image: Image.Image, format: str = "JPEG") -> str:
    """이미지를 base64로 인코딩.

    Args:
        image: PIL Image
        format: 이미지 포맷

    Returns:
        base64 인코딩된 문자열
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def resize_image(
    image: Image.Image,
    max_size: int = 512,
    maintain_aspect: bool = True,
) -> Image.Image:
    """이미지 리사이즈.

    Args:
        image: 원본 이미지
        max_size: 최대 크기
        maintain_aspect: 비율 유지 여부

    Returns:
        리사이즈된 이미지
    """
    if maintain_aspect:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return image
    else:
        return image.resize((max_size, max_size), Image.Resampling.LANCZOS)
