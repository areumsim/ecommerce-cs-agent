from __future__ import annotations
"""FastAPI 서버 (정책 검색/주문/티켓/대화).

구성
- 정책 검색: 로컬 인덱스(JSONL)를 조회
- 주문/티켓: CSV 저장소 기반 서비스 호출
- 대화: 의도 분류 → 오케스트레이터 실행
- 인증: JWT 기반 사용자 인증
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from contextlib import asynccontextmanager

from src.rag.retriever import PolicyRetriever
from src.agents.tools import order_tools
from src.agents.nodes.intent_classifier import classify_intent_async
from src.agents.orchestrator import run as orchestrate
from src.agents.state import AgentState
from src.llm.client import cleanup_client

# 인증 모듈
from src.auth import (
    AuthRepository,
    User,
    UserCreate,
    UserLogin,
    TokenResponse,
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_password,
    get_current_user,
    get_current_active_user,
    get_optional_user,
    get_auth_repo,
)
from src.auth.models import RefreshRequest, UserResponse
from src.auth.jwt_handler import get_token_expiry_seconds

# 커스텀 예외
from src.core.exceptions import (
    AppError,
    AuthError,
    RateLimitError,
    ValidationError,
    NotFoundError,
    PermissionError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 정보 설정
    from src.monitoring.metrics import set_app_info
    set_app_info("ecommerce-agent", "0.2.0", "development")

    yield
    await cleanup_client()


app = FastAPI(title="Ecommerce Agent API", version="0.2.0", lifespan=lifespan)

# CORS 미들웨어
# ⚠️ 프로덕션 배포 시 주의:
# - allow_origins=["*"]는 개발 편의용 설정입니다
# - 프로덕션에서는 반드시 특정 도메인으로 제한하세요
# - 예: allow_origins=["https://your-domain.com", "https://api.your-domain.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus 모니터링 미들웨어
from src.monitoring import PrometheusMiddleware
app.add_middleware(PrometheusMiddleware)


# -------- 전역 예외 핸들러 --------


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """애플리케이션 예외 핸들러."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """Rate Limit 예외 핸들러."""
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(int(exc.retry_after))
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """일반 예외 핸들러."""
    import logging
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "내부 서버 오류가 발생했습니다",
        },
    )


class CancelRequest(BaseModel):
    reason: str


class CreateTicketRequest(BaseModel):
    user_id: str
    order_id: Optional[str] = None
    issue_type: str = "other"
    description: str
    priority: str = "normal"


retriever = PolicyRetriever()


@app.get("/healthz")
async def healthz() -> Dict[str, str]:
    return {"status": "ok"}


# -------- Monitoring --------


from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response as StarletteResponse


@app.get("/metrics")
async def metrics() -> StarletteResponse:
    """Prometheus 메트릭 엔드포인트."""
    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/", include_in_schema=False)
async def root() -> Dict[str, Any]:
    """루트 엔드포인트: 간단한 안내 정보 제공."""
    return {
        "name": "Ecommerce Agent API",
        "version": "0.2.0",
        "links": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "healthz": "/healthz",
            "health": "/health",
            "metrics": "/metrics",
            "search_sample": "/policies/search?q=환불&top_k=3",
        },
        "message": "API가 실행 중입니다. 자세한 정보는 /docs를 확인하세요.",
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """상세 헬스체크."""
    import sqlite3
    from pathlib import Path

    health = {
        "status": "healthy",
        "components": {},
    }

    # DB 체크
    try:
        db_path = Path("data/ecommerce.db")
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            health["components"]["database"] = {"status": "up"}
        else:
            health["components"]["database"] = {"status": "down", "reason": "file not found"}
            health["status"] = "degraded"
    except Exception as e:
        health["components"]["database"] = {"status": "down", "reason": str(e)}
        health["status"] = "degraded"

    # RAG 인덱스 체크
    try:
        from src.rag.retriever import get_retriever
        rag_retriever = get_retriever()
        health["components"]["rag_index"] = {"status": "up", "documents": len(rag_retriever._docs)}
    except Exception as e:
        health["components"]["rag_index"] = {"status": "down", "reason": str(e)}
        health["status"] = "degraded"

    return health


@app.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """준비 상태 확인 (Kubernetes readiness probe)."""
    # 필수 컴포넌트 체크
    try:
        from pathlib import Path
        if not Path("data/ecommerce.db").exists():
            raise HTTPException(status_code=503, detail="Database not ready")
        return {"status": "ready"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# -------- Authentication --------


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    repo: AuthRepository = Depends(get_auth_repo),
) -> UserResponse:
    """회원가입."""
    try:
        user = repo.create_user(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
        )
        return user.to_response()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/auth/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    repo: AuthRepository = Depends(get_auth_repo),
) -> TokenResponse:
    """로그인 (토큰 발급)."""
    user = repo.get_user_by_email(credentials.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )

    # 토큰 생성
    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id)

    # 리프레시 토큰 저장
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    repo.save_refresh_token(user.id, refresh_token, expires_at)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=get_token_expiry_seconds(),
    )


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    repo: AuthRepository = Depends(get_auth_repo),
) -> TokenResponse:
    """토큰 갱신."""
    # 리프레시 토큰 검증
    token_data = verify_token(request.refresh_token, token_type="refresh")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 리프레시 토큰입니다",
        )

    # DB에서 토큰 확인
    stored_token = repo.get_refresh_token(request.refresh_token)

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 만료되었거나 무효화되었습니다",
        )

    # 사용자 조회
    user = repo.get_user_by_id(token_data.user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다",
        )

    # 기존 토큰 무효화
    repo.revoke_refresh_token(request.refresh_token)

    # 새 토큰 생성
    access_token = create_access_token(user.id, user.email, user.role)
    new_refresh_token = create_refresh_token(user.id)

    # 새 리프레시 토큰 저장
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    repo.save_refresh_token(user.id, new_refresh_token, expires_at)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=get_token_expiry_seconds(),
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    """현재 사용자 정보."""
    return current_user.to_response()


@app.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
    repo: AuthRepository = Depends(get_auth_repo),
) -> Dict[str, str]:
    """로그아웃 (모든 토큰 무효화)."""
    revoked = repo.revoke_all_user_tokens(current_user.id)
    return {"message": f"로그아웃 완료 ({revoked}개 토큰 무효화)"}


# -------- Conversations (Multi-turn) --------


from src.conversation import (
    ConversationManager,
    ConversationRepository,
    ConversationCreate,
    MessageCreate,
)
from src.conversation.models import ConversationResponse, ConversationDetailResponse, MessageResponse
from src.conversation.manager import get_conversation_repo


def get_conv_manager() -> ConversationManager:
    """대화 매니저 반환."""
    return ConversationManager()


@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
) -> ConversationResponse:
    """새 대화 시작."""
    repo = get_conversation_repo()
    conversation = repo.create_conversation(
        user_id=current_user.id,
        title=req.title,
        metadata=req.metadata,
    )
    return conversation.to_response()


@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
) -> List[ConversationResponse]:
    """사용자의 대화 목록 조회."""
    repo = get_conversation_repo()
    conversations = repo.get_user_conversations(
        user_id=current_user.id,
        status=status_filter,
        limit=limit,
    )
    return [c.to_response() for c in conversations]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
) -> ConversationDetailResponse:
    """대화 상세 조회 (메시지 포함)."""
    repo = get_conversation_repo()
    conversation = repo.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

    return conversation.to_detail_response()


@app.post("/conversations/{conversation_id}/messages", response_model=Dict[str, Any])
async def send_message(
    conversation_id: str,
    req: MessageCreate,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """대화에 메시지 전송 (멀티턴)."""
    manager = get_conv_manager()

    # 대화 소유권 확인
    repo = get_conversation_repo()
    conversation = repo.get_conversation(conversation_id, include_messages=False)

    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

    if conversation.status != "active":
        raise HTTPException(status_code=400, detail="종료된 대화입니다")

    # 메시지 처리
    response, _ = await manager.process_message(
        user_id=current_user.id,
        message=req.content,
        conversation_id=conversation_id,
    )

    return {
        "conversation_id": conversation_id,
        **response,
    }


@app.delete("/conversations/{conversation_id}")
async def close_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, str]:
    """대화 종료."""
    repo = get_conversation_repo()
    conversation = repo.get_conversation(conversation_id, include_messages=False)

    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

    repo.close_conversation(conversation_id)
    return {"message": "대화가 종료되었습니다"}


# -------- Policies --------


@app.get("/policies/search")
async def policies_search(q: str = Query(..., min_length=1), top_k: int = 5) -> Dict[str, Any]:
    hits = retriever.search_policy(q, top_k=top_k)
    return {
        "query": q,
        "hits": [
            {"id": h.id, "score": h.score, "text": h.text, "metadata": h.metadata}
            for h in hits
        ],
    }


# -------- Orders --------


@app.get("/users/{user_id}/orders")
async def list_user_orders(user_id: str, status: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    orders = await order_tools.get_user_orders(user_id=user_id, status=status, limit=limit)
    return {"orders": [o.__dict__ for o in orders]}


@app.get("/orders/{order_id}")
async def order_detail(order_id: str) -> Dict[str, Any]:
    try:
        detail = await order_tools.get_order_detail(order_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="order not found")
    return {"order": detail.order.__dict__, "items": detail.items}


@app.get("/orders/{order_id}/status")
async def order_status(order_id: str) -> Dict[str, Any]:
    try:
        status = await order_tools.get_order_status(order_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="order not found")
    return {"status": status.__dict__}


@app.post("/orders/{order_id}/cancel")
async def order_cancel(order_id: str, body: CancelRequest) -> Dict[str, Any]:
    try:
        res = await order_tools.request_cancel(order_id, body.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="order not found")
    return res


# -------- Tickets --------


@app.post("/tickets")
async def create_ticket(body: CreateTicketRequest) -> Dict[str, Any]:
    rec = await order_tools.create_ticket(
        user_id=body.user_id,
        order_id=body.order_id,
        issue_type=body.issue_type,
        description=body.description,
        priority=body.priority,
    )
    return {"ticket": rec}


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> Dict[str, Any]:
    t = await order_tools.get_ticket(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket": t}


@app.get("/users/{user_id}/tickets")
async def list_tickets(user_id: str, status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    rows = await order_tools.list_user_tickets(user_id=user_id, status=status, limit=limit)
    return {"tickets": rows}


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str) -> Dict[str, Any]:
    updated = await order_tools.update_ticket_status(ticket_id, "resolved")
    return {"ticket": updated}


# -------- Vision (이미지 분석) --------


class ImageAnalyzeRequest(BaseModel):
    """이미지 분석 요청."""
    image_base64: str
    analysis_type: str = "product"  # product 또는 defect


@app.post("/vision/analyze")
async def analyze_image(req: ImageAnalyzeRequest) -> Dict[str, Any]:
    """이미지 분석 엔드포인트.

    Args:
        req: 이미지 분석 요청 (base64 이미지, 분석 유형)

    Returns:
        분석 결과
    """
    import base64
    from src.vision import get_product_analyzer, get_defect_detector

    try:
        # base64 디코딩
        image_bytes = base64.b64decode(req.image_base64)

        # 분석기 선택
        if req.analysis_type == "defect":
            analyzer = get_defect_detector(use_clip=False)
        else:
            analyzer = get_product_analyzer(use_clip=False)

        # 분석 실행
        result = await analyzer.analyze(image_bytes)

        return {
            "success": result.success,
            "analysis_type": result.analysis_type,
            "description": result.description,
            "confidence": result.confidence,
            "labels": result.labels,
            "attributes": result.attributes,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 분석 실패: {str(e)}")


@app.post("/vision/defect")
async def analyze_defect(req: ImageAnalyzeRequest) -> Dict[str, Any]:
    """불량 탐지 전용 엔드포인트."""
    req.analysis_type = "defect"
    return await analyze_image(req)


# -------- OpenAI-compatible layer (optional) --------

def _oai_config() -> Dict[str, Any]:
    try:
        from src.config import get_config
        raw = get_config().get_raw("app") or {}
        return raw.get("openai_compat") or {}
    except Exception:
        return {}


def _oai_enabled() -> bool:
    return bool(_oai_config().get("enabled", False))


def _oai_mode() -> str:
    return str(_oai_config().get("mode", "orchestrator"))


def _oai_require_key() -> bool:
    return bool(_oai_config().get("require_api_key", False))


def _oai_allowed_keys() -> List[str]:
    return list(_oai_config().get("allowed_keys", []))


def _oai_default_model() -> str:
    return str(_oai_config().get("default_model", "ecommerce-agent-merged"))


def _check_oai_key(request: Request) -> None:
    if not _oai_require_key():
        return
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing api key")
    key = auth.split(" ", 1)[1].strip()
    if _oai_allowed_keys() and key not in _oai_allowed_keys():
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/v1/models")
async def oai_models() -> Dict[str, Any]:
    if not _oai_enabled():
        raise HTTPException(status_code=404, detail="not enabled")
    try:
        from src.config import get_config
        model = get_config().llm.model or _oai_default_model()
    except Exception:
        model = _oai_default_model()
    return {"object": "list", "data": [{"id": model, "object": "model"}]}


class _OAIMessage(BaseModel):
    role: str
    content: str


class _OAIChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[_OAIMessage]
    stream: Optional[bool] = False


@app.post("/v1/chat/completions")
async def oai_chat(request: Request, body: _OAIChatRequest):
    if not _oai_enabled():
        raise HTTPException(status_code=404, detail="not enabled")
    _check_oai_key(request)

    import json as _json
    import time as _time

    model = body.model or _oai_default_model()
    created = int(_time.time())
    # 마지막 user 메시지 추출
    user_msg = ""
    for m in reversed(body.messages or []):
        if (m.role or "").lower() == "user":
            user_msg = m.content or ""
            break

    mode = _oai_mode()

    # 스트리밍 모드 처리
    if body.stream:
        async def generate_stream():
            try:
                if mode == "passthrough":
                    # LLM 직접 스트리밍
                    from src.llm.client import get_client
                    client = get_client()
                    messages = [{"role": m.role, "content": m.content} for m in (body.messages or [])]
                    async for chunk in client.chat_stream(messages):
                        data = {
                            "id": f"chatcmpl-{created}",
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]
                        }
                        yield f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"
                else:
                    # orchestrator 경유 (청크 단위로 분할)
                    result = await classify_intent_async(user_msg)
                    intent, sub_intent, payload = result.intent, result.sub_intent, result.payload
                    if intent == "unknown":
                        intent = "policy"
                        payload = {"query": user_msg, "top_k": 5}
                    st = AgentState(user_id="oai", intent=intent, sub_intent=sub_intent, payload=payload)
                    st = await orchestrate(st)
                    final = st.final_response or {}
                    text = (
                        final.get("response")
                        or (f"정책 검색 결과 {len(final.get('hits', []))}건" if final.get("hits") else None)
                        or (f"주문 {len(final.get('orders', []))}건" if final.get("orders") else None)
                        or (f"티켓 {final.get('ticket',{}).get('ticket_id','')} 처리" if final.get("ticket") else None)
                        or (f"상태: {final.get('status',{}).get('status','')}" if final.get("status") else None)
                        or _json.dumps(final, ensure_ascii=False)
                    )
                    # 텍스트를 청크로 분할하여 스트리밍
                    chunk_size = 10
                    for i in range(0, len(text), chunk_size):
                        chunk = text[i:i+chunk_size]
                        data = {
                            "id": f"chatcmpl-{created}",
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]
                        }
                        yield f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"
                # 종료 청크
                data = {
                    "id": f"chatcmpl-{created}",
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # 비스트리밍 모드
    text = ""

    if mode == "passthrough":
        # LLM 직접 호출
        from src.llm.client import get_client
        client = get_client()
        messages = [{"role": m.role, "content": m.content} for m in (body.messages or [])]
        try:
            text = await client.chat(messages)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"llm error: {e}")
    else:
        # orchestrator 경유
        try:
            result = await classify_intent_async(user_msg)
            intent, sub_intent, payload = result.intent, result.sub_intent, result.payload
            if intent == "unknown":
                intent = "policy"
                payload = {"query": user_msg, "top_k": 5}
            st = AgentState(user_id="oai", intent=intent, sub_intent=sub_intent, payload=payload)
            st = await orchestrate(st)
            final = st.final_response or {}
            text = (
                final.get("response")
                or (f"정책 검색 결과 {len(final.get('hits', []))}건" if final.get("hits") else None)
                or (f"주문 {len(final.get('orders', []))}건" if final.get("orders") else None)
                or (f"티켓 {final.get('ticket',{}).get('ticket_id','')} 처리" if final.get("ticket") else None)
                or (f"상태: {final.get('status',{}).get('status','')}" if final.get("status") else None)
                or _json.dumps(final, ensure_ascii=False)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"orchestrator error: {e}")

    return {
        "id": f"chatcmpl-{created}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
# -------- Chat (intent→orchestrator) --------


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.post("/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    result = await classify_intent_async(req.message)
    intent, sub_intent, payload = result.intent, result.sub_intent, result.payload
    if intent == "unknown":
        intent = "policy"
        payload = {"query": req.message, "top_k": 5}
    if intent == "order" and sub_intent in {"status", "detail", "cancel"} and not payload.get("order_id"):
        return {"need": "order_id", "message": "주문번호(ORD-...)를 알려주세요."}
    state = AgentState(user_id=req.user_id, intent=intent, sub_intent=sub_intent, payload=payload)
    state = await orchestrate(state)
    return state.final_response or {}


class ChatStreamRequest(BaseModel):
    """스트리밍 채팅 요청."""
    message: str
    system_prompt: Optional[str] = None


@app.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest):
    """스트리밍 채팅 응답 (SSE).

    Server-Sent Events 형식으로 응답을 스트리밍합니다.
    각 청크는 `data: {text}\n\n` 형식으로 전송됩니다.
    """
    from src.llm import get_client

    async def generate():
        try:
            client = get_client()
            messages = [{"role": "user", "content": req.message}]

            async for chunk in client.chat_stream(messages, system_prompt=req.system_prompt):
                # SSE 형식으로 전송
                yield f"data: {chunk}\n\n"

            # 스트림 종료 신호
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"스트리밍 오류: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
