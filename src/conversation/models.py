"""대화 모델 정의.

대화 세션 및 메시지 관련 데이터 모델을 정의합니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================
# Pydantic 모델 (API 요청/응답)
# ============================================


class ConversationCreate(BaseModel):
    """대화 생성 요청."""

    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageCreate(BaseModel):
    """메시지 생성 요청."""

    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """메시지 응답."""

    id: str
    conversation_id: str
    role: str  # user, assistant, system
    content: str
    intent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class ConversationResponse(BaseModel):
    """대화 응답."""

    id: str
    user_id: str
    title: Optional[str] = None
    status: str  # active, closed, expired
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationDetailResponse(BaseModel):
    """대화 상세 응답 (메시지 포함)."""

    conversation: ConversationResponse
    messages: List[MessageResponse]


# ============================================
# 데이터클래스 (내부 사용)
# ============================================


@dataclass
class Message:
    """메시지 모델."""

    id: str
    conversation_id: str
    role: str  # user, assistant, system
    content: str
    intent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_response(self) -> MessageResponse:
        """응답용 데이터로 변환."""
        return MessageResponse(
            id=self.id,
            conversation_id=self.conversation_id,
            role=self.role,
            content=self.content,
            intent=self.intent,
            metadata=self.metadata,
            created_at=self.created_at,
        )

    def to_llm_format(self) -> Dict[str, str]:
        """LLM API 형식으로 변환."""
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class Conversation:
    """대화 모델."""

    id: str
    user_id: str
    title: Optional[str] = None
    status: str = "active"  # active, closed, expired
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    expires_at: Optional[str] = None
    messages: List[Message] = field(default_factory=list)

    def to_response(self) -> ConversationResponse:
        """응답용 데이터로 변환."""
        return ConversationResponse(
            id=self.id,
            user_id=self.user_id,
            title=self.title,
            status=self.status,
            message_count=len(self.messages),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_detail_response(self) -> ConversationDetailResponse:
        """상세 응답용 데이터로 변환."""
        return ConversationDetailResponse(
            conversation=self.to_response(),
            messages=[m.to_response() for m in self.messages],
        )

    def get_history_for_llm(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """LLM에 전달할 히스토리 형식으로 변환.

        Args:
            max_messages: 최대 메시지 수 (최근 N개)

        Returns:
            LLM API 형식의 메시지 리스트
        """
        # 최근 N개 메시지만 사용
        recent_messages = self.messages[-max_messages:] if self.messages else []
        return [m.to_llm_format() for m in recent_messages]
