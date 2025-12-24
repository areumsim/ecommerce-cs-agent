"""오케스트레이터: 의도별 처리 + LLM 응답 생성"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .state import AgentState
from .nodes.order_agent import handle_order_query
from .nodes.claim_agent import handle_claim
from src.rag.retriever import PolicyRetriever
from src.guardrails.pipeline import apply_guards, process_input, get_guard_summary
from src.llm.client import generate_response, get_llm_config
try:
    from src.llm.router import generate_routed_response
except Exception:
    generate_routed_response = None

logger = logging.getLogger(__name__)

retriever = PolicyRetriever()


def _is_llm_available() -> bool:
    """LLM 사용 가능 여부 확인"""
    try:
        config = get_llm_config()
        if config.provider in ("openai", "anthropic"):
            return bool(config.api_key)
        elif config.provider == "local":
            return bool(config.base_url)
        return False
    except Exception:
        return False


def _format_data_for_llm(data: Dict[str, Any], intent: str) -> str:
    """도구 결과를 LLM 입력용 문자열로 포맷"""
    if intent == "order":
        if "orders" in data:
            orders = data["orders"]
            if not orders:
                return "주문 내역이 없습니다."
            lines = ["주문 목록:"]
            for o in orders[:5]:
                lines.append(f"- {o.get('order_id', 'N/A')}: {o.get('status', 'N/A')} ({o.get('total_amount', 'N/A')}원)")
            return "\n".join(lines)
        elif "status" in data:
            st = data["status"]
            return f"주문번호: {st.get('order_id', 'N/A')}\n상태: {st.get('status', 'N/A')}\n최종 업데이트: {st.get('updated_at', 'N/A')}"
        elif "detail" in data:
            d = data["detail"]
            order = d.get("order", {})
            items = d.get("items", [])
            lines = [f"주문번호: {order.get('order_id', 'N/A')}", f"상태: {order.get('status', 'N/A')}", f"총액: {order.get('total_amount', 'N/A')}원", "상품:"]
            for item in items[:5]:
                lines.append(f"  - {item.get('product_name', 'N/A')} x {item.get('quantity', 1)}")
            return "\n".join(lines)
        elif "cancel_result" in data:
            res = data["cancel_result"]
            if res.get("success"):
                return f"주문 취소가 완료되었습니다. (주문번호: {res.get('order_id', 'N/A')})"
            else:
                return f"주문 취소에 실패했습니다. 사유: {res.get('error', '알 수 없는 오류')}"

    elif intent == "claim":
        if "ticket" in data:
            t = data["ticket"]
            return f"티켓이 생성되었습니다.\n티켓 ID: {t.get('ticket_id', 'N/A')}\n상태: {t.get('status', 'open')}\n우선순위: {t.get('priority', 'normal')}"

    elif intent == "policy":
        hits = data.get("hits", [])
        if not hits:
            return "관련 정책을 찾을 수 없습니다."
        lines = ["검색된 정책:"]
        for h in hits[:3]:
            text = h.get("text", "")[:200]
            lines.append(f"- {text}...")
        return "\n".join(lines)

    return json.dumps(data, ensure_ascii=False, indent=2)


async def run(state: AgentState) -> AgentState:
    """의도별 처리 및 응답 생성"""
    use_llm = _is_llm_available()
    user_message = state.payload.get("query") or state.payload.get("description", "")

    # 입력 가드 적용
    if user_message:
        input_guard_result = process_input(user_message, strict_mode=True)

        # 차단된 입력인 경우
        if input_guard_result.blocked:
            state.final_response = apply_guards({
                "error": input_guard_result.block_reason or "입력이 차단되었습니다.",
                "blocked": True,
            })
            return state

        # PII 마스킹된 텍스트 사용 (로깅용)
        if input_guard_result.pii_detected:
            logger.info(f"PII detected and masked: {len(input_guard_result.pii_detected)} items")

        # 경고가 있으면 로깅
        if input_guard_result.warnings:
            logger.warning(f"Input guard warnings: {input_guard_result.warnings}")

    if state.intent == "order":
        res = await handle_order_query(state.user_id, state.sub_intent or "list", state.payload)

        # 최근 구매한 상품 요약 요청 시(예: "내가 뭐 샀는지") 아이템 요약을 포함
        try:
            if (state.sub_intent in (None, "list")) and isinstance(res, dict) and "orders" in res and state.payload.get("include_items"):
                orders = res.get("orders", [])
                limit = int(state.payload.get("limit", 5) or 5)
                orders = orders[: max(0, limit)]

                aggregated: dict[str, int] = {}
                for o in orders:
                    oid = o.get("order_id") if isinstance(o, dict) else None
                    if not oid:
                        continue
                    detail = await handle_order_query(state.user_id, "detail", {"order_id": oid})
                    items = (detail.get("detail", {}) or {}).get("items", []) if isinstance(detail, dict) else []
                    for it in items:
                        title = (it.get("title") or it.get("product_name") or it.get("product_id") or "").strip()
                        if not title:
                            continue
                        qty = int(it.get("quantity", 1) or 1)
                        aggregated[title] = aggregated.get(title, 0) + qty

                # 상위 항목 10개 정렬
                top_items = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)[:10]
                res["recent_items"] = [{"title": k, "quantity": v} for k, v in top_items]
        except Exception as e:
            logger.warning(f"아이템 요약 생성 실패: {e}")

        if use_llm:
            try:
                context_str = _format_data_for_llm(res, "order")
                if generate_routed_response:
                    llm_response = await generate_routed_response(
                        context=res,
                        user_message=user_message or f"주문 {state.sub_intent} 정보를 알려주세요.",
                        intent="order",
                    )
                else:
                    llm_response = await generate_response(
                        context=res,
                        user_message=user_message or f"주문 {state.sub_intent} 정보를 알려주세요.",
                        intent="order",
                    )
                state.final_response = apply_guards({
                    "response": llm_response,
                    "data": res,
                })
            except Exception as e:
                logger.warning(f"LLM 응답 생성 실패, 기본 응답 사용: {e}")
                state.final_response = apply_guards(res)
        else:
            state.final_response = apply_guards(res)

        return state

    if state.intent == "claim":
        res = await handle_claim(state.user_id, state.payload)

        if use_llm:
            try:
                if generate_routed_response:
                    llm_response = await generate_routed_response(
                        context=res,
                        user_message=user_message or "클레임 접수 결과를 알려주세요.",
                        intent="claim",
                    )
                else:
                    llm_response = await generate_response(
                        context=res,
                        user_message=user_message or "클레임 접수 결과를 알려주세요.",
                        intent="claim",
                    )
                state.final_response = apply_guards({
                    "response": llm_response,
                    "data": res,
                })
            except Exception as e:
                logger.warning(f"LLM 응답 생성 실패, 기본 응답 사용: {e}")
                state.final_response = apply_guards(res)
        else:
            state.final_response = apply_guards(res)

        return state

    if state.intent == "policy":
        q = state.payload.get("query", "")
        hits = retriever.search_policy(q, top_k=int(state.payload.get("top_k", 5)))
        res = {
            "query": q,
            "hits": [{"id": h.id, "score": h.score, "text": h.text, "metadata": h.metadata} for h in hits],
        }

        if use_llm:
            try:
                if generate_routed_response:
                    llm_response = await generate_routed_response(
                        context=res,
                        user_message=q,
                        intent="policy",
                    )
                else:
                    llm_response = await generate_response(
                        context=res,
                        user_message=q,
                        intent="policy",
                    )
                state.final_response = apply_guards({
                    "response": llm_response,
                    "data": res,
                })
            except Exception as e:
                logger.warning(f"LLM 응답 생성 실패, 기본 응답 사용: {e}")
                state.final_response = apply_guards(res)
        else:
            state.final_response = apply_guards(res)

        return state

    state.final_response = apply_guards({"error": f"unknown intent: {state.intent}"})
    return state
