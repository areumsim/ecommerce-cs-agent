"""API 엔드포인트 테스트."""

import pytest


class TestHealthEndpoint:
    """헬스체크 엔드포인트 테스트."""

    def test_healthz_returns_200(self, client):
        """GET /healthz가 200을 반환하는지 확인."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestPolicyEndpoints:
    """정책 검색 엔드포인트 테스트."""

    def test_policy_search_returns_results(self, client, sample_policy_query):
        """GET /policies/search가 결과를 반환하는지 확인."""
        response = client.get(
            "/policies/search",
            params={"q": sample_policy_query, "top_k": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data
        assert isinstance(data["hits"], list)

    def test_policy_search_with_korean_query(self, client):
        """한국어 쿼리로 정책 검색이 동작하는지 확인."""
        response = client.get(
            "/policies/search",
            params={"q": "배송", "top_k": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data

    def test_policy_search_empty_query(self, client):
        """빈 쿼리 처리 확인."""
        response = client.get(
            "/policies/search",
            params={"q": "", "top_k": 5}
        )
        # 빈 쿼리도 처리되어야 함
        assert response.status_code in [200, 422]


class TestOrderEndpoints:
    """주문 관련 엔드포인트 테스트."""

    def test_get_user_orders(self, client, test_user_id):
        """GET /users/{user_id}/orders가 동작하는지 확인."""
        response = client.get(f"/users/{test_user_id}/orders")
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)

    def test_get_user_orders_with_status_filter(self, client, test_user_id):
        """상태 필터가 적용되는지 확인."""
        response = client.get(
            f"/users/{test_user_id}/orders",
            params={"status": "pending"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data

    def test_get_user_orders_with_limit(self, client, test_user_id):
        """limit 파라미터가 적용되는지 확인."""
        response = client.get(
            f"/users/{test_user_id}/orders",
            params={"limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("orders", [])) <= 5

    def test_get_nonexistent_user_orders(self, client):
        """존재하지 않는 사용자의 주문 조회."""
        response = client.get("/users/nonexistent_user/orders")
        assert response.status_code == 200
        data = response.json()
        assert data.get("orders", []) == []


class TestTicketEndpoints:
    """티켓 관련 엔드포인트 테스트."""

    def test_create_ticket(self, client, sample_ticket_payload):
        """POST /tickets로 티켓 생성 확인."""
        response = client.post("/tickets", json=sample_ticket_payload)
        # 생성 성공 또는 이미 존재하는 경우
        assert response.status_code in [200, 201, 400]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "ticket_id" in data or "ticket" in data

    def test_create_ticket_missing_fields(self, client):
        """필수 필드 누락 시 에러 확인."""
        incomplete_payload = {
            "user_id": "user_001",
            # issue_type, description 누락
        }
        response = client.post("/tickets", json=incomplete_payload)
        assert response.status_code == 422  # Validation error

    def test_get_user_tickets(self, client, test_user_id):
        """GET /users/{user_id}/tickets가 동작하는지 확인."""
        response = client.get(f"/users/{test_user_id}/tickets")
        assert response.status_code == 200
        data = response.json()
        assert "tickets" in data
        assert isinstance(data["tickets"], list)


class TestChatEndpoint:
    """채팅 엔드포인트 테스트."""

    def test_chat_basic(self, client, sample_chat_payload):
        """POST /chat 기본 동작 확인."""
        response = client.post("/chat", json=sample_chat_payload)
        assert response.status_code == 200
        data = response.json()
        # LLM 있으면 response/final_response, 없으면 hits (fallback)
        assert "response" in data or "final_response" in data or "hits" in data

    def test_chat_policy_query(self, client):
        """정책 관련 채팅 쿼리 처리 확인."""
        payload = {
            "user_id": "test_user",
            "message": "배송은 얼마나 걸려요?",
        }
        response = client.post("/chat", json=payload)
        assert response.status_code == 200

    def test_chat_order_query(self, client):
        """주문 관련 채팅 쿼리 처리 확인."""
        payload = {
            "user_id": "user_001",
            "message": "내 주문 목록 보여줘",
        }
        response = client.post("/chat", json=payload)
        assert response.status_code == 200

    def test_chat_empty_message(self, client):
        """빈 메시지 처리 확인."""
        payload = {
            "user_id": "test_user",
            "message": "",
        }
        response = client.post("/chat", json=payload)
        # 빈 메시지도 처리되거나 에러 반환
        assert response.status_code in [200, 400, 422]
