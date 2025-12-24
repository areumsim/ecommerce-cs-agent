"""비전 모듈.

상품 이미지 분석 및 불량 탐지 기능을 제공합니다.
"""

from .base import (
    BaseImageAnalyzer,
    ImageAnalysisResult,
    encode_image_base64,
    resize_image,
)
from .product_analyzer import (
    ProductImageAnalyzer,
    SimpleProductAnalyzer,
    PRODUCT_CATEGORIES,
    PRODUCT_CONDITIONS,
)
from .defect_detector import (
    DefectDetector,
    SimpleDefectDetector,
    DEFECT_TYPES,
)
from .pipeline import (
    VisionPipeline,
    PipelineResult,
    get_pipeline,
    reset_pipeline,
)

__all__ = [
    # Base
    "BaseImageAnalyzer",
    "ImageAnalysisResult",
    "encode_image_base64",
    "resize_image",
    # Product Analyzer
    "ProductImageAnalyzer",
    "SimpleProductAnalyzer",
    "PRODUCT_CATEGORIES",
    "PRODUCT_CONDITIONS",
    # Defect Detector
    "DefectDetector",
    "SimpleDefectDetector",
    "DEFECT_TYPES",
    # Pipeline
    "VisionPipeline",
    "PipelineResult",
    "get_pipeline",
    "reset_pipeline",
]


# 편의 함수: 기본 분석기 인스턴스 생성
def get_product_analyzer(use_clip: bool = False) -> BaseImageAnalyzer:
    """상품 분석기 인스턴스 반환.

    Args:
        use_clip: CLIP 모델 사용 여부

    Returns:
        상품 분석기 인스턴스
    """
    if use_clip:
        return ProductImageAnalyzer()
    return SimpleProductAnalyzer()


def get_defect_detector(use_clip: bool = False) -> BaseImageAnalyzer:
    """불량 탐지기 인스턴스 반환.

    Args:
        use_clip: CLIP 모델 사용 여부

    Returns:
        불량 탐지기 인스턴스
    """
    if use_clip:
        return DefectDetector()
    return SimpleDefectDetector()
