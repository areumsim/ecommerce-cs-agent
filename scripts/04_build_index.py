#!/usr/bin/env python3
"""정책 인덱스 빌드 스크립트.

텍스트 인덱스와 벡터 인덱스를 함께 생성합니다.

사용법:
    python scripts/04_build_index.py [--no-vectors]

옵션:
    --no-vectors: 벡터 인덱스 생성 건너뛰기
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.rag.indexer import PolicyIndexer
from src.config import get_config


def build_text_index() -> int:
    """텍스트 인덱스 빌드."""
    cfg = get_config().rag
    src = Path(cfg.paths.policies_source)
    out = Path(cfg.paths.policies_index)

    if not src.exists():
        print(f"[SKIP] 정책 원본 파일 없음: {src}")
        return 0

    n = PolicyIndexer().build_local_index(
        src_jsonl=src,
        out_jsonl=out,
        chunk_chars=cfg.index.chunk_size,
        overlap=cfg.index.chunk_overlap,
    )
    print(f"[OK] 텍스트 인덱스 생성: {n}개 청크 → {out}")
    return n


def build_vector_index() -> int:
    """벡터 인덱스 빌드."""
    try:
        import faiss
    except ImportError:
        print("[SKIP] faiss 미설치, 벡터 인덱스 건너뛰기")
        return 0

    cfg = get_config().rag
    index_path = Path(cfg.paths.policies_index)
    vector_path = Path(cfg.paths.vector_index)
    embeddings_path = Path(cfg.paths.embeddings_cache)

    if not index_path.exists():
        print(f"[SKIP] 텍스트 인덱스 없음: {index_path}")
        return 0

    # 문서 로드
    documents = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            documents.append(obj.get("text", ""))

    if not documents:
        print("[SKIP] 문서 없음")
        return 0

    print(f"[INFO] {len(documents)}개 문서 임베딩 생성 중...")

    # 임베딩 생성
    from src.rag.embedder import Embedder

    embedder = Embedder()
    embeddings = embedder.encode_documents(documents, show_progress=True)

    # 임베딩 저장
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(embeddings_path), embeddings)
    print(f"[OK] 임베딩 저장: {embeddings.shape} → {embeddings_path}")

    # FAISS 인덱스 생성
    dimension = embeddings.shape[1]
    index_type = cfg.index.vector_index_type

    if index_type == "ivf":
        # IVF 인덱스 (대용량용)
        nlist = cfg.index.ivf_nlist
        quantizer = faiss.IndexFlatIP(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(embeddings.astype(np.float32))
        index.add(embeddings.astype(np.float32))
    else:
        # Flat 인덱스 (소규모용, 정확)
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings.astype(np.float32))

    # 인덱스 저장
    vector_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(vector_path))
    print(f"[OK] FAISS 인덱스 저장: {index.ntotal}개 벡터 → {vector_path}")

    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="정책 인덱스 빌드")
    parser.add_argument(
        "--no-vectors",
        action="store_true",
        help="벡터 인덱스 생성 건너뛰기",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("정책 인덱스 빌드")
    print("=" * 50)

    # 텍스트 인덱스
    n_text = build_text_index()

    # 벡터 인덱스
    if not args.no_vectors and n_text > 0:
        n_vector = build_vector_index()
    else:
        n_vector = 0

    print("=" * 50)
    print(f"완료: 텍스트 {n_text}개, 벡터 {n_vector}개")
    print("=" * 50)


if __name__ == "__main__":
    main()
