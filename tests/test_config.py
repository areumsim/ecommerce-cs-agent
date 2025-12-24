"""설정 로더 테스트."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import (
    Config,
    AppConfig,
    LLMConfig,
    GuardrailsConfig,
    IntentsConfig,
    PathsConfig,
    get_config,
    load_yaml,
)


@pytest.fixture
def temp_config_dir():
    """임시 설정 디렉토리 생성."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # app.yaml
        app_yaml = {
            "app": {
                "name": "test-agent",
                "version": "0.0.1",
                "environment": "test",
            },
            "server": {
                "host": "127.0.0.1",
                "port": 9000,
            },
            "logging": {
                "level": "DEBUG",
            },
        }
        with open(config_dir / "app.yaml", "w") as f:
            yaml.dump(app_yaml, f)

        # llm.yaml
        llm_yaml = {
            "provider": "openai",
            "openai": {
                "api_key": "test-key",
                "model": "gpt-4o",
                "temperature": 0.5,
                "max_tokens": 2048,
                "timeout": 60,
            },
        }
        with open(config_dir / "llm.yaml", "w") as f:
            yaml.dump(llm_yaml, f)

        # guardrails.yaml
        guardrails_yaml = {
            "input": {
                "max_length": 1000,
                "min_length": 5,
                "pii_patterns": {
                    "email": {
                        "pattern": r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
                        "mask": "***@***.***",
                        "description": "이메일",
                    },
                },
                "injection_patterns": [
                    r"jailbreak",
                ],
                "blocked_words": ["test_blocked"],
            },
            "output": {
                "max_length": 2000,
                "min_length": 10,
                "tone": {
                    "polite_endings": ["니다", "요"],
                    "min_polite_ratio": 0.6,
                },
                "sensitive_patterns": [r"/etc/"],
                "inappropriate_patterns": [r"test_inappropriate"],
            },
            "policy": {
                "strict_mode": True,
                "check_factual": False,
                "check_tone": True,
            },
        }
        with open(config_dir / "guardrails.yaml", "w") as f:
            yaml.dump(guardrails_yaml, f)

        # intents.yaml
        intents_yaml = {
            "patterns": {
                "order_id": r"\bORD-\d+\b",
            },
            "intents": {
                "policy": {
                    "keywords": ["정책", "규정"],
                },
                "order": {
                    "keywords": ["주문"],
                    "sub_intents": {
                        "cancel": {"keywords": ["취소"]},
                    },
                },
            },
            "fallback": {
                "intent": "fallback",
            },
        }
        with open(config_dir / "intents.yaml", "w") as f:
            yaml.dump(intents_yaml, f)

        # paths.yaml
        paths_yaml = {
            "storage": {
                "backend": "sqlite",
                "data_dir": "test/data",
            },
            "data": {
                "processed": {
                    "policies_index": "test/policies.jsonl",
                    "policies": "test/policies.jsonl",
                },
            },
        }
        with open(config_dir / "paths.yaml", "w") as f:
            yaml.dump(paths_yaml, f)

        # mock.yaml (호환성)
        mock_yaml = {
            "storage_backend": "csv",
            "data_dir": "mock/data",
        }
        with open(config_dir / "mock.yaml", "w") as f:
            yaml.dump(mock_yaml, f)

        yield config_dir


class TestLoadYaml:
    """load_yaml 함수 테스트."""

    def test_load_existing_file(self, temp_config_dir):
        """존재하는 파일 로드."""
        data = load_yaml(temp_config_dir / "app.yaml")
        assert "app" in data
        assert data["app"]["name"] == "test-agent"

    def test_load_nonexistent_file(self, temp_config_dir):
        """존재하지 않는 파일은 빈 딕셔너리 반환."""
        data = load_yaml(temp_config_dir / "nonexistent.yaml")
        assert data == {}


