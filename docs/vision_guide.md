# 비전 파이프라인 가이드

이 문서는 이미지 분석을 위한 비전 모듈 사용법을 설명합니다.

## 개요

비전 모듈은 상품 이미지 분석과 불량 탐지 기능을 제공합니다:

- **ProductImageAnalyzer**: 상품 카테고리, 상태, 특성 분석
- **DefectDetector**: 스크래치, 찌그러짐, 오염 등 불량 탐지
- **VisionPipeline**: 여러 분석기를 조합한 종합 분석

---

## 빠른 시작

### 기본 사용법

```python
from src.vision import get_pipeline

# 기본 파이프라인 (상품 분석 + 불량 탐지)
pipeline = get_pipeline()

# 이미지 분석
result = await pipeline.analyze("product_image.jpg")

print(f"성공: {result.success}")
print(f"요약: {result.summary}")
print(f"신뢰도: {result.confidence}")
print(f"권장사항: {result.recommendations}")
```

### 분석 결과 구조

```python
@dataclass
class PipelineResult:
    success: bool                         # 분석 성공 여부
    image_info: Dict[str, Any]            # 이미지 정보 (크기, 형식 등)
    analyses: Dict[str, ImageAnalysisResult]  # 분석기별 결과
    summary: str                          # 종합 요약
    confidence: float                     # 평균 신뢰도
    recommendations: List[str]            # 권장 사항
    metadata: Dict[str, Any]              # 메타데이터
```

---

## 분석기 종류

### 1. 상품 분석기 (ProductAnalyzer)

상품의 카테고리, 상태, 특성을 분석합니다.

```python
from src.vision import get_product_analyzer

analyzer = get_product_analyzer()
result = await analyzer.analyze("product.jpg")

print(result.labels)       # ["의류", "상의", "티셔츠"]
print(result.attributes)   # {"category": "clothing", "condition": "new"}
```

**지원 카테고리**:
- `clothing`: 의류
- `electronics`: 전자제품
- `furniture`: 가구
- `cosmetics`: 화장품
- `food`: 식품
- `other`: 기타

**상태 분류**:
- `new`: 새 상품
- `used`: 중고
- `damaged`: 손상됨

### 2. 불량 탐지기 (DefectDetector)

이미지에서 불량을 탐지합니다.

```python
from src.vision import get_defect_detector

detector = get_defect_detector()
result = await detector.analyze("product.jpg")

print(result.labels)       # ["scratch", "dent"]
print(result.bounding_boxes)  # [{"label": "scratch", "x": 100, "y": 50, ...}]
```

**탐지 가능 불량**:
- `scratch`: 스크래치
- `dent`: 찌그러짐
- `stain`: 오염
- `crack`: 균열
- `tear`: 찢어짐
- `discoloration`: 변색

---

## VisionPipeline 사용법

### 기본 파이프라인

```python
from src.vision import get_pipeline

# 기본 설정 (상품 + 불량 분석기 포함)
pipeline = get_pipeline()

result = await pipeline.analyze("image.jpg")
```

### 커스텀 파이프라인

```python
from src.vision import VisionPipeline, get_product_analyzer, get_defect_detector

# 커스텀 파이프라인 생성
pipeline = VisionPipeline(
    max_image_size=1024,  # 최대 이미지 크기
    parallel=True,         # 병렬 실행
)

# 분석기 추가
pipeline.add_analyzer("product", get_product_analyzer())
pipeline.add_analyzer("defect", get_defect_detector())

# 체이닝 지원
pipeline = (
    VisionPipeline()
    .add_analyzer("product", get_product_analyzer())
    .add_analyzer("defect", get_defect_detector())
)
```

### 특정 분석기만 실행

```python
# 상품 분석만 실행
result = await pipeline.analyze("image.jpg", analyzers=["product"])

# 불량 탐지만 실행
result = await pipeline.analyze("image.jpg", analyzers=["defect"])
```

### 분석기 관리

```python
# 등록된 분석기 목록
print(pipeline.list_analyzers())  # ["product", "defect"]

# 분석기 제거
pipeline.remove_analyzer("defect")

# 파이프라인 리셋
from src.vision import reset_pipeline
reset_pipeline()
```

---

## 이미지 입력 형식

파이프라인은 다양한 이미지 입력을 지원합니다:

