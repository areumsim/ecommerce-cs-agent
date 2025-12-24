from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class PolicyDoc:
    url: str
    title: str
    content: str
    doc_type: str  # refund/shipping/faq/other
    source: Optional[str] = None


class PolicyCrawler:
    """Minimal policy crawler skeleton (HTML→text normalization)."""

    def parse_html(self, url: str, html: str, doc_type: str = "other", title: Optional[str] = None) -> PolicyDoc:
        text = strip_tags(html)
        ttl = title or url
        src = self._domain(url)
        return PolicyDoc(url=url, title=ttl, content=text, doc_type=doc_type, source=src)

    def _domain(self, url: str) -> str:
        m = re.match(r"https?://([^/]+)/?", url)
        return m.group(1) if m else "local"

