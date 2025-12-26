"""대화 매니저 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.conversation.manager import ConversationManager, get_conversation_repo
from src.conversation.models import Conversation, Message


class TestGetConversationRepo:
    """get_conversation_repo 테스트."""

    def test_returns_repository(self):
        """ConversationRepository 반환."""
        repo = get_conversation_repo()
        assert repo is not None

    def test_singleton(self):
        """싱글톤 패턴."""
        repo1 = get_conversation_repo()
        repo2 = get_conversation_repo()
        assert repo1 is repo2


class TestConversationManagerInit:
    """ConversationManager 초기화 테스트."""

    def test_default_repo(self):
        """기본 저장소 사용."""
        manager = ConversationManager()
        assert manager.repo is not None

    def test_custom_repo(self):
        """커스텀 저장소 사용."""
        mock_repo = MagicMock()
        manager = ConversationManager(repo=mock_repo)
        assert manager.repo is mock_repo

    def test_default_max_history(self):
        """기본 히스토리 제한."""
        manager = ConversationManager()
        assert manager.max_history_messages == 10

    def test_custom_max_history(self):
        """커스텀 히스토리 제한."""
        manager = ConversationManager(max_history_messages=20)
        assert manager.max_history_messages == 20


class TestProcessMessage:
    """process_message 테스트."""

    @pytest.mark.asyncio
    async def test_new_conversation_created(self):
        """새 대화 생성."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_repo.create_conversation.return_value = mock_conversation
        mock_repo.get_conversation.return_value = None

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"response": "안녕하세요!", "intent": "greeting"}

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="안녕하세요",
            )

        assert conv_id == "conv_123"
        mock_repo.create_conversation.assert_called_once_with("user_001")

    @pytest.mark.asyncio
    async def test_existing_conversation_used(self):
        """기존 대화 사용."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_existing",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(return_value=[])
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"response": "네!", "intent": "general"}

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="추가 질문",
                conversation_id="conv_existing",
            )

        assert conv_id == "conv_existing"
        mock_repo.get_conversation.assert_called_with("conv_existing")

    @pytest.mark.asyncio
    async def test_wrong_user_creates_new_conversation(self):
        """다른 사용자의 대화는 새로 생성."""
        mock_repo = MagicMock()
        other_user_conv = Conversation(
            id="conv_other",
            user_id="other_user",  # 다른 사용자
            status="active",
        )
        new_conv = Conversation(
            id="conv_new",
            user_id="user_001",
            status="active",
        )
        mock_repo.get_conversation.return_value = other_user_conv
        mock_repo.create_conversation.return_value = new_conv

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"response": "네!"}

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="테스트",
                conversation_id="conv_other",
            )

        assert conv_id == "conv_new"
        mock_repo.create_conversation.assert_called_once_with("user_001")

    @pytest.mark.asyncio
    async def test_inactive_conversation_creates_new(self):
        """비활성 대화는 새로 생성."""
        mock_repo = MagicMock()
        inactive_conv = Conversation(
            id="conv_inactive",
            user_id="user_001",
            status="closed",  # 비활성
        )
        new_conv = Conversation(
            id="conv_new",
            user_id="user_001",
            status="active",
        )
        mock_repo.get_conversation.return_value = inactive_conv
        mock_repo.create_conversation.return_value = new_conv

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"response": "네!"}

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="테스트",
                conversation_id="conv_inactive",
            )

        assert conv_id == "conv_new"

    @pytest.mark.asyncio
    async def test_message_saved(self):
        """메시지 저장 확인."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(return_value=[])
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"response": "응답입니다", "intent": "general"}

            await manager.process_message(
                user_id="user_001",
                message="테스트 메시지",
                conversation_id="conv_123",
            )

        # 사용자 메시지 저장 확인
        calls = mock_repo.add_message.call_args_list
        assert len(calls) >= 2  # user + assistant

        user_call = calls[0]
        assert user_call[1]["role"] == "user"
        assert user_call[1]["content"] == "테스트 메시지"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """오류 처리."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(return_value=[])
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = Exception("테스트 오류")

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="테스트",
                conversation_id="conv_123",
            )

        assert "error" in response
        assert "오류가 발생했습니다" in response["response"]

    @pytest.mark.asyncio
    async def test_string_response_handling(self):
        """문자열 응답 처리."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(return_value=[])
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)

        with patch("src.agents.router.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = "단순 문자열 응답"

            response, conv_id = await manager.process_message(
                user_id="user_001",
                message="테스트",
                conversation_id="conv_123",
            )

        # 문자열 응답도 처리됨
        assert conv_id == "conv_123"


class TestGetConversation:
    """get_conversation 테스트."""

    def test_returns_conversation(self):
        """대화 반환."""
        mock_repo = MagicMock()
        expected = Conversation(id="conv_123", user_id="user_001", status="active")
        mock_repo.get_conversation.return_value = expected

        manager = ConversationManager(repo=mock_repo)
        result = manager.get_conversation("conv_123")

        assert result.id == "conv_123"


class TestGetUserConversations:
    """get_user_conversations 테스트."""

    def test_returns_list(self):
        """대화 목록 반환."""
        mock_repo = MagicMock()
        mock_repo.get_user_conversations.return_value = [
            Conversation(id="conv_1", user_id="user_001", status="active"),
            Conversation(id="conv_2", user_id="user_001", status="active"),
        ]

        manager = ConversationManager(repo=mock_repo)
        result = manager.get_user_conversations("user_001")

        assert len(result) == 2


class TestCloseConversation:
    """close_conversation 테스트."""

    def test_closes_conversation(self):
        """대화 종료."""
        mock_repo = MagicMock()
        mock_repo.close_conversation.return_value = True

        manager = ConversationManager(repo=mock_repo)
        result = manager.close_conversation("conv_123")

        assert result is True
        mock_repo.close_conversation.assert_called_with("conv_123")


class TestDeleteConversation:
    """delete_conversation 테스트."""

    def test_deletes_conversation(self):
        """대화 삭제."""
        mock_repo = MagicMock()
        mock_repo.delete_conversation.return_value = True

        manager = ConversationManager(repo=mock_repo)
        result = manager.delete_conversation("conv_123")

        assert result is True
        mock_repo.delete_conversation.assert_called_with("conv_123")


class TestGetHistoryForAgent:
    """get_history_for_agent 테스트."""

    def test_returns_history(self):
        """히스토리 반환."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(
            return_value=[{"role": "user", "content": "안녕"}]
        )
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)
        result = manager.get_history_for_agent("conv_123")

        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_returns_empty_for_nonexistent(self):
        """존재하지 않는 대화는 빈 리스트."""
        mock_repo = MagicMock()
        mock_repo.get_conversation.return_value = None

        manager = ConversationManager(repo=mock_repo)
        result = manager.get_history_for_agent("nonexistent")

        assert result == []

    def test_custom_max_messages(self):
        """커스텀 최대 메시지 수."""
        mock_repo = MagicMock()
        mock_conversation = Conversation(
            id="conv_123",
            user_id="user_001",
            status="active",
        )
        mock_conversation.get_history_for_llm = MagicMock(return_value=[])
        mock_repo.get_conversation.return_value = mock_conversation

        manager = ConversationManager(repo=mock_repo)
        manager.get_history_for_agent("conv_123", max_messages=5)

        mock_conversation.get_history_for_llm.assert_called_with(5)
