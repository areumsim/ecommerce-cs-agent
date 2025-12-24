#!/usr/bin/env python3
from __future__ import annotations

"""Crawl or parse policy pages into data/processed/policies.jsonl.

Networking is optional; if POLICY_LOCAL_HTML is set (comma-separated paths),
the script will parse local HTML files. Otherwise, it writes a placeholder.
"""

import json
import os
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from typing import List

from src.data_prep.crawler import PolicyCrawler


def load_local_html(paths: List[str]) -> List[tuple[str, str]]:
    pairs = []
    for p in paths:
        pth = Path(p).expanduser()
        if pth.exists():
            pairs.append((pth.as_posix(), pth.read_text(encoding="utf-8", errors="ignore")))
    return pairs


def main() -> None:
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "policies.jsonl"

    local = os.getenv("POLICY_LOCAL_HTML", "").strip()
    items: List[dict] = []

    crawler = PolicyCrawler()

    if local:
        for url, html in load_local_html([s for s in local.split(",") if s.strip()]):
            doc = crawler.parse_html(url=url, html=html, doc_type="policy")
            items.append(doc.__dict__)
    else:
        example_html = """<h1>Refund Policy</h1><p>You can request a refund within 7 days.</p>"""
        doc = crawler.parse_html(url="https://example.com/refund", html=example_html, doc_type="refund", title="Refund Policy")
        items.append(doc.__dict__)

    with out_path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"Wrote {len(items)} policy docs → {out_path}")


if __name__ == "__main__":
    main()
