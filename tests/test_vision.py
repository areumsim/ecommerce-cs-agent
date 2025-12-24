"""비전 모듈 테스트."""

import pytest
from io import BytesIO
from PIL import Image

from src.vision import (
    ImageAnalysisResult,
    SimpleProductAnalyzer,
    SimpleDefectDetector,
    get_product_analyzer,
    get_defect_detector,
)


def create_test_image(color: tuple = (255, 0, 0), size: tuple = (100, 100)) -> Image.Image:
    """테스트용 이미지 생성."""
    return Image.new("RGB", size, color)


def create_test_image_bytes(color: tuple = (255, 0, 0), size: tuple = (100, 100)) -> bytes:
    """테스트용 이미지 bytes 생성."""
    img = create_test_image(color, size)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestImageAnalysisResult:
    """ImageAnalysisResult 테스트."""

    def test_create_success_result(self):
        """성공 결과 생성."""
        result = ImageAnalysisResult(
            success=True,
            analysis_type="product",
            description="테스트 설명",
            confidence=0.95,
            labels=["의류"],
        )
        assert result.success is True
        assert result.analysis_type == "product"
        assert result.confidence == 0.95
        assert "의류" in result.labels

    def test_create_error_result(self):
        """에러 결과 생성."""
        result = ImageAnalysisResult(
            success=False,
            analysis_type="product",
            description="분석 실패: 오류 메시지",
            confidence=0.0,
        )
        assert result.success is False
        assert "실패" in result.description


class TestSimpleProductAnalyzer:
    """SimpleProductAnalyzer 테스트."""

    @pytest.fixture
    def analyzer(self):
        return SimpleProductAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_pil_image(self, analyzer):
        """PIL 이미지 분석."""
        img = create_test_image((255, 0, 0))
        result = await analyzer.analyze(img)

        assert result.success is True
        assert result.analysis_type == "product"
        assert result.confidence == 1.0
        assert "width" in result.attributes
        assert result.attributes["width"] == 100

    @pytest.mark.asyncio
    async def test_analyze_bytes_image(self, analyzer):
        """bytes 이미지 분석."""
        img_bytes = create_test_image_bytes((0, 255, 0))
        result = await analyzer.analyze(img_bytes)

        assert result.success is True
        assert "dominant_colors" in result.attributes

    @pytest.mark.asyncio
    async def test_analyze_invalid_image(self, analyzer):
        """잘못된 이미지 분석."""
        # 너무 작은 이미지
        img = Image.new("RGB", (5, 5), (255, 255, 255))
        result = await analyzer.analyze(img)

        assert result.success is False
        assert "유효하지 않은" in result.description

    @pytest.mark.asyncio
    async def test_color_detection(self, analyzer):
        """색상 감지 테스트."""
        # 흰색 이미지
        white_img = create_test_image((255, 255, 255))
        result = await analyzer.analyze(white_img)
        assert "흰색" in result.attributes.get("dominant_colors", [])

        # 검정색 이미지
        black_img = create_test_image((0, 0, 0))
        result = await analyzer.analyze(black_img)
        assert "검정" in result.attributes.get("dominant_colors", [])


class TestSimpleDefectDetector:
    """SimpleDefectDetector 테스트."""

    @pytest.fixture
    def detector(self):
        return SimpleDefectDetector()

    @pytest.mark.asyncio
    async def test_analyze_normal_image(self, detector):
        """정상 이미지 분석."""
        img = create_test_image((128, 128, 128))  # 균일한 회색
        result = await detector.analyze(img)

        assert result.success is True
        assert result.analysis_type == "defect"
        assert "defect_type" in result.attributes

    @pytest.mark.asyncio
    async def test_analyze_bytes_image(self, detector):
        """bytes 이미지 분석."""
        img_bytes = create_test_image_bytes()
        result = await detector.analyze(img_bytes)

        assert result.success is True
        assert "is_defective" in result.attributes

    @pytest.mark.asyncio
    async def test_analyze_invalid_image(self, detector):
        """잘못된 이미지 분석."""
        img = Image.new("RGB", (5, 5))
        result = await detector.analyze(img)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_quality_analysis(self, detector):
        """품질 분석 테스트."""
        # 고품질 이미지 (적당한 콘트라스트)
        high_quality = Image.new("RGB", (200, 200))
        for x in range(200):
            for y in range(200):
                val = (x + y) % 256
                high_quality.putpixel((x, y), (val, val, val))

        result = await detector.analyze(high_quality)
        assert result.success is True
        assert "quality_score" in result.attributes


class TestFactoryFunctions:
    """팩토리 함수 테스트."""

    def test_get_product_analyzer_simple(self):
        """간단한 상품 분석기 생성."""
        analyzer = get_product_analyzer(use_clip=False)
        assert isinstance(analyzer, SimpleProductAnalyzer)

    def test_get_defect_detector_simple(self):
        """간단한 불량 탐지기 생성."""
        detector = get_defect_detector(use_clip=False)
        assert isinstance(detector, SimpleDefectDetector)


class TestImageLoading:
    """이미지 로딩 테스트."""

    @pytest.fixture
    def analyzer(self):
        return SimpleProductAnalyzer()

    @pytest.mark.asyncio
    async def test_load_pil_image(self, analyzer):
        """PIL Image 로딩."""
        img = create_test_image()
        loaded = analyzer.load_image(img)
        assert isinstance(loaded, Image.Image)
        assert loaded.size == (100, 100)

    @pytest.mark.asyncio
    async def test_load_bytes_image(self, analyzer):
        """bytes 이미지 로딩."""
        img_bytes = create_test_image_bytes()
        loaded = analyzer.load_image(img_bytes)
        assert isinstance(loaded, Image.Image)

    def test_validate_image_valid(self, analyzer):
        """유효한 이미지 검증."""
        img = create_test_image()
        assert analyzer.validate_image(img) is True

    def test_validate_image_too_small(self, analyzer):
        """너무 작은 이미지 검증."""
        img = Image.new("RGB", (5, 5))
        assert analyzer.validate_image(img) is False

    def test_validate_image_none(self, analyzer):
        """None 이미지 검증."""
        assert analyzer.validate_image(None) is False

    def test_preprocess_rgba_to_rgb(self, analyzer):
        """RGBA -> RGB 변환."""
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        processed = analyzer.preprocess(img)
        assert processed.mode == "RGB"
