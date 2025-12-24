"""상품 이미지 분석기.

상품 이미지를 분석하여 카테고리, 속성 등을 추출합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from .base import BaseImageAnalyzer, ImageAnalysisResult, resize_image

logger = logging.getLogger(__name__)


# 상품 카테고리 (CLIP 텍스트 프롬프트용)
PRODUCT_CATEGORIES = [
    "의류 - 상의",
    "의류 - 하의",
    "의류 - 원피스",
    "신발",
    "가방",
    "액세서리",
    "화장품",
    "전자제품",
    "가구",
    "식품",
    "기타",
]

# 상품 상태
PRODUCT_CONDITIONS = [
    "새 상품",
    "포장 손상",
    "제품 파손",
    "오염",
    "정상",
]


class ProductImageAnalyzer(BaseImageAnalyzer):
    """상품 이미지 분석기.

    CLIP 모델을 사용하여 상품 이미지를 분석합니다.
    """

    name = "product_analyzer"

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        super().__init__()
        self.model_name = model_name
        self._model = None
        self._processor = None

    def _load_model(self):
        """모델 지연 로딩."""
        if self._model is not None:
            return

        try:
            from transformers import CLIPProcessor, CLIPModel

            self.logger.info(f"CLIP 모델 로딩: {self.model_name}")
            self._model = CLIPModel.from_pretrained(self.model_name)
            self._processor = CLIPProcessor.from_pretrained(self.model_name)
            self.logger.info("CLIP 모델 로딩 완료")
        except Exception as e:
            self.logger.error(f"CLIP 모델 로딩 실패: {e}")
            raise

    async def analyze(
        self,
        image: Union[str, Path, bytes, Image.Image],
        categories: Optional[List[str]] = None,
        **kwargs,
    ) -> ImageAnalysisResult:
        """상품 이미지 분석.

        Args:
            image: 분석할 이미지
            categories: 분류할 카테고리 목록 (없으면 기본값 사용)

        Returns:
            분석 결과
        """
        try:
            # 이미지 로드 및 전처리
            img = self.load_image(image)
            if not self.validate_image(img):
                return self._create_error_result("유효하지 않은 이미지")

            img = self.preprocess(img)
            img = resize_image(img, max_size=224)

            # 모델 로드
            self._load_model()

            # 카테고리 분류
            categories = categories or PRODUCT_CATEGORIES
            category_result = await self._classify_category(img, categories)

            # 상태 분석
            condition_result = await self._analyze_condition(img)

            # 결과 통합
            return ImageAnalysisResult(
                success=True,
                analysis_type="product",
                description=self._generate_description(category_result, condition_result),
                confidence=category_result.get("confidence", 0.0),
                labels=[category_result.get("category", "")],
                attributes={
                    "category": category_result.get("category"),
                    "category_confidence": category_result.get("confidence"),
                    "condition": condition_result.get("condition"),
                    "condition_confidence": condition_result.get("confidence"),
                    "all_categories": category_result.get("all_scores", {}),
                },
                raw_output={
                    "category_result": category_result,
                    "condition_result": condition_result,
                },
            )

        except Exception as e:
            self.logger.error(f"상품 이미지 분석 오류: {e}")
            return self._create_error_result(str(e))

    async def _classify_category(
        self,
        image: Image.Image,
        categories: List[str],
    ) -> Dict[str, Any]:
        """카테고리 분류."""
        import torch

        inputs = self._processor(
            text=categories,
            images=image,
            return_tensors="pt",
            padding=True,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)

        probs_list = probs[0].tolist()
        max_idx = probs_list.index(max(probs_list))

        return {
            "category": categories[max_idx],
            "confidence": probs_list[max_idx],
            "all_scores": dict(zip(categories, probs_list)),
        }

    async def _analyze_condition(self, image: Image.Image) -> Dict[str, Any]:
        """상품 상태 분석."""
        import torch

        inputs = self._processor(
            text=PRODUCT_CONDITIONS,
            images=image,
            return_tensors="pt",
            padding=True,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)

        probs_list = probs[0].tolist()
        max_idx = probs_list.index(max(probs_list))

        return {
            "condition": PRODUCT_CONDITIONS[max_idx],
            "confidence": probs_list[max_idx],
            "all_scores": dict(zip(PRODUCT_CONDITIONS, probs_list)),
        }

    def _generate_description(
        self,
        category_result: Dict[str, Any],
        condition_result: Dict[str, Any],
    ) -> str:
        """분석 결과 설명 생성."""
        category = category_result.get("category", "알 수 없음")
        cat_conf = category_result.get("confidence", 0) * 100
        condition = condition_result.get("condition", "알 수 없음")
        cond_conf = condition_result.get("confidence", 0) * 100

        return (
            f"카테고리: {category} (신뢰도 {cat_conf:.1f}%)\n"
            f"상품 상태: {condition} (신뢰도 {cond_conf:.1f}%)"
        )


class SimpleProductAnalyzer(BaseImageAnalyzer):
    """간단한 상품 이미지 분석기.

    CLIP 없이 기본적인 이미지 분석만 수행합니다.
    (PoC용 경량 버전)
    """

    name = "simple_product_analyzer"

    async def analyze(
        self,
        image: Union[str, Path, bytes, Image.Image],
        **kwargs,
    ) -> ImageAnalysisResult:
        """기본 이미지 분석."""
        try:
            img = self.load_image(image)
            if not self.validate_image(img):
                return self._create_error_result("유효하지 않은 이미지")

            img = self.preprocess(img)

            # 기본 이미지 속성 추출
            attributes = {
                "width": img.width,
                "height": img.height,
                "format": img.format or "unknown",
                "mode": img.mode,
                "aspect_ratio": round(img.width / img.height, 2),
            }

            # 색상 분석 (간단한 히스토그램)
            colors = self._analyze_colors(img)
            attributes["dominant_colors"] = colors

            return ImageAnalysisResult(
                success=True,
                analysis_type="product",
                description=f"이미지 크기: {img.width}x{img.height}, 주요 색상: {', '.join(colors[:3])}",
                confidence=1.0,
                labels=colors[:3],
                attributes=attributes,
            )

        except Exception as e:
            return self._create_error_result(str(e))

    def _analyze_colors(self, image: Image.Image) -> List[str]:
        """주요 색상 분석."""
        # 이미지를 작게 리사이즈하여 색상 추출
        small = image.resize((50, 50))
        colors = small.getcolors(maxcolors=2500)

        if not colors:
            return ["알 수 없음"]

        # 가장 많은 색상 추출
        sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)

        color_names = []
        for count, rgb in sorted_colors[:5]:
            name = self._rgb_to_name(rgb)
            if name not in color_names:
                color_names.append(name)

        return color_names[:3] if color_names else ["알 수 없음"]

    def _rgb_to_name(self, rgb: tuple) -> str:
        """RGB를 색상 이름으로 변환."""
        if len(rgb) == 4:
            r, g, b, _ = rgb
        else:
            r, g, b = rgb

        # 간단한 색상 매핑
        if r > 200 and g > 200 and b > 200:
            return "흰색"
        if r < 50 and g < 50 and b < 50:
            return "검정"
        if r > 200 and g < 100 and b < 100:
            return "빨강"
        if r < 100 and g > 200 and b < 100:
            return "초록"
        if r < 100 and g < 100 and b > 200:
            return "파랑"
        if r > 200 and g > 200 and b < 100:
            return "노랑"
        if r > 200 and g < 150 and b > 200:
            return "분홍"
        if r > 150 and g > 100 and b < 100:
            return "주황"
        if r > 100 and g > 100 and b > 100:
            return "회색"
        return "기타"
