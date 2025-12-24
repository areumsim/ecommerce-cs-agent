from __future__ import annotations
"""Amazon 리뷰/메타데이터 전처리 파이프라인.

출력
- data/processed/reviews.parquet
- data/processed/products.parquet
"""

from pathlib import Path
from typing import Iterable

import pandas as pd


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    a = sum(1 for c in text if ord(c) < 128)
    return a / max(1, len(text))


def preprocess_reviews(df: pd.DataFrame) -> pd.DataFrame:
    # rename (flexible)
    rename_map = {
        "reviewerID": "user_id",
        "reviewText": "text",
        "overall": "rating",
        "summary": "title",
        "unixReviewTime": "timestamp",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "product_id" not in df.columns and "asin" in df.columns:
        df = df.rename(columns={"asin": "product_id"})

    # filter
    df = df.dropna(subset=["text", "product_id", "user_id"]).copy()
    df = df[df["text"].astype(str).str.len() >= 50]
    df = df[_ascii_ratio_series(df["text"].astype(str)) >= 0.8]

    # sentiment label from rating
    def _sent(r: float) -> str:
        if r <= 2:
            return "negative"
        if r == 3:
            return "neutral"
        return "positive"

    # rating may be int/str → coerce safely
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0).astype(float)
    df["sentiment"] = df["rating"].map(_sent)

    # verified purchase
    if "verified_purchase" in df.columns:
        df["verified"] = df["verified_purchase"].fillna(False).astype(bool)
    elif "verified" in df.columns:
        df["verified"] = df["verified"].fillna(False).astype(bool)
    else:
        df["verified"] = False

    # helpful votes in 'vote' (sometimes '2/3') → parse, default 0
    if "helpful_vote" in df.columns:
        hv = df["helpful_vote"].fillna(0)
        df["helpful_votes"] = pd.to_numeric(hv, errors="coerce").fillna(0).astype(int)
    elif "vote" in df.columns:
        hv = df["vote"].fillna(0)
        def _parse_vote(v):
            if isinstance(v, (int, float)):
                return int(v)
            s = str(v)
            try:
                if "/" in s:
                    s = s.split("/")[0]
                return int(float(s))
            except Exception:
                return 0
        df["helpful_votes"] = hv.map(_parse_vote)
    else:
        df["helpful_votes"] = 0
    df["review_id"] = df.index.astype(str)
    cols = [
        "review_id",
        "product_id",
        "user_id",
        "rating",
        "title",
        "text",
        "sentiment",
        "timestamp",
        "verified",
        "helpful_votes",
    ]
    return df[cols].copy()


def _ascii_ratio_series(series: pd.Series) -> pd.Series:
    return series.map(_ascii_ratio)


def preprocess_products(meta: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    m = meta.copy()
    if "product_id" not in m.columns:
        if "asin" in m.columns:
            m = m.rename(columns={"asin": "product_id"})
        elif "parent_asin" in m.columns:
            m = m.rename(columns={"parent_asin": "product_id"})
    if "category" not in m.columns and "main_category" in m.columns:
        m["category"] = m["main_category"].map(lambda x: [x] if pd.notna(x) else [])
    if "category_main" not in m.columns and "main_category" in m.columns:
        m["category_main"] = m["main_category"]
    if "image_url" not in m.columns:
        m["image_url"] = ""
    if "description" not in m.columns and "details" in m.columns:
        m["description"] = m["details"].astype(str)
    if "avg_rating" not in m.columns and "average_rating" in m.columns:
        m["avg_rating"] = pd.to_numeric(m["average_rating"], errors="coerce").fillna(0.0)
    if "review_count" not in m.columns and "rating_number" in m.columns:
        m["review_count"] = pd.to_numeric(m["rating_number"], errors="coerce").fillna(0).astype(int)

    # filter: ID, price
    m = m.dropna(subset=["product_id"]).copy()
    if "price" in m.columns:
        m["price"] = pd.to_numeric(m["price"], errors="coerce")
    m = m[m.get("price").notna()]

    def _bucket(p):
        try:
            p = float(p)
        except Exception:
            return "unknown"
        if p < 50000:
            return "budget"
        if p < 200000:
            return "mid"
        return "premium"
    m["price_range"] = m["price"].map(_bucket)

    g = reviews.groupby("product_id")["rating"].agg(["mean", "count"]).reset_index()
    g = g.rename(columns={"mean": "avg_rating_from_reviews", "count": "review_count_from_reviews"})
    prod = m.merge(g, on="product_id", how="left")
    prod["avg_rating"] = prod.get("avg_rating", pd.Series(index=prod.index)).fillna(prod.get("avg_rating_from_reviews"))
    prod["review_count"] = prod.get("review_count", pd.Series(index=prod.index)).fillna(prod.get("review_count_from_reviews")).fillna(0).astype(int)
    prod["avg_rating"] = prod["avg_rating"].fillna(0.0)

    cols = [
        "product_id",
        "title",
        "brand",
        "category",
        "category_main",
        "price",
        "price_range",
        "image_url",
        "description",
        "avg_rating",
        "review_count",
    ]
    for c in cols:
        if c not in prod.columns:
            prod[c] = "" if c in ("title", "brand", "image_url", "description") else 0
    return prod[cols].copy()


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
