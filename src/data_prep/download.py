from __future__ import annotations
"""데이터 다운로드/로드 유틸.

우선순위(아마존 리뷰/메타):
1) 로컬 Parquet 존재 시 사용 (data/raw/*.parquet)
2) 환경변수 URL(AMZ_REVIEWS_URL / AMZ_META_URL) 다운로드 후 사용
3) (가능하면) datasets v2.x 로드 시도 → v3 환경에서는 안내 후 실패
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd


RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _download_file(url: str, dest: Path) -> None:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _scrape_amazon_2023_index_for_electronics(index_url: str):
    """Index 페이지에서 Electronics 리뷰/메타 parquet URL을 추정하여 반환.

    반환: (reviews_url, metadata_url)
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(index_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [a.get("href", "") for a in soup.find_all("a")]

        def pick(cands, key_subs):
            for href in cands:
                if not href:
                    continue
                h = href.lower()
                if all(s in h for s in key_subs) and (h.endswith(".parquet") or ".parquet" in h):
                    if href.startswith("http://") or href.startswith("https://"):
                        return href
                    return index_url.rstrip("/") + "/" + href.lstrip("/")
            return None

        r_url = pick(links, ["electronics", "review"]) or pick(links, ["electronics", "raw_review"])  # type: ignore[arg-type]
        m_url = pick(links, ["electronics", "meta"]) or pick(links, ["electronics", "raw_meta"])      # type: ignore[arg-type]
        return r_url, m_url
    except Exception:
        return None, None


def load_amazon_reviews_electronics(split: str = "full") -> pd.DataFrame:
    local = RAW_DIR / "amazon_reviews_electronics.parquet"
    if local.exists():
        return pd.read_parquet(local)
    env_url = os.getenv("AMZ_REVIEWS_URL")
    if env_url:
        _download_file(env_url, local)
        return pd.read_parquet(local)
    # index 페이지에서 추론 시도
    r_url, _ = _scrape_amazon_2023_index_for_electronics("https://amazon-reviews-2023.github.io/")
    if r_url:
        _download_file(r_url, local)
        return pd.read_parquet(local)
    try:
        from datasets import __version__ as ds_ver
        from packaging.version import Version
        if Version(ds_ver) >= Version("3.0.0"):
            raise RuntimeError(
                "datasets>=3.0 환경에서는 Amazon-Reviews-2023 스크립트 로더가 지원되지 않습니다. "
                "로컬 parquet 또는 AMZ_REVIEWS_URL 환경변수를 사용하세요."
            )
        from datasets import load_dataset
        ds = load_dataset("McAuley-Lab/Amazon-Reviews-2023", "raw_review_Electronics", split=split)
        return ds.to_pandas()
    except Exception as e:
        raise RuntimeError(
            "아마존 리뷰 로드 실패: 로컬 parquet 또는 AMZ_REVIEWS_URL을 설정하세요.\n" + str(e)
        )


def load_amazon_metadata_electronics(split: str = "full") -> pd.DataFrame:
    local = RAW_DIR / "amazon_metadata_electronics.parquet"
    if local.exists():
        return pd.read_parquet(local)
    env_url = os.getenv("AMZ_META_URL")
    if env_url:
        _download_file(env_url, local)
        return pd.read_parquet(local)
    # index 페이지에서 추론 시도
    _, m_url = _scrape_amazon_2023_index_for_electronics("https://amazon-reviews-2023.github.io/")
    if m_url:
        _download_file(m_url, local)
        return pd.read_parquet(local)
    try:
        from datasets import __version__ as ds_ver
        from packaging.version import Version
        if Version(ds_ver) >= Version("3.0.0"):
            raise RuntimeError(
                "datasets>=3.0 환경에서는 해당 데이터셋 로더가 지원되지 않습니다. "
                "로컬 parquet 또는 AMZ_META_URL 환경변수를 사용하세요."
            )
        from datasets import load_dataset
        ds = load_dataset("McAuley-Lab/Amazon-Reviews-2023", "raw_meta_Electronics", split=split)
        return ds.to_pandas()
    except Exception as e:
        raise RuntimeError(
            "아마존 메타데이터 로드 실패: 로컬 parquet 또는 AMZ_META_URL을 설정하세요.\n" + str(e)
        )


def load_bitext_cs(split: Optional[str] = None):
    from datasets import load_dataset

    ds = load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset")
    return ds[split] if split else ds
