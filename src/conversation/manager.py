"""대화 매니저.

대화 세션 관리 및 에이전트 연동을 담당합니다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .models import Conversation, Message
from .repository import ConversationRepository

logger = logging.getLogger(__name__)

# 싱글톤 저장소
_conversation_repo: Optional[ConversationRepository] = None


def get_conversation_repo() -> ConversationRepository:
    """대화 저장소 반환."""
    global _conversation_repo
    if _conversation_repo is None:
        _conversation_repo = ConversationRepository()
    return _conversation_repo


class ConversationManager:
    """대화 매니저.

    멀티턴 대화 세션을 관리하고 에이전트와 연동합니다.
    """

    def __init__(
        self,
        repo: Optional[ConversationRepository] = None,
        max_history_messages: int = 10,
    ):
        """초기화.

        Args:
            repo: 대화 저장소 (없으면 기본값)
            max_history_messages: LLM에 전달할 최대 히스토리 메시지 수
        """
        self.repo = repo or get_conversation_repo()
        self.max_history_messages = max_history_messages

    async def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """메시지 처리 (멀티턴 지원).

        Args:
            user_id: 사용자 ID
            message: 사용자 메시지
            conversation_id: 대화 ID (없으면 새 대화 생성)

        Returns:
            (응답 딕셔너리, 대화 ID) 튜플
        """
        # 대화 가져오기 또는 생성
        if conversation_id:
            conversation = self.repo.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"대화를 찾을 수 없음: {conversation_id}")
                conversation = self.repo.create_conversation(user_id)
            elif conversation.user_id != user_id:
                logger.warning(f"대화 소유자 불일치: {conversation_id}")
                conversation = self.repo.create_conversation(user_id)
            elif conversation.status != "active":
                logger.info(f"비활성 대화, 새 대화 생성: {conversation_id}")
                conversation = self.repo.create_conversation(user_id)
        else:
            conversation = self.repo.create_conversation(user_id)

        # 사용자 메시지 저장
        self.repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # 히스토리 구성
        history = conversation.get_history_for_llm(self.max_history_messages)

        # 에이전트 호출
        try:
            from src.agents.router import process_message

            response = await process_message(
                user_id=user_id,
                message=message,
                history=history,
            )

            # 응답 추출
            if isinstance(response, dict):
                response_text = response.get("response", response.get("message", str(response)))
                intent = response.get("intent")
            else:
                response_text = str(response)
                intent = None

            # 어시스턴트 응답 저장
            self.repo.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_text,
                intent=intent,
            )

            # 대화 제목 자동 설정 (첫 메시지 기반)
            if not conversation.title and len(conversation.messages) == 0:
                title = message[:50] + ("..." if len(message) > 50 else "")
                self.repo.update_conversation(conversation.id, title=title)

            return response, conversation.id

        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")

            # 에러 메시지 저장
            error_response = {
                "response": "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다.",
                "error": str(e),
            }

            self.repo.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=error_response["response"],
                metadata={"error": str(e)},
            )

            return error_response, conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """대화 조회."""
        return self.repo.get_conversation(conversation_id)

    def get_user_conversations(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Conversation]:
        """사용자의 대화 목록 조회."""
        return self.repo.get_user_conversations(user_id, status, limit)

    def close_conversation(self, conversation_id: str) -> bool:
        """대화 종료."""
        return self.repo.close_conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        """대화 삭제."""
        return self.repo.delete_conversation(conversation_id)

    def get_history_for_agent(
        self,
        conversation_id: str,
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """에이전트에 전달할 히스토리 반환.

        Args:
            conversation_id: 대화 ID
            max_messages: 최대 메시지 수 (없으면 기본값)

        Returns:
            LLM API 형식의 메시지 리스트
        """
        conversation = self.repo.get_conversation(conversation_id)
        if not conversation:
            return []

        max_msgs = max_messages or self.max_history_messages
        return conversation.get_history_for_llm(max_msgs)
