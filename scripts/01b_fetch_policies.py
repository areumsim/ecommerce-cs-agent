#!/usr/bin/env python3
from __future__ import annotations

"""Fetch policy pages from seed URLs and save raw HTML under data/raw/crawled.

주의: 네트워크가 허용된 환경에서만 실행하십시오. robots.txt/도메인 화이트리스트를 준수하세요.
"""

import asyncio
import json
import re
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from typing import List

import aiohttp
import yaml


RAW_DIR = Path("data/raw/crawled")
CONF = Path("configs/crawl.yaml")


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)/?", url)
    return m.group(1) if m else "unknown"


async def fetch_one(session: aiohttp.ClientSession, url: str, timeout: int) -> tuple[str, str]:
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        html = await resp.text()
        return url, html


async def main() -> None:
    if not CONF.exists():
        raise SystemExit(f"config not found: {CONF}")
    cfg = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    ua = cfg.get("user_agent", "EcommerceAgentBot/0.1")
    timeout = int(cfg.get("timeout_sec", 10))
    whitelist = set(cfg.get("whitelist_domains", []) or [])
    urls: List[str] = list(cfg.get("seed_urls", []) or [])

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession(headers={"User-Agent": ua}) as session:
        for url in urls:
            dom = domain_of(url)
            if whitelist and dom not in whitelist:
                print(f"skip (not whitelisted): {url}")
                continue
            try:
                u, html = await fetch_one(session, url, timeout)
            except Exception as e:
                print(f"error: {url} -> {e}")
                continue
            out_dir = RAW_DIR / dom
            out_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^A-Za-z0-9_-]+", "_", url)
            (out_dir / f"{slug}.html").write_text(html, encoding="utf-8")
            meta = {"url": url, "domain": dom}
            (out_dir / f"{slug}.meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            print(f"saved: {url} → {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
