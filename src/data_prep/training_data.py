from __future__ import annotations
"""학습 데이터(ShareGPT 유사) 생성 유틸.

입력
- products.parquet, reviews.parquet
- (선택) bitext CS 데이터셋

출력
- data/processed/training_data.jsonl
"""

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def _product_summary_row(row: pd.Series) -> str:
    return (
        f"{row.get('title','')} 리뷰 요약\n"
        f"평점: {row.get('avg_rating',0):.1f} / 리뷰 수: {row.get('review_count',0)}\n"
        f"가격대: {row.get('price_range','unknown')}"
    )


def generate_product_summaries(products: pd.DataFrame, limit: int = 50) -> Iterable[dict]:
    for _, r in products.head(limit).iterrows():
        user = {"from": "human", "value": f"{r.get('title','')} 리뷰 요약해줘"}
        bot = {"from": "gpt", "value": _product_summary_row(r)}
        yield {"conversations": [user, bot]}


def generate_from_bitext(bitext_ds, limit: int = 200) -> Iterable[dict]:
    seen = 0
    for split in ["train", "validation", "test"]:
        d = bitext_ds.get(split)
        if not d:
            continue
        for rec in d:
            inp = rec.get("input") or rec.get("question") or rec.get("prompt")
            out = rec.get("output") or rec.get("answer") or rec.get("response")
            if not inp or not out:
                continue
            yield {"conversations": [{"from": "human", "value": inp}, {"from": "gpt", "value": out}]}
            seen += 1
            if seen >= limit:
                return


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for obj in rows:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
    return n

