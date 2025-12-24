# 실행 런북 (데이터→전처리→API/UI)

## 1) 의존성 설치
```
pip install -r requirements.txt
```

## 2) 데이터 다운로드
- 자동 스크레이프/다운로드(권장):
```
python scripts/01_download_data.py
```
- (선택) 명시 URL 지정:
```
python scripts/01_download_data.py --reviews-url <reviews.parquet> --meta-url <meta.parquet>
```

## 3) 전처리
- 빠른 검증(샘플 RowGroup 1개):
```
python scripts/02_preprocess.py --sample 1
```
- 전체 실행:
```
python scripts/02_preprocess.py
```

## 4) 산출물 확인
```
ls -lh data/processed/*.parquet
python - << 'PY'
import pandas as pd
r = pd.read_parquet('data/processed/reviews.parquet')
p = pd.read_parquet('data/processed/products.parquet')
print(len(r), r.columns.tolist())
print(len(p), p.columns.tolist())
print(p[['price_range','avg_rating','review_count']].describe())
PY
```

## 5) 정책 크롤/정규화/인덱싱(옵션)
```
# configs/crawl.yaml 편집(whitelist_domains/seed_urls)
python scripts/01b_fetch_policies.py
python scripts/01a_crawl_policies.py
python scripts/04_build_index.py
```

## 6) API/UI
```
uvicorn api:app --reload
python ui.py
```

## 트러블슈팅
- datasets 3.x로 Amazon-Reviews-2023 로더 실패 → 자동 스크레이프/URL/로컬 우선 로직 사용
- 대용량으로 오래 걸림 → `--sample` 옵션 검증 후 전체 실행
- src 모듈 임포트 실패 → PYTHONPATH=. 또는 스크립트 경로 보강 적용

