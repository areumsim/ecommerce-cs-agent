"""RAG 시스템 테스트."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from src.rag.retriever import (
    PolicyRetriever,
    PolicyHit,
    _tokenize,
    get_retriever,
    reset_retriever,
)
from src.rag.embedder import Embedder, compute_similarity


class TestTokenize:
    """토큰화 테스트."""

    def test_basic_tokenize(self):
        tokens = _tokenize("환불 정책 알려주세요")
        assert "환불" in tokens
        assert "정책" in tokens
        assert "알려주세요" in tokens

    def test_lowercase(self):
        tokens = _tokenize("HELLO World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_none_input(self):
        assert _tokenize(None) == []

    def test_unicode(self):
        tokens = _tokenize("배송비 3,000원")
        assert "배송비" in tokens
        assert "3" in tokens
        assert "000원" in tokens


class TestPolicyHit:
    """PolicyHit 데이터클래스 테스트."""

    def test_create_hit(self):
        hit = PolicyHit(
            id="test-001",
            score=0.85,
            text="환불 정책 내용",
            metadata={"title": "환불 정책", "doc_type": "refund"},
        )
        assert hit.id == "test-001"
        assert hit.score == 0.85
        assert hit.text == "환불 정책 내용"
        assert hit.metadata["doc_type"] == "refund"


class TestPolicyRetrieverKeyword:
    """키워드 검색 테스트."""

    @pytest.fixture
    def temp_index(self, tmp_path):
        """임시 인덱스 생성."""
        index_path = tmp_path / "policies_index.jsonl"
        docs = [
            {"id": "1", "text": "환불 정책: 7일 이내 환불 가능", "metadata": {"doc_type": "refund"}},
            {"id": "2", "text": "배송 정책: 2-3 영업일 소요", "metadata": {"doc_type": "shipping"}},
            {"id": "3", "text": "교환 정책: 불량품은 무료 교환", "metadata": {"doc_type": "exchange"}},
        ]
        with index_path.open("w") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        return index_path

    def test_keyword_search_basic(self, temp_index):
        """기본 키워드 검색."""
        retriever = PolicyRetriever(index_path=temp_index, mode="keyword")
        hits = retriever.search_policy("환불", top_k=5)
        assert len(hits) > 0
        assert "환불" in hits[0].text

    def test_keyword_search_multiple_terms(self, temp_index):
        """여러 키워드 검색."""
        retriever = PolicyRetriever(index_path=temp_index, mode="keyword")
        hits = retriever.search_policy("배송 영업일", top_k=5)
        assert len(hits) > 0
        # 배송 정책이 1위여야 함
        assert "배송" in hits[0].text

    def test_keyword_search_no_results(self, temp_index):
        """결과 없는 검색."""
        retriever = PolicyRetriever(index_path=temp_index, mode="keyword")
        hits = retriever.search_policy("없는키워드xyz", top_k=5)
        # 점수가 0인 결과는 제외됨
        assert len(hits) == 0

    def test_keyword_search_top_k(self, temp_index):
        """top_k 제한."""
        retriever = PolicyRetriever(index_path=temp_index, mode="keyword")
        hits = retriever.search_policy("정책", top_k=2)
        assert len(hits) <= 2


class TestPolicyRetrieverEmbedding:
    """임베딩 검색 테스트."""

    @pytest.fixture
    def temp_index_with_vectors(self, tmp_path):
        """임시 인덱스 + 벡터 생성."""
        import faiss

        index_path = tmp_path / "policies_index.jsonl"
        vector_path = tmp_path / "policies_vectors.faiss"

        docs = [
            {"id": "1", "text": "환불 정책: 상품 수령 후 7일 이내 환불 가능합니다.", "metadata": {"doc_type": "refund"}},
            {"id": "2", "text": "배송 정책: 결제 완료 후 2-3 영업일 소요됩니다.", "metadata": {"doc_type": "shipping"}},
            {"id": "3", "text": "교환 정책: 불량품은 무료로 교환 가능합니다.", "metadata": {"doc_type": "exchange"}},
        ]
        with index_path.open("w") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        # 임베딩 생성
        embedder = Embedder()
        texts = [doc["text"] for doc in docs]
        embeddings = embedder.encode_documents(texts, show_progress=False)

        # FAISS 인덱스 생성
        dimension = embeddings.shape[1]
        faiss_index = faiss.IndexFlatIP(dimension)
        faiss_index.add(embeddings.astype(np.float32))
        faiss.write_index(faiss_index, str(vector_path))

        return index_path, vector_path

    def test_embedding_search_basic(self, temp_index_with_vectors):
        """기본 임베딩 검색."""
        index_path, vector_path = temp_index_with_vectors
        retriever = PolicyRetriever(
            index_path=index_path,
            vector_path=vector_path,
            mode="embedding",
        )
        hits = retriever.search_policy("반품하고 싶어요", top_k=3)
        assert len(hits) > 0
        # 의미상 환불 정책과 가장 유사해야 함
        assert any("환불" in hit.text for hit in hits[:2])

    def test_embedding_search_semantic(self, temp_index_with_vectors):
        """시맨틱 검색 (동의어)."""
        index_path, vector_path = temp_index_with_vectors
        retriever = PolicyRetriever(
            index_path=index_path,
            vector_path=vector_path,
            mode="embedding",
        )
        # "택배"는 문서에 없지만 "배송"과 의미적으로 유사
        hits = retriever.search_policy("택배 언제 도착해요?", top_k=3)
        assert len(hits) > 0
        # 배송 정책이 상위에 있어야 함
        top_texts = [hit.text for hit in hits[:2]]
        assert any("배송" in text for text in top_texts)


class TestPolicyRetrieverHybrid:
    """하이브리드 검색 테스트."""

    @pytest.fixture
    def temp_index_with_vectors(self, tmp_path):
        """임시 인덱스 + 벡터 생성."""
        import faiss

        index_path = tmp_path / "policies_index.jsonl"
        vector_path = tmp_path / "policies_vectors.faiss"

        docs = [
            {"id": "1", "text": "환불 정책: 상품 수령 후 7일 이내 환불 가능합니다.", "metadata": {"doc_type": "refund"}},
            {"id": "2", "text": "배송 정책: 결제 완료 후 2-3 영업일 소요됩니다.", "metadata": {"doc_type": "shipping"}},
            {"id": "3", "text": "교환 정책: 불량품은 무료로 교환 가능합니다.", "metadata": {"doc_type": "exchange"}},
        ]
        with index_path.open("w") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        # 임베딩 생성
        embedder = Embedder()
        texts = [doc["text"] for doc in docs]
        embeddings = embedder.encode_documents(texts, show_progress=False)

        # FAISS 인덱스 생성
        dimension = embeddings.shape[1]
        faiss_index = faiss.IndexFlatIP(dimension)
        faiss_index.add(embeddings.astype(np.float32))
        faiss.write_index(faiss_index, str(vector_path))

        return index_path, vector_path

    def test_hybrid_search(self, temp_index_with_vectors):
        """하이브리드 검색."""
        index_path, vector_path = temp_index_with_vectors
        retriever = PolicyRetriever(
            index_path=index_path,
            vector_path=vector_path,
            mode="hybrid",
        )
        hits = retriever.search_policy("환불 정책 알려주세요", top_k=3)
        assert len(hits) > 0
        # 환불 정책이 1위여야 함 (키워드 + 의미 모두 일치)
        assert "환불" in hits[0].text


class TestEmbedder:
    """임베딩 생성기 테스트."""

    def test_encode_single(self):
        """단일 텍스트 임베딩."""
        embedder = Embedder()
        embedding = embedder.encode("환불 정책")
        assert isinstance(embedding, np.ndarray)
        assert embedding.ndim == 1
        assert embedding.shape[0] > 0

    def test_encode_batch(self):
        """배치 임베딩."""
        embedder = Embedder()
        texts = ["환불 정책", "배송 정책", "교환 정책"]
        embeddings = embedder.encode(texts)
        assert embeddings.shape[0] == 3
        assert embeddings.ndim == 2

    def test_encode_query(self):
        """쿼리 임베딩 (E5 프리픽스)."""
        embedder = Embedder()
        embedding = embedder.encode_query("환불 어떻게 해요?")
        assert isinstance(embedding, np.ndarray)
        assert embedding.ndim == 1

    def test_encode_documents(self):
        """문서 임베딩 (E5 프리픽스)."""
        embedder = Embedder()
        docs = ["환불 정책 내용", "배송 정책 내용"]
        embeddings = embedder.encode_documents(docs, show_progress=False)
        assert embeddings.shape[0] == 2

    def test_dimension(self):
        """임베딩 차원 확인."""
        embedder = Embedder()
        # multilingual-e5-small은 384 차원
        assert embedder.dimension == 384


class TestComputeSimilarity:
    """유사도 계산 테스트."""

    def test_identical_vectors(self):
        """동일 벡터 유사도."""
        vec = np.array([1.0, 0.0, 0.0])
        vec_norm = vec / np.linalg.norm(vec)
        scores = compute_similarity(vec_norm, vec_norm.reshape(1, -1))
        assert scores[0] == pytest.approx(1.0, abs=0.01)

    def test_orthogonal_vectors(self):
        """직교 벡터 유사도."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        scores = compute_similarity(vec1, vec2.reshape(1, -1))
        assert scores[0] == pytest.approx(0.0, abs=0.01)

    def test_batch_similarity(self):
        """배치 유사도 계산."""
        query = np.array([1.0, 0.0, 0.0])
        docs = np.array([
            [1.0, 0.0, 0.0],  # 동일
            [0.0, 1.0, 0.0],  # 직교
            [0.5, 0.5, 0.0],  # 부분 유사
        ])
        # 정규화
        query = query / np.linalg.norm(query)
        docs = docs / np.linalg.norm(docs, axis=1, keepdims=True)

        scores = compute_similarity(query, docs)
        assert len(scores) == 3
        assert scores[0] > scores[2] > scores[1]


class TestRetrieverIntegration:
    """리트리버 통합 테스트."""

    def test_real_index_keyword_mode(self):
        """실제 인덱스로 키워드 검색."""
        reset_retriever()
        retriever = PolicyRetriever(mode="keyword")
        hits = retriever.search_policy("환불", top_k=3)
        assert len(hits) > 0
        assert any("환불" in hit.text for hit in hits)

    def test_real_index_hybrid_mode(self):
        """실제 인덱스로 하이브리드 검색."""
        reset_retriever()
        retriever = PolicyRetriever(mode="hybrid")
        hits = retriever.search_policy("반품하고 싶어요", top_k=3)
        assert len(hits) > 0

    def test_search_alias(self):
        """search() 별칭 메서드."""
        reset_retriever()
        retriever = PolicyRetriever(mode="keyword")
        hits = retriever.search("배송", top_k=2)
        assert len(hits) > 0

    def test_get_retriever_singleton(self):
        """싱글톤 패턴."""
        reset_retriever()
        r1 = get_retriever()
        r2 = get_retriever()
        assert r1 is r2