class TestAppConfig:
    """AppConfig 테스트."""

    def test_load_app_config(self, temp_config_dir):
        """앱 설정 로드."""
        Config.reset_instance()
        cfg = Config(temp_config_dir)
        app = cfg.app

        assert app.name == "test-agent"
        assert app.version == "0.0.1"
        assert app.environment == "test"
        assert app.host == "127.0.0.1"
        assert app.port == 9000
        assert app.log_level == "DEBUG"

    def test_env_override(self, temp_config_dir):
        """환경변수 오버라이드."""
        Config.reset_instance()
        os.environ["APP_ENV"] = "production"
        os.environ["APP_PORT"] = "8080"

        try:
            cfg = Config(temp_config_dir)
            app = cfg.app
            assert app.environment == "production"
            assert app.port == 8080
        finally:
            del os.environ["APP_ENV"]
            del os.environ["APP_PORT"]
            Config.reset_instance()


class TestLLMConfig:
    """LLMConfig 테스트."""

    def test_load_llm_config(self, temp_config_dir):
        """LLM 설정 로드."""
        Config.reset_instance()
        # 환경변수가 있으면 일시적으로 제거
        saved_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            cfg = Config(temp_config_dir)
            llm = cfg.llm

            assert llm.provider == "openai"
            assert llm.model == "gpt-4o"
            assert llm.api_key == "test-key"
            assert llm.temperature == 0.5
            assert llm.max_tokens == 2048
            assert llm.timeout == 60
        finally:
            if saved_key:
                os.environ["OPENAI_API_KEY"] = saved_key
            Config.reset_instance()

    def test_env_api_key_override(self, temp_config_dir):
        """API 키 환경변수 오버라이드."""
        Config.reset_instance()
        os.environ["OPENAI_API_KEY"] = "env-api-key"

        try:
            cfg = Config(temp_config_dir)
            llm = cfg.llm
            assert llm.api_key == "env-api-key"
        finally:
            del os.environ["OPENAI_API_KEY"]
            Config.reset_instance()


class TestGuardrailsConfig:
    """GuardrailsConfig 테스트."""

    def test_load_guardrails_config(self, temp_config_dir):
        """가드레일 설정 로드."""
        Config.reset_instance()
        cfg = Config(temp_config_dir)
        gr = cfg.guardrails

        assert gr.max_input_length == 1000
        assert gr.min_input_length == 5
        assert gr.max_output_length == 2000
        assert gr.min_output_length == 10
        assert gr.min_polite_ratio == 0.6
        assert gr.strict_mode is True
        assert gr.check_factual is False
        assert gr.check_tone is True

        # 패턴 로드
        assert "email" in gr.pii_patterns
        assert "jailbreak" in gr.injection_patterns
        assert "test_blocked" in gr.blocked_words


class TestIntentsConfig:
    """IntentsConfig 테스트."""

    def test_load_intents_config(self, temp_config_dir):
        """의도 분류 설정 로드."""
        Config.reset_instance()
        cfg = Config(temp_config_dir)
        intents = cfg.intents

        assert intents.order_id_pattern == r"\bORD-\d+\b"
        assert intents.fallback_intent == "fallback"
        assert "policy" in intents.intents
        assert "order" in intents.intents


class TestPathsConfig:
    """PathsConfig 테스트."""

    def test_load_paths_config(self, temp_config_dir):
        """경로 설정 로드."""
        Config.reset_instance()
        cfg = Config(temp_config_dir)
        paths = cfg.paths

        assert paths.storage_backend == "sqlite"
        assert paths.data_dir == "test/data"
        assert paths.policies_index == "test/policies.jsonl"


class TestSingleton:
    """싱글톤 패턴 테스트."""

    def test_singleton_instance(self, temp_config_dir):
        """싱글톤 인스턴스 테스트."""
        Config.reset_instance()
        cfg1 = Config.get_instance(temp_config_dir)
        cfg2 = Config.get_instance(temp_config_dir)
        assert cfg1 is cfg2

    def test_reset_instance(self, temp_config_dir):
        """인스턴스 리셋 테스트."""
        Config.reset_instance()
        cfg1 = Config.get_instance(temp_config_dir)
        Config.reset_instance()
        cfg2 = Config.get_instance(temp_config_dir)
        assert cfg1 is not cfg2
