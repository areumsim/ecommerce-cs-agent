"""대화 히스토리 모듈 테스트."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.conversation.models import (
    Conversation, Message, MessageCreate, ConversationCreate, ConversationResponse
)
from src.conversation.repository import ConversationRepository
from src.conversation.manager import ConversationManager


class TestMessageModel:
    """메시지 모델 테스트."""

    def test_message_creation(self):
        """메시지 생성."""
        msg = Message(
            id="msg_123",
            conversation_id="conv_456",
            role="user",
            content="안녕하세요"
        )

        assert msg.id == "msg_123"
        assert msg.conversation_id == "conv_456"
        assert msg.role == "user"
        assert msg.content == "안녕하세요"

    def test_message_with_intent(self):
        """의도가 있는 메시지."""
        msg = Message(
            id="msg_123",
            conversation_id="conv_456",
            role="assistant",
            content="주문을 취소해 드리겠습니다.",
            intent="order_cancel"
        )

        assert msg.intent == "order_cancel"

    def test_message_to_llm_format(self):
        """LLM 형식 변환."""
        msg = Message(
            id="msg_123",
            conversation_id="conv_456",
            role="user",
            content="배송 상태 확인해주세요"
        )

        llm_format = msg.to_llm_format()

        assert llm_format == {"role": "user", "content": "배송 상태 확인해주세요"}


class TestConversationModel:
    """대화 모델 테스트."""

    def test_conversation_creation(self):
        """대화 생성."""
        conv = Conversation(
            id="conv_123",
            user_id="user_456"
        )

        assert conv.id == "conv_123"
        assert conv.user_id == "user_456"
        assert conv.status == "active"
        assert conv.messages == []

    def test_conversation_with_messages(self):
        """메시지가 있는 대화."""
        msg1 = Message(
            id="msg_1", conversation_id="conv_123",
            role="user", content="안녕"
        )
        msg2 = Message(
            id="msg_2", conversation_id="conv_123",
            role="assistant", content="안녕하세요!"
        )

        conv = Conversation(
            id="conv_123",
            user_id="user_456",
            messages=[msg1, msg2]
        )

        assert len(conv.messages) == 2
        assert conv.messages[0].role == "user"
        assert conv.messages[1].role == "assistant"

    def test_get_history_for_llm(self):
        """LLM용 히스토리 반환."""
        messages = [
            Message(id="1", conversation_id="c", role="user", content="질문1"),
            Message(id="2", conversation_id="c", role="assistant", content="답변1"),
            Message(id="3", conversation_id="c", role="user", content="질문2"),
        ]
        conv = Conversation(id="c", user_id="u", messages=messages)

        history = conv.get_history_for_llm(max_messages=10)

        assert len(history) == 3
        assert history[0] == {"role": "user", "content": "질문1"}
        assert history[1] == {"role": "assistant", "content": "답변1"}
        assert history[2] == {"role": "user", "content": "질문2"}

    def test_get_history_for_llm_limited(self):
        """제한된 히스토리."""
        messages = [
            Message(id=str(i), conversation_id="c", role="user", content=f"메시지{i}")
            for i in range(20)
        ]
        conv = Conversation(id="c", user_id="u", messages=messages)

        history = conv.get_history_for_llm(max_messages=5)

        assert len(history) == 5


class TestConversationRepository:
    """대화 저장소 테스트."""

    @pytest.fixture
    def repo(self, tmp_path):
        """테스트용 저장소."""
        db_path = str(tmp_path / "test_conv.db")
        return ConversationRepository(db_path=db_path)

    def test_create_conversation(self, repo):
        """대화 생성."""
        conv = repo.create_conversation(user_id="user_123")

        assert conv is not None
        assert conv.user_id == "user_123"
        assert conv.status == "active"
        assert conv.id.startswith("conv_")

    def test_get_conversation(self, repo):
        """대화 조회."""
        created = repo.create_conversation(user_id="user_123")
        retrieved = repo.get_conversation(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_conversation_not_found(self, repo):
        """존재하지 않는 대화."""
        conv = repo.get_conversation("conv_nonexistent")

        assert conv is None

    def test_add_message(self, repo):
        """메시지 추가."""
        conv = repo.create_conversation(user_id="user_123")

        msg = repo.add_message(
            conversation_id=conv.id,
            role="user",
            content="테스트 메시지"
        )

        assert msg is not None
        assert msg.role == "user"
        assert msg.content == "테스트 메시지"

    def test_add_message_with_intent(self, repo):
        """의도가 있는 메시지 추가."""
        conv = repo.create_conversation(user_id="user_123")

        msg = repo.add_message(
            conversation_id=conv.id,
            role="assistant",
            content="주문을 확인해 드리겠습니다.",
            intent="order_status"
        )

        assert msg.intent == "order_status"

    def test_get_user_conversations(self, repo):
        """사용자 대화 목록."""
        repo.create_conversation(user_id="user_A")
        repo.create_conversation(user_id="user_A")
        repo.create_conversation(user_id="user_B")

        convs = repo.get_user_conversations(user_id="user_A")

        assert len(convs) == 2

    def test_close_conversation(self, repo):
        """대화 종료."""
        conv = repo.create_conversation(user_id="user_123")

        result = repo.close_conversation(conv.id)

        assert result is True

        updated = repo.get_conversation(conv.id)
        assert updated.status == "closed"

    def test_delete_conversation(self, repo):
        """대화 삭제."""
        conv = repo.create_conversation(user_id="user_123")

        result = repo.delete_conversation(conv.id)

        assert result is True

        deleted = repo.get_conversation(conv.id)
        assert deleted is None


class TestConversationManager:
    """대화 매니저 테스트."""

    @pytest.fixture
    def manager(self, tmp_path):
        """테스트용 매니저."""
        db_path = str(tmp_path / "test_manager.db")
        repo = ConversationRepository(db_path=db_path)
        return ConversationManager(repo=repo)

    def test_get_conversation(self, manager):
        """대화 조회."""
        conv = manager.repo.create_conversation(user_id="user_123")
        retrieved = manager.get_conversation(conv.id)

        assert retrieved is not None
        assert retrieved.id == conv.id

    def test_close_conversation(self, manager):
        """대화 종료."""
        conv = manager.repo.create_conversation(user_id="user_123")

        result = manager.close_conversation(conv.id)

        assert result is True

    def test_get_user_conversations(self, manager):
        """사용자 대화 목록."""
        manager.repo.create_conversation(user_id="user_test")
        manager.repo.create_conversation(user_id="user_test")

        convs = manager.get_user_conversations(user_id="user_test")

        assert len(convs) == 2

    def test_get_history_for_agent(self, manager):
        """에이전트용 히스토리."""
        conv = manager.repo.create_conversation(user_id="user_123")
        manager.repo.add_message(conv.id, "user", "질문입니다")
        manager.repo.add_message(conv.id, "assistant", "답변입니다")

        # 대화 다시 로드
        conv = manager.get_conversation(conv.id)
        history = manager.get_history_for_agent(conv.id)

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
