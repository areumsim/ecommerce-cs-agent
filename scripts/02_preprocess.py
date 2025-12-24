#!/usr/bin/env python3
from __future__ import annotations

"""Amazon 리뷰/메타데이터 전처리 스크립트.

입력(둘 중 하나)
- data/raw/*.parquet (01_download_data.py 산출)
- 또는 datasets에서 직접 로드(네트워크 필요)

옵션
- --sample <N>: pyarrow로 첫 RowGroup N개만 읽어 샘플 처리(빠른 검증용)
"""

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import pandas as pd
import pyarrow.parquet as pq

from src.data_prep.download import load_amazon_metadata_electronics, load_amazon_reviews_electronics
from src.data_prep.preprocess import preprocess_products, preprocess_reviews, save_parquet


def read_or_load(raw_path: Path, loader, sample_row_groups: int | None = None, columns: list[str] | None = None):
    if raw_path.exists():
        if sample_row_groups:
            pf = pq.ParquetFile(raw_path)
            tables = []
            take = min(sample_row_groups, pf.metadata.num_row_groups)
            for i in range(take):
                tables.append(pf.read_row_group(i, columns=columns))
            import pyarrow as pa
            return pa.concat_tables(tables).to_pandas()
        return pd.read_parquet(raw_path, columns=columns)
    ds = loader()
    return ds.to_pandas()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None, help="첫 RowGroup N개만 읽어서 빠르게 처리")
    args = ap.parse_args()

    raw_dir = Path("data/raw")
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 최소 컬럼만 먼저 읽어서 메모리/속도 최적화
    r_cols = ["reviewerID","asin","reviewText","overall","summary","unixReviewTime","user_id","text","rating","title","timestamp","verified_purchase","helpful_vote"]
    m_cols = ["asin","parent_asin","title","brand","category","main_category","price","imageURL","details","average_rating","rating_number"]

    reviews_raw = read_or_load(raw_dir / "amazon_reviews_electronics.parquet", load_amazon_reviews_electronics, sample_row_groups=args.sample, columns=r_cols)
    meta_raw = read_or_load(raw_dir / "amazon_metadata_electronics.parquet", load_amazon_metadata_electronics, sample_row_groups=args.sample, columns=m_cols)

    reviews_df = preprocess_reviews(reviews_raw)
    products_df = preprocess_products(meta_raw, reviews_df)

    save_parquet(reviews_df, out_dir / "reviews.parquet")
    save_parquet(products_df, out_dir / "products.parquet")
    print("Saved:", out_dir / "reviews.parquet", ",", out_dir / "products.parquet")


if __name__ == "__main__":
    main()
