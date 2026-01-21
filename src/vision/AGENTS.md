# VISION MODULE

Product image analysis and defect detection using CLIP/simple models.

## STRUCTURE

```
vision/
├── base.py            # BaseImageAnalyzer ABC, ImageAnalysisResult
├── product_analyzer.py # ProductImageAnalyzer (CLIP), SimpleProductAnalyzer
├── defect_detector.py  # DefectDetector (CLIP), SimpleDefectDetector
└── pipeline.py         # VisionPipeline: multi-analyzer orchestration
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add analyzer | `base.py` | Extend `BaseImageAnalyzer`, implement `analyze()` |
| Add defect type | `defect_detector.py` | Update `DEFECT_TYPES` dict |
| Add product category | `product_analyzer.py` | Update `PRODUCT_CATEGORIES` |
| Modify pipeline | `pipeline.py` | `VisionPipeline.add_analyzer()` |
| Change image size | `pipeline.py` | `max_image_size` param |

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `BaseImageAnalyzer` | ABC with `load_image()`, `validate_image()`, `analyze()` |
| `ImageAnalysisResult` | Dataclass: success, labels, confidence, attributes |
| `ProductImageAnalyzer` | CLIP-based product classification |
| `SimpleProductAnalyzer` | Rule-based fallback (no CLIP) |
| `DefectDetector` | CLIP-based defect detection |
| `SimpleDefectDetector` | Rule-based fallback (no CLIP) |
| `VisionPipeline` | Multi-analyzer orchestration |
| `PipelineResult` | Aggregated analysis with recommendations |

## FLOW

```
Image input (path/bytes/PIL.Image)
    |
VisionPipeline.analyze(image)
    |
    +-- Load & preprocess (RGB, resize)
    |
    +-- Run analyzers (parallel or sequential)
    |   +-- ProductImageAnalyzer → category, condition
    |   +-- DefectDetector → defect labels, severity
    |
    +-- Aggregate results
    |
    +-- Generate recommendations
    |
PipelineResult(analyses, summary, recommendations)
```

## USAGE

```python
from src.vision import get_pipeline

pipeline = get_pipeline(use_clip=True)
result = await pipeline.analyze("product.jpg")

# Access individual results
product_result = result.analyses.get("product")
defect_result = result.analyses.get("defect")

# Get recommendations
for rec in result.recommendations:
    print(rec)  # "스크래치가 발견되었습니다. 교환을 권장합니다."
```

## CONVENTIONS

- **Async only**: All `analyze()` methods are async
- **Lazy loading**: CLIP models loaded on first use
- **Fallback**: Simple analyzers work without CLIP (rule-based)
- **Korean messages**: Recommendations in Korean

## ANTI-PATTERNS

- **Never import CLIP at module level** - use lazy loading
- **Don't skip validation** - always call `validate_image()`
- **Don't block on analysis** - use async/await
