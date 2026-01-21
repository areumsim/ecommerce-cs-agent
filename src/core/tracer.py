"""처리 파이프라인 트레이서.

에이전트 처리 과정의 모든 단계를 추적하고 기록합니다.
- 의도 분류
- LLM 호출
- 오케스트레이터 결정
- 도구 실행
- 가드레일 적용
- SPARQL 쿼리
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """단일 처리 단계"""
    step_id: str
    step_type: str  # intent | llm | orchestrator | tool | guard | sparql
    name: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class TraceSession:
    """전체 요청 처리 세션"""
    session_id: str
    user_id: str
    user_message: str
    timestamp: str
    steps: List[TraceStep] = field(default_factory=list)
    final_response: Optional[Dict[str, Any]] = None
    total_duration_ms: float = 0.0
    llm_calls: int = 0
    sparql_queries: int = 0
    guardrails_applied: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_message": self.user_message,
            "timestamp": self.timestamp,
            "steps": [asdict(s) for s in self.steps],
            "final_response": self.final_response,
            "summary": {
                "total_duration_ms": self.total_duration_ms,
                "total_steps": len(self.steps),
                "llm_calls": self.llm_calls,
                "sparql_queries": self.sparql_queries,
                "guardrails_applied": self.guardrails_applied,
            }
        }


class Tracer:
    """파이프라인 트레이서"""
    
    _current_session: Optional[TraceSession] = None
    _sessions: List[TraceSession] = []
    _save_dir: Path = Path("data/traces")
    _enabled: bool = True
    _max_sessions: int = 100
    
    @classmethod
    def enable(cls):
        cls._enabled = True
    
    @classmethod
    def disable(cls):
        cls._enabled = False
    
    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled
    
    @classmethod
    def start_session(cls, user_id: str, user_message: str) -> str:
        """새 추적 세션 시작"""
        if not cls._enabled:
            return ""
        
        session_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        cls._current_session = TraceSession(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            timestamp=datetime.now().isoformat(),
        )
        return session_id
    
    @classmethod
    def end_session(cls, final_response: Optional[Dict[str, Any]] = None) -> Optional[TraceSession]:
        """세션 종료 및 저장"""
        if not cls._enabled or not cls._current_session:
            return None
        
        session = cls._current_session
        session.final_response = final_response
        
        if session.steps:
            session.total_duration_ms = sum(s.duration_ms for s in session.steps)
        
        session.llm_calls = sum(1 for s in session.steps if s.step_type == "llm")
        session.sparql_queries = sum(1 for s in session.steps if s.step_type == "sparql")
        session.guardrails_applied = sum(1 for s in session.steps if s.step_type == "guard")
        
        cls._sessions.append(session)
        if len(cls._sessions) > cls._max_sessions:
            cls._sessions = cls._sessions[-cls._max_sessions:]
        
        cls._save_session(session)
        
        cls._current_session = None
        return session
    
    @classmethod
    def add_step(
        cls,
        step_type: str,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> Optional[TraceStep]:
        """처리 단계 추가"""
        if not cls._enabled or not cls._current_session:
            return None
        
        step = TraceStep(
            step_id=f"step_{len(cls._current_session.steps):03d}",
            step_type=step_type,
            name=name,
            input_data=cls._sanitize_data(input_data),
            output_data=cls._sanitize_data(output_data),
            metadata=metadata or {},
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        cls._current_session.steps.append(step)
        return step
    
    @classmethod
    @contextmanager
    def trace_step(cls, step_type: str, name: str, input_data: Optional[Dict[str, Any]] = None):
        """컨텍스트 매니저로 단계 추적"""
        if not cls._enabled or not cls._current_session:
            yield None
            return
        
        start_time = time.time()
        step = TraceStep(
            step_id=f"step_{len(cls._current_session.steps):03d}",
            step_type=step_type,
            name=name,
            input_data=cls._sanitize_data(input_data),
            start_time=start_time,
        )
        
        try:
            yield step
            step.success = True
        except Exception as e:
            step.success = False
            step.error = str(e)
            raise
        finally:
            step.end_time = time.time()
            step.duration_ms = (step.end_time - step.start_time) * 1000
            cls._current_session.steps.append(step)
    
    @classmethod
    def get_current_session(cls) -> Optional[TraceSession]:
        return cls._current_session
    
    @classmethod
    def get_recent_sessions(cls, limit: int = 10) -> List[TraceSession]:
        return cls._sessions[-limit:]
    
    @classmethod
    def get_session_by_id(cls, session_id: str) -> Optional[TraceSession]:
        for session in cls._sessions:
            if session.session_id == session_id:
                return session
        return None
    
    @classmethod
    def _sanitize_data(cls, data: Any, max_str_len: int = 500) -> Any:
        """민감 정보 마스킹 및 크기 제한"""
        if data is None:
            return None
        if isinstance(data, str):
            if "sk-" in data or "api_key" in data.lower():
                return "[REDACTED]"
            if len(data) > max_str_len:
                return data[:max_str_len] + "..."
            return data
        if isinstance(data, dict):
            return {k: cls._sanitize_data(v, max_str_len) for k, v in data.items()}
        if isinstance(data, list):
            return [cls._sanitize_data(item, max_str_len) for item in data[:20]]
        return data
    
    @classmethod
    def _save_session(cls, session: TraceSession):
        """세션을 파일로 저장"""
        try:
            cls._save_dir.mkdir(parents=True, exist_ok=True)
            filepath = cls._save_dir / f"{session.session_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"트레이스 저장 실패: {e}")
    
    @classmethod
    def format_for_display(cls, session: Optional[TraceSession] = None) -> str:
        """세션을 사람이 읽기 쉬운 형식으로 포맷"""
        if session is None:
            session = cls._current_session
        if session is None:
            return "추적 세션 없음"
        
        lines = [
            f"{'='*60}",
            f"🔍 TRACE SESSION: {session.session_id}",
            f"{'='*60}",
            f"👤 사용자: {session.user_id}",
            f"💬 메시지: {session.user_message[:100]}{'...' if len(session.user_message) > 100 else ''}",
            f"⏰ 시간: {session.timestamp}",
            f"",
            f"📊 요약",
            f"  • 총 단계: {len(session.steps)}",
            f"  • LLM 호출: {session.llm_calls}",
            f"  • SPARQL 쿼리: {session.sparql_queries}",
            f"  • 가드레일: {session.guardrails_applied}",
            f"  • 총 소요시간: {session.total_duration_ms:.1f}ms",
            f"",
            f"{'─'*60}",
            f"📋 처리 단계",
            f"{'─'*60}",
        ]
        
        step_icons = {
            "intent": "🎯",
            "llm": "🤖",
            "orchestrator": "🎭",
            "tool": "🔧",
            "guard": "🛡️",
            "sparql": "📊",
        }
        
        for step in session.steps:
            icon = step_icons.get(step.step_type, "•")
            status = "✅" if step.success else "❌"
            
            lines.append(f"\n{icon} [{step.step_id}] {step.name} {status}")
            lines.append(f"   유형: {step.step_type} | 시간: {step.duration_ms:.1f}ms")
            
            if step.input_data:
                input_str = json.dumps(step.input_data, ensure_ascii=False)
                if len(input_str) > 200:
                    input_str = input_str[:200] + "..."
                lines.append(f"   입력: {input_str}")
            
            if step.output_data:
                output_str = json.dumps(step.output_data, ensure_ascii=False)
                if len(output_str) > 200:
                    output_str = output_str[:200] + "..."
                lines.append(f"   출력: {output_str}")
            
            if step.metadata:
                for k, v in step.metadata.items():
                    lines.append(f"   {k}: {v}")
            
            if step.error:
                lines.append(f"   ⚠️ 에러: {step.error}")
        
        lines.append(f"\n{'='*60}")
        return "\n".join(lines)


def start_trace(user_id: str, user_message: str) -> str:
    return Tracer.start_session(user_id, user_message)

def end_trace(final_response: Optional[Dict[str, Any]] = None) -> Optional[TraceSession]:
    return Tracer.end_session(final_response)

def trace_step(step_type: str, name: str, input_data: Optional[Dict[str, Any]] = None):
    return Tracer.trace_step(step_type, name, input_data)

def add_trace(
    step_type: str,
    name: str,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    duration_ms: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
) -> Optional[TraceStep]:
    return Tracer.add_step(step_type, name, input_data, output_data, metadata, duration_ms, success, error)

def get_trace_display() -> str:
    return Tracer.format_for_display()

def get_current_trace() -> Optional[TraceSession]:
    return Tracer.get_current_session()
