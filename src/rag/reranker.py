"""리랭커 모듈.

검색 결과를 재순위화하여 정확도를 향상시킵니다.
Cross-Encoder 기반 리랭킹을 지원합니다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class RerankedResult:
    """리랭킹 결과."""

    id: str
    score: float
    original_score: float
    text: str
    metadata: dict


class Reranker:
    """Cross-Encoder 기반 리랭커.

    검색 결과를 쿼리와 함께 Cross-Encoder에 통과시켜
    더 정확한 관련성 점수를 계산합니다.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        """리랭커 초기화.

        Args:
            model_name: Cross-Encoder 모델 이름
            device: 사용할 디바이스 (auto, cpu, cuda)
        """
        cfg = get_config().rag
        self.model_name = model_name or getattr(
            cfg.retrieval, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.device = device or cfg.embedding.device
        self._model = None

    def _load_model(self):
        """모델 지연 로딩."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder

            # 디바이스 결정
            if self.device == "auto":
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            self._model = CrossEncoder(self.model_name, device=device)
            logger.info(f"리랭커 로드: {self.model_name} on {device}")
            return self._model

        except ImportError:
            logger.warning("sentence-transformers 미설치, 리랭킹 비활성화")
            return None
        except Exception as e:
            logger.error(f"리랭커 로드 실패: {e}")
            return None

    def rerank(
        self,
        query: str,
        documents: List[Tuple[str, str, float, dict]],
        top_k: Optional[int] = None,
    ) -> List[RerankedResult]:
        """검색 결과 리랭킹.

        Args:
            query: 검색 쿼리
            documents: (id, text, score, metadata) 튜플 리스트
            top_k: 반환할 최대 결과 수

        Returns:
            리랭킹된 결과 리스트
        """
        if not documents:
            return []

        model = self._load_model()
        if model is None:
            # 모델 로드 실패 시 원본 순서 유지
            return [
                RerankedResult(
                    id=doc_id,
                    score=score,
                    original_score=score,
                    text=text,
                    metadata=meta,
                )
                for doc_id, text, score, meta in documents[:top_k]
            ]

        # Cross-Encoder 입력 생성
        pairs = [(query, text) for _, text, _, _ in documents]

        # 점수 계산
        try:
            scores = model.predict(pairs)
            if isinstance(scores, np.ndarray):
                scores = scores.tolist()
        except Exception as e:
            logger.error(f"리랭킹 실패: {e}")
            return [
                RerankedResult(
                    id=doc_id,
                    score=score,
                    original_score=score,
                    text=text,
                    metadata=meta,
                )
                for doc_id, text, score, meta in documents[:top_k]
            ]

        # 결과 생성 및 정렬
        results = []
        for (doc_id, text, orig_score, meta), new_score in zip(documents, scores):
            results.append(
                RerankedResult(
                    id=doc_id,
                    score=float(new_score),
                    original_score=orig_score,
                    text=text,
                    metadata=meta,
                )
            )

        # 점수 기준 정렬
        results.sort(key=lambda x: x.score, reverse=True)

        if top_k:
            results = results[:top_k]

        return results


# 전역 리랭커 인스턴스
_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """전역 리랭커 인스턴스 반환."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def reset_reranker() -> None:
    """전역 리랭커 리셋 (테스트용)."""
    global _reranker
    _reranker = None
