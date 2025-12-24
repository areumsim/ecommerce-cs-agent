"""불량 탐지기.

상품 이미지에서 불량/결함을 탐지합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image, ImageFilter, ImageStat

from .base import BaseImageAnalyzer, ImageAnalysisResult, resize_image

logger = logging.getLogger(__name__)


# 불량 유형
DEFECT_TYPES = [
    "정상",
    "스크래치",
    "찌그러짐",
    "파손",
    "오염",
    "색상 불량",
    "누락 부품",
]


class DefectDetector(BaseImageAnalyzer):
    """불량 탐지기.

    CLIP 모델을 사용하여 상품 이미지에서 불량을 탐지합니다.
    """

    name = "defect_detector"

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
        defect_types: Optional[List[str]] = None,
        **kwargs,
    ) -> ImageAnalysisResult:
        """불량 탐지.

        Args:
            image: 분석할 이미지
            defect_types: 탐지할 불량 유형 목록 (없으면 기본값 사용)

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

            # 불량 유형 분류
            defect_types = defect_types or DEFECT_TYPES
            defect_result = await self._classify_defect(img, defect_types)

            # 불량 영역 탐지 (간단한 에지 분석)
            anomaly_regions = self._detect_anomaly_regions(img)

            # 결과 생성
            is_defective = defect_result.get("defect_type", "정상") != "정상"
            confidence = defect_result.get("confidence", 0.0)

            return ImageAnalysisResult(
                success=True,
                analysis_type="defect",
                description=self._generate_description(defect_result, is_defective),
                confidence=confidence,
                labels=[defect_result.get("defect_type", "")],
                attributes={
                    "defect_type": defect_result.get("defect_type"),
                    "defect_confidence": confidence,
                    "is_defective": is_defective,
                    "all_scores": defect_result.get("all_scores", {}),
                    "anomaly_regions": anomaly_regions,
                },
                bounding_boxes=anomaly_regions,
                raw_output={
                    "defect_result": defect_result,
                },
            )

        except Exception as e:
            self.logger.error(f"불량 탐지 오류: {e}")
            return self._create_error_result(str(e))

    async def _classify_defect(
        self,
        image: Image.Image,
        defect_types: List[str],
    ) -> Dict[str, Any]:
        """불량 유형 분류."""
        import torch

        # 한국어 프롬프트로 CLIP 분류
        prompts = [f"상품 사진, {dt}" for dt in defect_types]

        inputs = self._processor(
            text=prompts,
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
            "defect_type": defect_types[max_idx],
            "confidence": probs_list[max_idx],
            "all_scores": dict(zip(defect_types, probs_list)),
        }

    def _detect_anomaly_regions(self, image: Image.Image) -> List[Dict[str, Any]]:
        """이상 영역 탐지 (간단한 에지 기반 분석).

        실제 프로덕션에서는 세그멘테이션 모델 사용 권장.
        """
        try:
            # 그레이스케일 변환
            gray = image.convert("L")

            # 에지 탐지
            edges = gray.filter(ImageFilter.FIND_EDGES)

            # 이미지를 그리드로 분할하여 분석
            grid_size = 4
            w, h = edges.size
            cell_w, cell_h = w // grid_size, h // grid_size

            regions = []
            threshold = 30  # 에지 강도 임계값

            for row in range(grid_size):
                for col in range(grid_size):
                    x1 = col * cell_w
                    y1 = row * cell_h
                    x2 = x1 + cell_w
                    y2 = y1 + cell_h

                    cell = edges.crop((x1, y1, x2, y2))
                    stat = ImageStat.Stat(cell)
                    mean_edge = stat.mean[0]

                    if mean_edge > threshold:
                        regions.append({
                            "x": x1,
                            "y": y1,
                            "width": cell_w,
                            "height": cell_h,
                            "score": mean_edge / 255.0,
                            "label": "potential_anomaly",
                        })

            return regions

        except Exception as e:
            self.logger.warning(f"이상 영역 탐지 실패: {e}")
            return []

    def _generate_description(
        self,
        defect_result: Dict[str, Any],
        is_defective: bool,
    ) -> str:
        """분석 결과 설명 생성."""
        defect_type = defect_result.get("defect_type", "알 수 없음")
        confidence = defect_result.get("confidence", 0) * 100

        if is_defective:
            return (
                f"불량 발견: {defect_type} (신뢰도 {confidence:.1f}%)\n"
                f"클레임 처리가 필요할 수 있습니다."
            )
        else:
            return f"정상 상품으로 판단됩니다 (신뢰도 {confidence:.1f}%)"


