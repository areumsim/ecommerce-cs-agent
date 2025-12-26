"""정책 검색 리트리버.

키워드 검색, 임베딩 검색, 하이브리드 검색을 지원합니다.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)

# 리랭커 지연 임포트
_reranker_module = None

_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    """텍스트를 토큰으로 분리."""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


@dataclass
class PolicyHit:
    """검색 결과."""

    id: str
    score: float
    text: str
    metadata: Dict[str, str]


class PolicyRetriever:
    """정책 문서 검색기.

    검색 모드:
    - keyword: 키워드 기반 TF 스코어링
    - embedding: 임베딩 기반 시맨틱 검색
    - hybrid: 키워드 + 임베딩 결합 (기본값)
    """

    def __init__(
        self,
        index_path: Optional[Path] = None,
        vector_path: Optional[Path] = None,
        mode: Optional[str] = None,
    ) -> None:
        """리트리버 초기화.

        Args:
            index_path: 텍스트 인덱스 경로
            vector_path: 벡터 인덱스 경로
            mode: 검색 모드 (keyword, embedding, hybrid)
        """
        cfg = get_config().rag

        self.index_path = Path(index_path) if index_path else Path(cfg.paths.policies_index)
        self.vector_path = Path(vector_path) if vector_path else Path(cfg.paths.vector_index)
        self.mode = mode or cfg.retrieval.mode
        self.hybrid_alpha = cfg.retrieval.hybrid_alpha
        self.min_score = cfg.retrieval.min_score
        self.use_reranking = cfg.retrieval.use_reranking

        # 리랭커 (필요시 로드)
        self._reranker = None

        # 문서 저장소
        self._docs: List[Tuple[str, str, Dict[str, str]]] = []

        # 벡터 검색 관련
        self._faiss_index = None
        self._embedder = None

        # 텍스트 인덱스 로드
        self._load_text_index()

        # 벡터 인덱스 로드 (필요시)
        if self.mode in ("embedding", "hybrid"):
            self._load_vector_index()

    def _load_text_index(self) -> None:
        """텍스트 인덱스 로드."""
        self._docs.clear()
        if not self.index_path.exists():
            logger.warning(f"텍스트 인덱스 없음: {self.index_path}")
            return

        with self.index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                self._docs.append((
                    obj.get("id", ""),
                    obj.get("text", ""),
                    obj.get("metadata", {}),
                ))

        logger.info(f"텍스트 인덱스 로드: {len(self._docs)}개 문서")

    def _load_vector_index(self) -> None:
        """FAISS 벡터 인덱스 로드."""
        if not self.vector_path.exists():
            logger.warning(f"벡터 인덱스 없음: {self.vector_path}")
            # 벡터 없으면 키워드 모드로 폴백
            if self.mode == "embedding":
                logger.warning("임베딩 모드에서 키워드 모드로 폴백")
                self.mode = "keyword"
            elif self.mode == "hybrid":
                logger.warning("하이브리드 모드에서 키워드 모드로 폴백")
                self.mode = "keyword"
            return

        try:
            import faiss
            self._faiss_index = faiss.read_index(str(self.vector_path))
            logger.info(f"FAISS 인덱스 로드: {self._faiss_index.ntotal}개 벡터")
        except ImportError:
            logger.warning("faiss 미설치, 키워드 모드로 폴백")
            self.mode = "keyword"
        except Exception as e:
            logger.error(f"FAISS 인덱스 로드 실패: {e}")
            self.mode = "keyword"

    def _get_embedder(self):
        """임베딩 모델 로드 (지연 로딩)."""
        if self._embedder is None:
            from src.rag.embedder import Embedder
            self._embedder = Embedder()
        return self._embedder

    def _get_reranker(self):
        """리랭커 로드 (지연 로딩)."""
        if self._reranker is None and self.use_reranking:
            try:
                from src.rag.reranker import get_reranker
                self._reranker = get_reranker()
            except ImportError:
                logger.warning("리랭커 모듈 로드 실패")
                self.use_reranking = False
        return self._reranker

    def _keyword_search(self, query: str, top_k: int) -> List[Tuple[float, int]]:
        """키워드 기반 검색.

        Returns:
            (score, index) 튜플 리스트
        """
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []

        scores: List[Tuple[float, int]] = []
        for i, (_id, text, _meta) in enumerate(self._docs):
            t_tokens = _tokenize(text)
            if not t_tokens:
                scores.append((0.0, i))
                continue

            # TF 점수 계산
            t_token_set = set(t_tokens)
            overlap = len(q_tokens & t_token_set)
            if overlap == 0:
                scores.append((0.0, i))
                continue

            # TF with length normalization
            tf = sum(t_tokens.count(qt) for qt in q_tokens)
            score = tf / math.sqrt(len(t_tokens))
            scores.append((score, i))

        # 점수 정규화 (0-1 범위)
        max_score = max(s for s, _ in scores) if scores else 1.0
        if max_score > 0:
            scores = [(s / max_score, i) for s, i in scores]

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]

    def _embedding_search(self, query: str, top_k: int) -> List[Tuple[float, int]]:
        """임베딩 기반 검색.

        Returns:
            (score, index) 튜플 리스트
        """
        if self._faiss_index is None:
            return []

        embedder = self._get_embedder()
        query_embedding = embedder.encode_query(query)
        query_embedding = query_embedding.astype(np.float32).reshape(1, -1)

        # FAISS 검색
        scores, indices = self._faiss_index.search(query_embedding, top_k)

        # (score, index) 튜플로 변환
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:  # -1은 결과 없음
                # 코사인 유사도를 0-1 범위로 정규화
                normalized_score = (score + 1) / 2  # [-1, 1] → [0, 1]
                results.append((float(normalized_score), int(idx)))

        return results

    def _hybrid_search(self, query: str, top_k: int) -> List[Tuple[float, int]]:
        """하이브리드 검색 (키워드 + 임베딩).

        Returns:
            (score, index) 튜플 리스트
        """
        # 양쪽 모두 더 많은 결과를 가져와서 합침
        fetch_k = min(top_k * 3, len(self._docs))

        keyword_results = self._keyword_search(query, fetch_k)
        embedding_results = self._embedding_search(query, fetch_k)

        # 점수 합산 (weighted)
        alpha = self.hybrid_alpha  # 임베딩 가중치
        score_map: Dict[int, float] = {}

        for score, idx in keyword_results:
            score_map[idx] = (1 - alpha) * score

        for score, idx in embedding_results:
            if idx in score_map:
                score_map[idx] += alpha * score
            else:
                score_map[idx] = alpha * score

        # 정렬
        combined = [(score, idx) for idx, score in score_map.items()]
        combined.sort(key=lambda x: x[0], reverse=True)

        return combined[:top_k]

    def search_policy(self, query: str, top_k: int = 5) -> List[PolicyHit]:
        """정책 검색.

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        if not self._docs:
            return []

        cfg = get_config().rag
        top_k = min(top_k, cfg.retrieval.max_top_k)

        # 모드별 검색
        if self.mode == "embedding":
            results = self._embedding_search(query, top_k)
        elif self.mode == "hybrid":
            results = self._hybrid_search(query, top_k)
        else:  # keyword
            results = self._keyword_search(query, top_k)

        # 결과 생성
        hits: List[PolicyHit] = []
        for score, idx in results:
            if score <= self.min_score:
                continue
            if idx >= len(self._docs):
                continue

            doc_id, text, meta = self._docs[idx]
            hits.append(PolicyHit(
                id=doc_id,
                score=score,
                text=text,
                metadata=meta,
            ))

        # 리랭킹 적용 (설정 시)
        if self.use_reranking and hits:
            reranker = self._get_reranker()
            if reranker:
                documents = [
                    (hit.id, hit.text, hit.score, hit.metadata)
                    for hit in hits
                ]
                reranked = reranker.rerank(query, documents, top_k)
                hits = [
                    PolicyHit(
                        id=r.id,
                        score=r.score,
                        text=r.text,
                        metadata=r.metadata,
                    )
                    for r in reranked
                ]
            else:
                # 휴리스틱 리랭커: 쿼리 토큰과 텍스트/타이틀 겹침 점수로 정렬
                q_tokens = set(_tokenize(query))
                def _hscore(h: PolicyHit) -> float:
                    text_tokens = set(_tokenize(h.text))
                    title = (h.metadata or {}).get('title', '')
                    title_tokens = set(_tokenize(title))
                    overlap = len(q_tokens & text_tokens)
                    overlap_title = len(q_tokens & title_tokens)
                    return overlap + (2.0 * overlap_title) + (0.1 * h.score)
                hits = sorted(hits, key=_hscore, reverse=True)[:top_k]


        return hits

    def search(self, query: str, top_k: int = 5) -> List[PolicyHit]:
        """search_policy의 별칭."""
        return self.search_policy(query, top_k)


# 전역 리트리버 인스턴스 (지연 로딩)
_retriever: Optional[PolicyRetriever] = None


def get_retriever() -> PolicyRetriever:
    """전역 리트리버 인스턴스 반환."""
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever()
    return _retriever


def reset_retriever() -> None:
    """전역 리트리버 리셋 (테스트용)."""
    global _retriever
    _retriever = None
