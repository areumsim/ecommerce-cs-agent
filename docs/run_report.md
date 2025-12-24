## 실행 보고서 (초기 데이터 파이프라인 검증)

### 환경/전제
- Repo: ar_agent (현재 워크스페이스)
- 의존성: `pip install -r requirements.txt`
- 데이터 소스: Amazon Reviews/Metadata (Electronics)
- 네트워크: 허용 (인덱스 스크레이프/다운로드), 제한 시 수동 배치 가능

### 수행 순서 및 결과
1) 원본 파일 존재/크기 확인
- data/raw/amazon_reviews_electronics.parquet: 8.4G
- data/raw/amazon_metadata_electronics.parquet: 1.8G

2) 스키마/메타 점검 (pyarrow)
- reviews rows: 43,886,944 | row_groups: 42
- meta    rows: 1,610,012  | row_groups: 2
- 원본 컬럼(발췌)
  - reviews: ['rating','title','text','asin','user_id','timestamp','helpful_vote','verified_purchase', ...]
  - meta   : ['main_category','title','average_rating','rating_number','price','details','parent_asin', ...]

3) 전처리 실행 (샘플 모드)
- 명령: `python scripts/02_preprocess.py --sample 1`
- 산출: data/processed/reviews.parquet, products.parquet
- 요약
  - reviews: 804,607 rows | cols: ['review_id','product_id','user_id','rating','title','text','sentiment','timestamp','verified','helpful_votes']
  - products: 364,802 rows | cols: ['product_id','title','brand','category','category_main','price','price_range','image_url','description','avg_rating','review_count']
- 소요: ~46초 (샘플 1 RowGroup 기준)

4) 전체 실행 가이드
- 샘플 모드 제거: `python scripts/02_preprocess.py` (수십 분 소요 가능)
- 메모리/시간 최적화: pyarrow RowGroup 단위로 읽음(코드 반영 완료)

### 이슈 및 수정 내역
- datasets v3 차단 → 인덱스 스크레이프/직접 URL/로컬 우선 로직 구현
- src 임포트 오류 → 실행 스크립트 `sys.path` 보강, `src/__init__.py` 추가
- 전처리 오류(verified 스칼라) → 안전 처리로 수정, rating/helpful_votes 파싱 강화
- 메타 스키마 상이 → 'main_category','average_rating','rating_number','parent_asin' 매핑 보강
- 대용량 → `--sample` 옵션 추가, 최소 컬럼 로딩

### 다음 작업 제안
- 전체 전처리(샘플 제거) 실행 후 결과 점검
- 정책 크롤/정규화/인덱싱 연동 → UI 정책 검색 검증
- API/UI 스모크: `/healthz`, `/policies/search`, UI 주문 액션/정책 패널

