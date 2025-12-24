#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import time
from collections import defaultdict
from typing import Dict

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data_prep.preprocess import preprocess_reviews, preprocess_products, save_parquet


RAW_REVIEWS = Path("data/raw/amazon_reviews_electronics.parquet")
RAW_META = Path("data/raw/amazon_metadata_electronics.parquet")
OUT_DIR = Path("data/processed")
OUT_REVIEWS = OUT_DIR / "reviews.parquet"
OUT_PRODUCTS = OUT_DIR / "products.parquet"
OUT_REVIEWS_AGG = OUT_DIR / "reviews_agg.parquet"


def stream_reviews() -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pf = pq.ParquetFile(RAW_REVIEWS)
    writer = None
    agg_sum: Dict[str, float] = defaultdict(float)
    agg_cnt: Dict[str, int] = defaultdict(int)

    cols = [
        "reviewerID","asin","reviewText","overall","summary","unixReviewTime",
        "user_id","product_id","text","rating","title","timestamp",
        "verified_purchase","helpful_vote","verified","vote"
    ]
    cols = [c for c in cols if c in pf.schema.names]

    start = time.time()
    total = pf.metadata.num_row_groups
    for i in range(total):
        t0 = time.time()
        tbl = pf.read_row_group(i, columns=cols)
        df = tbl.to_pandas()
        df_p = preprocess_reviews(df)

        for pid, grp in df_p.groupby("product_id"):
            agg_sum[pid] += grp["rating"].sum()
            agg_cnt[pid] += grp["rating"].count()

        tab = pa.Table.from_pandas(df_p, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(OUT_REVIEWS.as_posix(), tab.schema)
        writer.write_table(tab)

        done = i + 1
        dt = time.time() - t0
        eta = (time.time() - start) / max(1, done) * (total - done)
        print(f"[reviews] row_group {done}/{total} done in {dt:.1f}s, ETA ~{eta/60:.1f}m")
    if writer is not None:
        writer.close()

    agg = pd.DataFrame({
        "product_id": list(agg_sum.keys()),
        "sum_rating": [agg_sum[k] for k in agg_sum.keys()],
        "review_count": [agg_cnt[k] for k in agg_sum.keys()],
    })
    agg["avg_rating"] = (agg["sum_rating"] / agg["review_count"].replace(0, pd.NA)).fillna(0.0)
    save_parquet(agg[["product_id","avg_rating","review_count"]], OUT_REVIEWS_AGG)
    print(f"[reviews] wrote {OUT_REVIEWS}, agg → {OUT_REVIEWS_AGG}")
    return agg


def build_products(agg: pd.DataFrame) -> None:
    meta = pd.read_parquet(RAW_META)
    prod = preprocess_products(meta, pd.DataFrame({"product_id": [], "rating": []}))
    prod = prod.drop(columns=["avg_rating","review_count"], errors="ignore").merge(
        agg, on="product_id", how="left"
    )
    prod["avg_rating"] = prod["avg_rating"].fillna(0.0)
    prod["review_count"] = prod["review_count"].fillna(0).astype(int)
    save_parquet(prod, OUT_PRODUCTS)
    print(f"[products] wrote {OUT_PRODUCTS}")


def main() -> None:
    print("[start] streaming full reviews → processed + agg")
    agg = stream_reviews()
    print("[start] build products using metadata + reviews agg")
    build_products(agg)
    print("[done] all outputs ready")


if __name__ == "__main__":
    main()