```python
# 1. 파일 경로
result = await pipeline.analyze("./images/product.jpg")
result = await pipeline.analyze(Path("./images/product.jpg"))

# 2. 바이트 데이터
with open("product.jpg", "rb") as f:
    image_bytes = f.read()
result = await pipeline.analyze(image_bytes)

# 3. PIL Image 객체
from PIL import Image
img = Image.open("product.jpg")
result = await pipeline.analyze(img)

# 4. Base64 인코딩 (data URL)
base64_image = "data:image/jpeg;base64,/9j/4AAQSkZ..."
result = await pipeline.analyze(base64_image)
```

**지원 형식**: JPEG, PNG, WebP, GIF

---

## API 엔드포인트

### 이미지 분석 API

```http
POST /vision/analyze
Content-Type: application/json
```

**Request:**
```json
{
  "image_base64": "/9j/4AAQSkZJRg...",
  "analysis_type": "product"
}
```

**Response:**
```json
{
  "success": true,
  "description": "흰색 면 티셔츠, 새 상품 상태",
  "confidence": 0.92,
  "labels": ["clothing", "t-shirt", "white"],
  "attributes": {
    "category": "clothing",
    "condition": "new",
    "color": "white"
  }
}
```

### 불량 탐지 API

```http
POST /vision/defect
Content-Type: application/json
```

**Request:**
```json
{
  "image_base64": "/9j/4AAQSkZJRg..."
}
```

**Response:**
```json
{
  "success": true,
  "description": "스크래치 1건 발견",
  "confidence": 0.87,
  "labels": ["scratch"],
  "bounding_boxes": [
    {
      "label": "scratch",
      "x": 150,
      "y": 80,
      "width": 50,
      "height": 10,
      "confidence": 0.87
    }
  ]
}
```

---

## 결과 해석

### 신뢰도 점수

| 범위 | 해석 |
|------|------|
| 0.9 ~ 1.0 | 매우 높음 - 결과 신뢰 가능 |
| 0.7 ~ 0.9 | 높음 - 대부분 정확 |
| 0.5 ~ 0.7 | 중간 - 확인 권장 |
| 0.0 ~ 0.5 | 낮음 - 수동 검토 필요 |

### 권장사항 자동 생성

파이프라인은 분석 결과를 기반으로 권장사항을 자동 생성합니다:

```python
result = await pipeline.analyze("damaged_product.jpg")

for rec in result.recommendations:
    print(rec)
# 출력:
# "스크래치가 발견되었습니다. 교환을 권장합니다."
# "상품 상태가 불량입니다. 클레임 접수를 권장합니다."
```

---

## CLIP 모델 사용 (선택)

고급 분석을 위해 CLIP 모델을 사용할 수 있습니다:

```python
# CLIP 기반 분석기 사용
pipeline = get_pipeline(use_clip=True)

# 또는 개별 분석기
analyzer = get_product_analyzer(use_clip=True)
detector = get_defect_detector(use_clip=True)
```

**요구사항**:
```bash
pip install transformers torch
```

**참고**: CLIP 모델은 더 정확하지만 더 많은 리소스를 사용합니다.

---

## 설정

### 이미지 전처리

```python
pipeline = VisionPipeline(
    max_image_size=1024,  # 최대 크기 (자동 리사이즈)
    parallel=True,         # 병렬 실행 여부
)
```

### 병렬 vs 순차 실행

```python
# 병렬 실행 (빠름, 기본값)
pipeline = VisionPipeline(parallel=True)

# 순차 실행 (리소스 절약)
pipeline = VisionPipeline(parallel=False)
```

---

## 에러 처리

```python
result = await pipeline.analyze("image.jpg")

if not result.success:
    print(f"분석 실패: {result.summary}")
    return

# 개별 분석기 결과 확인
for name, analysis in result.analyses.items():
    if not analysis.success:
        print(f"{name} 분석 실패: {analysis.description}")
```

### 일반적인 에러

| 에러 | 원인 | 해결 |
|------|------|------|
| `FileNotFoundError` | 이미지 파일 없음 | 파일 경로 확인 |
| `ValueError` | 지원하지 않는 형식 | JPEG/PNG/WebP 사용 |
| `분석 실패` | 모델 오류 | 이미지 품질 확인 |

---

## 관련 파일

- `src/vision/pipeline.py` - VisionPipeline 구현
- `src/vision/base.py` - 기본 분석기 인터페이스
- `src/vision/product_analyzer.py` - 상품 분석기
- `src/vision/defect_detector.py` - 불량 탐지기
- `api.py` - REST API 엔드포인트