class SimpleDefectDetector(BaseImageAnalyzer):
    """간단한 불량 탐지기.

    CLIP 없이 기본적인 이미지 분석으로 불량을 탐지합니다.
    (PoC용 경량 버전)
    """

    name = "simple_defect_detector"

    async def analyze(
        self,
        image: Union[str, Path, bytes, Image.Image],
        **kwargs,
    ) -> ImageAnalysisResult:
        """기본 불량 탐지."""
        try:
            img = self.load_image(image)
            if not self.validate_image(img):
                return self._create_error_result("유효하지 않은 이미지")

            img = self.preprocess(img)

            # 기본 이미지 품질 분석
            quality_score = self._analyze_image_quality(img)

            # 색상 이상 탐지
            color_anomaly = self._detect_color_anomaly(img)

            # 에지 이상 탐지
            edge_anomaly = self._detect_edge_anomaly(img)

            # 종합 점수
            is_defective = quality_score < 0.7 or color_anomaly or edge_anomaly
            confidence = 1.0 - quality_score if is_defective else quality_score

            defect_type = "정상"
            if color_anomaly:
                defect_type = "색상 불량"
            elif edge_anomaly:
                defect_type = "외형 이상"
            elif quality_score < 0.7:
                defect_type = "품질 저하"

            return ImageAnalysisResult(
                success=True,
                analysis_type="defect",
                description=self._generate_description(defect_type, confidence, is_defective),
                confidence=confidence,
                labels=[defect_type],
                attributes={
                    "defect_type": defect_type,
                    "is_defective": is_defective,
                    "quality_score": quality_score,
                    "color_anomaly": color_anomaly,
                    "edge_anomaly": edge_anomaly,
                },
            )

        except Exception as e:
            return self._create_error_result(str(e))

    def _analyze_image_quality(self, image: Image.Image) -> float:
        """이미지 품질 분석."""
        try:
            # 콘트라스트 분석
            gray = image.convert("L")
            stat = ImageStat.Stat(gray)
            stddev = stat.stddev[0]

            # 표준편차가 낮으면 콘트라스트가 낮음
            contrast_score = min(stddev / 80.0, 1.0)

            # 밝기 분석
            mean_brightness = stat.mean[0]
            brightness_score = 1.0 - abs(mean_brightness - 128) / 128

            # 해상도 점수
            w, h = image.size
            resolution_score = min((w * h) / (224 * 224), 1.0)

            return (contrast_score + brightness_score + resolution_score) / 3

        except Exception:
            return 0.5

    def _detect_color_anomaly(self, image: Image.Image) -> bool:
        """색상 이상 탐지."""
        try:
            stat = ImageStat.Stat(image)

            # RGB 채널 불균형 확인
            r, g, b = stat.mean[:3]
            max_diff = max(abs(r - g), abs(g - b), abs(r - b))

            # 극단적인 색상 불균형
            return max_diff > 100

        except Exception:
            return False

    def _detect_edge_anomaly(self, image: Image.Image) -> bool:
        """에지 이상 탐지."""
        try:
            gray = image.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            stat = ImageStat.Stat(edges)

            # 에지가 너무 많거나 적으면 이상
            mean_edge = stat.mean[0]
            return mean_edge > 100 or mean_edge < 5

        except Exception:
            return False

    def _generate_description(
        self,
        defect_type: str,
        confidence: float,
        is_defective: bool,
    ) -> str:
        """분석 결과 설명 생성."""
        conf_pct = confidence * 100

        if is_defective:
            return f"이상 감지: {defect_type} (신뢰도 {conf_pct:.1f}%)"
        else:
            return f"정상 상품 (신뢰도 {conf_pct:.1f}%)"
