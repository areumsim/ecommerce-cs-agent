#!/usr/bin/env python3
from __future__ import annotations

"""Amazon Reviews/Metadata, Bitext CS 데이터 다운로드 스크립트.

주의: 네트워크/패키지(datasets)가 필요합니다.
"""

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.data_prep.download import (
    load_amazon_metadata_electronics,
    load_amazon_reviews_electronics,
    load_bitext_cs,
)
import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews-url", dest="reviews_url", default=None)
    ap.add_argument("--meta-url", dest="meta_url", default=None)
    args = ap.parse_args()
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading Amazon Reviews (Electronics)...")
    reviews = load_amazon_reviews_electronics(split="full", url=args.reviews_url)
    reviews_path = raw_dir / "amazon_reviews_electronics.parquet"
    reviews.to_parquet(reviews_path.as_posix())
    print(f"Saved: {reviews_path}")

    print("Downloading Amazon Metadata (Electronics)...")
    meta = load_amazon_metadata_electronics(split="full", url=args.meta_url)
    meta_path = raw_dir / "amazon_metadata_electronics.parquet"
    meta.to_parquet(meta_path.as_posix())
    print(f"Saved: {meta_path}")

    print("Downloading Bitext CS dataset (optional)...")
    try:
        ds = load_bitext_cs()
        (raw_dir / "bitext_cs_downloaded.txt").write_text("ok", encoding="utf-8")
        print("Bitext CS downloaded (cached by datasets).")
    except Exception as e:
        print(f"Skip bitext: {e}")


if __name__ == "__main__":
    main()
