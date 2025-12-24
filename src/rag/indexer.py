from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


def _hash_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _chunks(text: str, chunk_chars: int = 1000, overlap: int = 100) -> Iterable[str]:
    if chunk_chars <= 0:
        yield text
        return
    i = 0
    n = len(text)
    step = max(1, chunk_chars - overlap)
    while i < n:
        yield text[i : i + chunk_chars]
        i += step


@dataclass
class PolicyRecord:
    id: str
    text: str
    metadata: Dict[str, str]


class PolicyIndexer:
    """Local policy index builder (prepares JSONL for later vectorization)."""

    def build_local_index(self, src_jsonl: Path, out_jsonl: Path, chunk_chars: int = 1000, overlap: int = 100) -> int:
        import json

        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with src_jsonl.open("r", encoding="utf-8") as fin, out_jsonl.open("w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                base_meta = {
                    "url": rec.get("url", ""),
                    "title": rec.get("title", ""),
                    "doc_type": rec.get("doc_type", ""),
                    "source": rec.get("source", ""),
                }
                content = rec.get("content", "")
                for part in _chunks(content, chunk_chars=chunk_chars, overlap=overlap):
                    pid = _hash_id(rec.get("url", "") + part[:50])
                    out = {
                        "id": pid,
                        "text": part,
                        "metadata": base_meta,
                    }
                    fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                    count += 1
        return count

