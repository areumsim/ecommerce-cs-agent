"""pytest 설정 및 공통 fixture."""

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app
from src.config import Config

pytest_plugins = ["pytest_asyncio"]

PROJECT_ROOT = Path(__file__).parent.parent
SQLITE_DB_PATH = PROJECT_ROOT / "data" / "ecommerce.db"
CSV_DIR = PROJECT_ROOT / "data" / "mock_csv"


def _ensure_sqlite_tables():
    """SQLite 테이블이 존재하는지 확인하고, 없으면 마이그레이션 실행."""
    if not SQLITE_DB_PATH.exists() or SQLITE_DB_PATH.stat().st_size == 0:
        migration_script = PROJECT_ROOT / "scripts" / "05_migrate_to_sqlite.py"
        if migration_script.exists():
            subprocess.run(
                ["python", str(migration_script)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
            )


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """테스트 세션 시작 시 DB 설정 확인."""
    _ensure_sqlite_tables()
    yield


@pytest.fixture(autouse=True)
def reset_config():
    Config.reset_instance()
    yield
    Config.reset_instance()


@pytest.fixture(autouse=True)
def reset_conversation_repo():
    """테스트 간 대화 저장소 싱글톤 초기화."""
    import src.conversation.manager as conv_manager
    conv_manager._conversation_repo = None
    yield
    conv_manager._conversation_repo = None


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user_id():
    """테스트용 사용자 ID."""
    return "user_001"


@pytest.fixture
def sample_policy_query():
    """테스트용 정책 쿼리."""
    return "환불"


@pytest.fixture
def sample_order_payload():
    """테스트용 주문 페이로드."""
    return {
        "user_id": "user_001",
        "order_id": "ORD_20251201_001",
    }


@pytest.fixture
def sample_ticket_payload():
    """테스트용 티켓 생성 페이로드."""
    return {
        "user_id": "user_001",
        "order_id": "ORD_20251201_001",
        "issue_type": "refund",
        "description": "상품 불량으로 환불 요청합니다.",
        "priority": "normal",
    }


@pytest.fixture
def sample_chat_payload():
    """테스트용 채팅 페이로드."""
    return {
        "user_id": "user_001",
        "message": "환불 정책 알려주세요",
    }
