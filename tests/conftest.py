"""pytest 설정 및 공통 fixture."""

import pytest
from fastapi.testclient import TestClient

from api import app
from src.config import Config

# pytest-asyncio 모드 설정
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
def reset_config():
    """각 테스트 전/후에 Config 싱글톤 리셋."""
    Config.reset_instance()
    yield
    Config.reset_instance()


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
