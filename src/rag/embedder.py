"""임베딩 생성기 모듈.

다국어 임베딩 모델을 사용하여 텍스트를 벡터로 변환합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)


class Embedder:
    """텍스트 임베딩 생성기.

    sentence-transformers를 사용하여 텍스트를 벡터로 변환합니다.
    """

    _instance: Optional["Embedder"] = None

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        normalize: bool = True,
    ):
        """임베딩 모델 초기화.

        Args:
            model_name: 모델 이름 (기본값: config에서 로드)
            device: 디바이스 (auto, cpu, cuda)
            normalize: 벡터 정규화 여부
        """
        cfg = get_config().rag.embedding

        self.model_name = model_name or cfg.model_name
        self.device = device or cfg.device
        self.normalize = normalize if normalize is not None else cfg.normalize
        self.batch_size = cfg.batch_size

        self._model = None
        self._dimension: Optional[int] = None

    @classmethod
    def get_instance(cls) -> "Embedder":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋 (테스트용)."""
        cls._instance = None

    def _load_model(self) -> None:
        """모델 로드 (지연 로딩)."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            # 디바이스 설정
            device = self.device
            if device == "auto":
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"임베딩 모델 로드: {self.model_name} (device={device})")
            self._model = SentenceTransformer(self.model_name, device=device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"임베딩 차원: {self._dimension}")

        except ImportError:
            raise ImportError(
                "sentence-transformers가 설치되지 않았습니다. "
                "pip install sentence-transformers 를 실행하세요."
            )

    @property
    def dimension(self) -> int:
        """임베딩 차원."""
        self._load_model()
        return self._dimension

    def encode(
        self,
        texts: Union[str, List[str]],
        show_progress: bool = False,
    ) -> np.ndarray:
        """텍스트를 임베딩 벡터로 변환.

        Args:
            texts: 단일 텍스트 또는 텍스트 리스트
            show_progress: 진행 표시줄 표시 여부

        Returns:
            임베딩 벡터 (N, D) 또는 (D,) for single text
        """
        self._load_model()

        if isinstance(texts, str):
            texts = [texts]
            single = True
        else:
            single = False

        # E5 모델의 경우 쿼리/문서 프리픽스 추가
        if "e5" in self.model_name.lower():
            # 기본적으로 passage로 처리 (인덱싱 시)
            texts = [f"passage: {t}" for t in texts]

        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize,
        )

        if single:
            return embeddings[0]
        return embeddings

    def encode_query(self, query: str) -> np.ndarray:
        """쿼리 텍스트를 임베딩.

        E5 모델의 경우 query: 프리픽스를 추가합니다.

        Args:
            query: 검색 쿼리

        Returns:
            쿼리 임베딩 벡터
        """
        self._load_model()

        # E5 모델의 경우 쿼리 프리픽스 추가
        if "e5" in self.model_name.lower():
            query = f"query: {query}"

        embedding = self._model.encode(
            query,
            normalize_embeddings=self.normalize,
        )

        return embedding

    def encode_documents(
        self,
        documents: List[str],
        show_progress: bool = True,
    ) -> np.ndarray:
        """문서 리스트를 임베딩.

        E5 모델의 경우 passage: 프리픽스를 추가합니다.

        Args:
            documents: 문서 텍스트 리스트
            show_progress: 진행 표시줄 표시 여부

        Returns:
            문서 임베딩 행렬 (N, D)
        """
        self._load_model()

        # E5 모델의 경우 문서 프리픽스 추가
        if "e5" in self.model_name.lower():
            documents = [f"passage: {doc}" for doc in documents]

        embeddings = self._model.encode(
            documents,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize,
        )

        return embeddings


def get_embedder() -> Embedder:
    """임베딩 인스턴스 반환."""
    return Embedder.get_instance()


def compute_similarity(
    query_embedding: np.ndarray,
    document_embeddings: np.ndarray,
) -> np.ndarray:
    """코사인 유사도 계산.

    Args:
        query_embedding: 쿼리 임베딩 (D,)
        document_embeddings: 문서 임베딩 행렬 (N, D)

    Returns:
        유사도 점수 (N,)
    """
    # 정규화된 벡터라면 내적 = 코사인 유사도
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)

    scores = np.dot(document_embeddings, query_embedding.T).flatten()
    return scores
