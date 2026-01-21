#!/usr/bin/env python3
from __future__ import annotations

"""학습 데이터(JSONL) 생성 스크립트.

입력: data/processed/products.parquet, reviews.parquet, (선택) bitext 데이터셋
출력: data/processed/training_data.jsonl
"""

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data_prep.download import load_bitext_cs
from src.data_prep.training_data import (
    generate_from_bitext,
    generate_product_summaries,
    write_jsonl,
)


def main() -> None:
    proc_dir = Path("data/processed")
    products_path = proc_dir / "products.parquet"
    if not products_path.exists():
        raise SystemExit("products.parquet not found. Run scripts/02_preprocess.py first.")

    products = pd.read_parquet(products_path)
    out_path = proc_dir / "training_data.jsonl"

    rows = list(generate_product_summaries(products, limit=100))

    try:
        bitext = load_bitext_cs()
        rows.extend(list(generate_from_bitext(bitext, limit=300)))
    except Exception:
        pass

    n = write_jsonl(out_path, rows)
    print(f"Saved {n} conversations → {out_path}")


if __name__ == "__main__":
    main()
