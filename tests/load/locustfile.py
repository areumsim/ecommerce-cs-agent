"""부하 테스트 스크립트.

Locust를 사용한 API 부하 테스트.

실행 방법:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

웹 UI:
    http://localhost:8089
"""

from locust import HttpUser, task, between
import json
import random


class EcommerceAgentUser(HttpUser):
    """Ecommerce Agent API 사용자 시뮬레이션."""

    wait_time = between(1, 3)  # 요청 간 1-3초 대기

    def on_start(self):
        """사용자 세션 시작 시 로그인."""
        # 테스트 사용자 생성 (이미 존재하면 로그인만)
        self.email = f"test_user_{random.randint(1000, 9999)}@example.com"
        self.password = "testpassword123"

        # 회원가입 시도
        response = self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "name": "테스트 사용자",
            },
        )

        # 로그인
        response = self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": self.password,
            },
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
        else:
            self.access_token = None
            self.refresh_token = None

    @property
    def auth_headers(self):
        """인증 헤더."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    @task(10)
    def healthz(self):
        """헬스체크 (가장 빈번)."""
        self.client.get("/healthz")

    @task(5)
    def health_detailed(self):
        """상세 헬스체크."""
        self.client.get("/health")

    @task(3)
    def policy_search(self):
        """정책 검색."""
        queries = ["환불", "배송", "교환", "취소", "결제"]
        query = random.choice(queries)
        self.client.get(f"/policies/search?q={query}&top_k=3")

    @task(2)
    def list_orders(self):
        """주문 목록 조회."""
        self.client.get("/users/user_001/orders?limit=5")

    @task(2)
    def list_tickets(self):
        """티켓 목록 조회."""
        self.client.get("/users/user_001/tickets?limit=5")

    @task(1)
    def get_me(self):
        """현재 사용자 정보 조회."""
        if self.access_token:
            self.client.get("/auth/me", headers=self.auth_headers)

    @task(1)
    def create_conversation(self):
        """대화 생성."""
        if self.access_token:
            response = self.client.post(
                "/conversations",
                json={"title": "테스트 대화"},
                headers=self.auth_headers,
            )
            if response.status_code == 201:
                data = response.json()
                self.conversation_id = data.get("id")

    @task(1)
    def list_conversations(self):
        """대화 목록 조회."""
        if self.access_token:
            self.client.get(
                "/conversations?limit=10",
                headers=self.auth_headers,
            )


class PolicySearchUser(HttpUser):
    """정책 검색 집중 테스트 사용자."""

    wait_time = between(0.5, 1.5)

    @task
    def search_policy(self):
        """정책 검색 (빈번한 요청)."""
        queries = [
            "환불 정책",
            "배송비",
            "교환 방법",
            "취소 규정",
            "결제 수단",
            "포인트 사용",
            "회원 등급",
            "적립금",
        ]
        query = random.choice(queries)
        with self.client.get(
            f"/policies/search?q={query}&top_k=5",
            name="/policies/search",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "hits" in data and len(data["hits"]) > 0:
                    response.success()
                else:
                    response.failure("No hits returned")
            else:
                response.failure(f"Status code: {response.status_code}")


class ChatUser(HttpUser):
    """채팅 API 테스트 사용자."""

    wait_time = between(2, 5)

    @task
    def chat(self):
        """채팅 메시지 전송."""
        messages = [
            "주문 상태 확인해주세요",
            "환불 가능한가요?",
            "배송은 언제 되나요?",
            "취소하고 싶어요",
            "교환 방법 알려주세요",
        ]
        message = random.choice(messages)

        with self.client.post(
            "/chat",
            json={
                "user_id": "user_001",
                "message": message,
            },
            name="/chat",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
