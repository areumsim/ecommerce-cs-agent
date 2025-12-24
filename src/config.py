"""통합 설정 로더 모듈.

모든 YAML 설정 파일을 로드하고 관리합니다.
환경변수 오버라이드를 지원합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# 기본 설정 디렉토리
DEFAULT_CONFIG_DIR = Path("configs")


def load_yaml(path: Path | str) -> Dict[str, Any]:
    """YAML 파일 로드."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_env_or_default(key: str, default: Any) -> Any:
    """환경변수 또는 기본값 반환."""
    env_val = os.environ.get(key)
    if env_val is not None:
        # 타입 변환
        if isinstance(default, bool):
            return env_val.lower() in ("true", "1", "yes")
        if isinstance(default, int):
            return int(env_val)
        if isinstance(default, float):
            return float(env_val)
        return env_val
    return default


@dataclass
class AppConfig:
    """앱 전역 설정."""

    name: str = "ecommerce-agent"
    version: str = "1.0.0"
    description: str = "한국어 전자상거래 상담 에이전트"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    ui_port: int = 8000
    log_level: str = "INFO"


@dataclass
class LLMConfig:
    """LLM 설정."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: int = 30
    api_version: str = "2024-01-01"  # Anthropic용


@dataclass
class GuardrailsConfig:
    """가드레일 설정."""

    # 입력 제한
    max_input_length: int = 2000
    min_input_length: int = 1
    # 출력 제한
    max_output_length: int = 4000
    min_output_length: int = 1
    # 톤 검증
    min_polite_ratio: float = 0.5
    polite_endings: List[str] = field(default_factory=lambda: ["니다", "세요", "습니다", "십시오", "시죠", "시요"])
    # 모드
    strict_mode: bool = False
    check_factual: bool = True
    check_tone: bool = True
    # 패턴 (동적 로드)
    pii_patterns: Dict[str, Dict[str, str]] = field(default_factory=dict)
    injection_patterns: List[str] = field(default_factory=list)
    blocked_words: List[str] = field(default_factory=list)
    sensitive_patterns: List[str] = field(default_factory=list)
    inappropriate_patterns: List[str] = field(default_factory=list)


@dataclass
class LLMClassificationConfig:
    """LLM 기반 의도 분류 설정."""

    enabled: bool = True
    fallback_to_keyword: bool = True
    confidence_threshold: str = "medium"
    timeout: int = 10
    max_retries: int = 1


@dataclass
class IntentsConfig:
    """의도 분류 설정."""

    # ORD-xxx 또는 ORD_xxx 형식 모두 지원
    order_id_pattern: str = r"\bORD[-_][A-Za-z0-9_-]+\b"
    ticket_id_pattern: str = r"\bTKT[-_][A-Za-z0-9_-]+\b"
    user_id_pattern: str = r"\buser_[A-Za-z0-9_-]+\b"
    intents: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    fallback_intent: str = "unknown"
    llm_classification: LLMClassificationConfig = field(default_factory=LLMClassificationConfig)


@dataclass
class PathsConfig:
    """경로 설정."""

    # 저장소
    storage_backend: str = "sqlite"
    data_dir: str = "data/mock_csv"
    sqlite_path: str = "data/ecommerce.db"
    # 정책 인덱스
    policies_index: str = "data/processed/policies_index.jsonl"
    policies: str = "data/processed/policies.jsonl"
    # 출력
    outputs_dir: str = "outputs"
    logs_dir: str = "logs"
    # 설정
    llm_config: str = "configs/llm.yaml"
    prompts_dir: str = "configs/prompts"


@dataclass
class EmbeddingConfig:
    """임베딩 모델 설정."""

    model_name: str = "intfloat/multilingual-e5-small"
    batch_size: int = 32
    normalize: bool = True
    device: str = "auto"


@dataclass
class RetrievalConfig:
    """검색 설정."""

    mode: str = "hybrid"  # keyword, embedding, hybrid
    default_top_k: int = 5
    max_top_k: int = 20
    hybrid_alpha: float = 0.7  # 임베딩 가중치
    min_score: float = 0.0
    use_reranking: bool = False


@dataclass
class RAGIndexConfig:
    """인덱스 설정."""

    chunk_size: int = 1000
    chunk_overlap: int = 100
    vector_index_type: str = "flat"
    ivf_nlist: int = 100


@dataclass
class RAGPathsConfig:
    """RAG 경로 설정."""

    policies_source: str = "data/processed/policies.jsonl"
    policies_index: str = "data/processed/policies_index.jsonl"
    vector_index: str = "data/processed/policies_vectors.faiss"
    embeddings_cache: str = "data/processed/policies_embeddings.npy"


@dataclass
class RAGConfig:
    """RAG 통합 설정."""

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    index: RAGIndexConfig = field(default_factory=RAGIndexConfig)
    paths: RAGPathsConfig = field(default_factory=RAGPathsConfig)


class Config:
    """통합 설정 클래스."""

    _instance: Optional["Config"] = None

    def __init__(self, config_dir: Path | str = DEFAULT_CONFIG_DIR):
        self.config_dir = Path(config_dir)
        self._app: Optional[AppConfig] = None
        self._llm: Optional[LLMConfig] = None
        self._guardrails: Optional[GuardrailsConfig] = None
        self._intents: Optional[IntentsConfig] = None
        self._paths: Optional[PathsConfig] = None
        self._rag: Optional[RAGConfig] = None
        self._raw: Dict[str, Dict[str, Any]] = {}
        self._load_all()

    @classmethod
    def get_instance(cls, config_dir: Path | str = DEFAULT_CONFIG_DIR) -> "Config":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """싱글톤 인스턴스 리셋 (테스트용)."""
        cls._instance = None

    def _load_all(self) -> None:
        """모든 설정 파일 로드."""
        self._raw["app"] = load_yaml(self.config_dir / "app.yaml")
        self._raw["llm"] = load_yaml(self.config_dir / "llm.yaml")
        self._raw["guardrails"] = load_yaml(self.config_dir / "guardrails.yaml")
        self._raw["intents"] = load_yaml(self.config_dir / "intents.yaml")
        self._raw["paths"] = load_yaml(self.config_dir / "paths.yaml")
        self._raw["mock"] = load_yaml(self.config_dir / "mock.yaml")
        self._raw["rag"] = load_yaml(self.config_dir / "rag.yaml")
        self._raw["auth"] = load_yaml(self.config_dir / "auth.yaml")

    @property
    def app(self) -> AppConfig:
        """앱 설정."""
        if self._app is None:
            raw = self._raw.get("app", {})
            app_cfg = raw.get("app", {})
            server_cfg = raw.get("server", {})
            logging_cfg = raw.get("logging", {})

            self._app = AppConfig(
                name=app_cfg.get("name", "ecommerce-agent"),
                version=app_cfg.get("version", "1.0.0"),
                description=app_cfg.get("description", ""),
                environment=get_env_or_default("APP_ENV", app_cfg.get("environment", "development")),
                host=get_env_or_default("APP_HOST", server_cfg.get("host", "0.0.0.0")),
                port=get_env_or_default("APP_PORT", server_cfg.get("port", 8000)),
                ui_port=get_env_or_default("UI_PORT", server_cfg.get("ui_port", 8000)),
                log_level=get_env_or_default("LOG_LEVEL", logging_cfg.get("level", "INFO")),
            )
        return self._app

    @property
    def llm(self) -> LLMConfig:
        """LLM 설정."""
        if self._llm is None:
            raw = self._raw.get("llm", {})
            provider = get_env_or_default("LLM_PROVIDER", raw.get("provider", "openai"))
            provider_cfg = raw.get(provider, {})

            # API 키는 환경변수 우선
            api_key_env = f"{provider.upper()}_API_KEY"
            api_key = get_env_or_default(api_key_env, provider_cfg.get("api_key", ""))

            self._llm = LLMConfig(
                provider=provider,
                model=get_env_or_default("LLM_MODEL", provider_cfg.get("model", "gpt-4o-mini")),
                api_key=api_key,
                base_url=provider_cfg.get("base_url"),
                temperature=provider_cfg.get("temperature", 0.7),
                max_tokens=provider_cfg.get("max_tokens", 1024),
                timeout=provider_cfg.get("timeout", 30),
                api_version=provider_cfg.get("api_version", "2024-01-01"),
            )
        return self._llm

    @property
    def guardrails(self) -> GuardrailsConfig:
        """가드레일 설정."""
        if self._guardrails is None:
            raw = self._raw.get("guardrails", {})
            input_cfg = raw.get("input", {})
            output_cfg = raw.get("output", {})
            policy_cfg = raw.get("policy", {})
            tone_cfg = output_cfg.get("tone", {})

            self._guardrails = GuardrailsConfig(
                max_input_length=input_cfg.get("max_length", 2000),
                min_input_length=input_cfg.get("min_length", 1),
                max_output_length=output_cfg.get("max_length", 4000),
                min_output_length=output_cfg.get("min_length", 1),
                min_polite_ratio=tone_cfg.get("min_polite_ratio", 0.5),
                polite_endings=tone_cfg.get("polite_endings", ["니다", "세요", "습니다"]),
                strict_mode=policy_cfg.get("strict_mode", False),
                check_factual=policy_cfg.get("check_factual", True),
                check_tone=policy_cfg.get("check_tone", True),
                pii_patterns=input_cfg.get("pii_patterns", {}),
                injection_patterns=input_cfg.get("injection_patterns", []),
                blocked_words=input_cfg.get("blocked_words", []),
                sensitive_patterns=output_cfg.get("sensitive_patterns", []),
                inappropriate_patterns=output_cfg.get("inappropriate_patterns", []),
            )
        return self._guardrails

    @property
    def intents(self) -> IntentsConfig:
        """의도 분류 설정."""
        if self._intents is None:
            raw = self._raw.get("intents", {})
            patterns = raw.get("patterns", {})
            fallback = raw.get("fallback", {})
            llm_cfg = raw.get("llm_classification", {})

            llm_classification = LLMClassificationConfig(
                enabled=llm_cfg.get("enabled", True),
                fallback_to_keyword=llm_cfg.get("fallback_to_keyword", True),
                confidence_threshold=llm_cfg.get("confidence_threshold", "medium"),
                timeout=llm_cfg.get("timeout", 10),
                max_retries=llm_cfg.get("max_retries", 1),
            )

            self._intents = IntentsConfig(
                order_id_pattern=patterns.get("order_id", r"\bORD[-_][A-Za-z0-9_-]+\b"),
                ticket_id_pattern=patterns.get("ticket_id", r"\bTKT[-_][A-Za-z0-9_-]+\b"),
                user_id_pattern=patterns.get("user_id", r"\buser_[A-Za-z0-9_-]+\b"),
                intents=raw.get("intents", {}),
                fallback_intent=fallback.get("intent", "unknown"),
                llm_classification=llm_classification,
            )
        return self._intents

    @property
    def paths(self) -> PathsConfig:
        """경로 설정."""
        if self._paths is None:
            raw = self._raw.get("paths", {})
            storage = raw.get("storage", {})
            data = raw.get("data", {})
            processed = data.get("processed", {})
            outputs = raw.get("outputs", {})
            configs = raw.get("configs", {})

            # mock.yaml에서도 로드
            mock_raw = self._raw.get("mock", {})

            self._paths = PathsConfig(
                storage_backend=storage.get("backend", mock_raw.get("storage_backend", "sqlite")),
                data_dir=storage.get("data_dir", mock_raw.get("data_dir", "data/mock_csv")),
                sqlite_path=storage.get("sqlite_path", "data/ecommerce.db"),
                policies_index=processed.get("policies_index", "data/processed/policies_index.jsonl"),
                policies=processed.get("policies", "data/processed/policies.jsonl"),
                outputs_dir=outputs.get("models", "outputs"),
                logs_dir=outputs.get("logs", "logs"),
                llm_config=configs.get("llm", "configs/llm.yaml"),
                prompts_dir=configs.get("prompts_dir", "configs/prompts"),
            )
        return self._paths

    @property
    def rag(self) -> RAGConfig:
        """RAG 설정."""
        if self._rag is None:
            raw = self._raw.get("rag", {})
            emb_cfg = raw.get("embedding", {})
            ret_cfg = raw.get("retrieval", {})
            idx_cfg = raw.get("index", {})
            paths_cfg = raw.get("paths", {})

            embedding = EmbeddingConfig(
                model_name=emb_cfg.get("model_name", "intfloat/multilingual-e5-small"),
                batch_size=emb_cfg.get("batch_size", 32),
                normalize=emb_cfg.get("normalize", True),
                device=emb_cfg.get("device", "auto"),
            )

            retrieval = RetrievalConfig(
                mode=ret_cfg.get("mode", "hybrid"),
                default_top_k=ret_cfg.get("default_top_k", 5),
                max_top_k=ret_cfg.get("max_top_k", 20),
                hybrid_alpha=ret_cfg.get("hybrid_alpha", 0.7),
                min_score=ret_cfg.get("min_score", 0.0),
                use_reranking=ret_cfg.get("use_reranking", False),
            )

            index = RAGIndexConfig(
                chunk_size=idx_cfg.get("chunk_size", 1000),
                chunk_overlap=idx_cfg.get("chunk_overlap", 100),
                vector_index_type=idx_cfg.get("vector_index_type", "flat"),
                ivf_nlist=idx_cfg.get("ivf_nlist", 100),
            )

            paths = RAGPathsConfig(
                policies_source=paths_cfg.get("policies_source", "data/processed/policies.jsonl"),
                policies_index=paths_cfg.get("policies_index", "data/processed/policies_index.jsonl"),
                vector_index=paths_cfg.get("vector_index", "data/processed/policies_vectors.faiss"),
                embeddings_cache=paths_cfg.get("embeddings_cache", "data/processed/policies_embeddings.npy"),
            )

            self._rag = RAGConfig(
                embedding=embedding,
                retrieval=retrieval,
                index=index,
                paths=paths,
            )
        return self._rag

    def get_raw(self, section: str) -> Dict[str, Any]:
        """원시 설정 데이터 반환."""
        return self._raw.get(section, {})


# 편의 함수
def get_config(config_dir: Path | str = DEFAULT_CONFIG_DIR) -> Config:
    """설정 인스턴스 반환."""
    return Config.get_instance(config_dir)


# 전역 설정 접근자
config = Config.get_instance()
