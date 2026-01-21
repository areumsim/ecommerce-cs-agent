"""오케스트레이터: 의도별 처리 + LLM 응답 생성"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from .state import AgentState
from .nodes.order_agent import handle_order_query
from .nodes.claim_agent import handle_claim
from .nodes.recommend_agent import handle_recommendation
from src.rag.retriever import PolicyRetriever
from src.guardrails.pipeline import apply_guards, process_input, get_guard_summary
from src.llm.client import generate_response, get_llm_config
from src.core.tracer import add_trace, Tracer

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


def _format_template_response(data: Dict[str, Any], intent: str, sub_intent: Optional[str] = None) -> str:
    """LLM 없이 템플릿 기반 자연어 응답 생성"""
    
    if intent == "order":
        if "orders" in data:
            orders = data["orders"]
            if not orders:
                return "고객님의 주문 내역이 없습니다. 새로운 주문을 원하시면 말씀해 주세요."
            
            lines = [f"고객님의 최근 주문 {len(orders)}건입니다:\n"]
            for i, o in enumerate(orders[:5], 1):
                status_kr = {
                    "pending": "결제 대기",
                    "processing": "처리 중", 
                    "shipped": "배송 중",
                    "delivered": "배송 완료",
                    "cancelled": "취소됨"
                }.get(o.get("status", ""), o.get("status", ""))
                amount = o.get("total_amount", 0)
                amount_str = f"{int(amount):,}원" if amount else "금액 정보 없음"
                lines.append(f"{i}. 주문번호 {o.get('order_id', 'N/A')} - {status_kr} ({amount_str})")
            
            if data.get("recent_items"):
                lines.append("\n최근 구매하신 상품:")
                for item in data["recent_items"][:5]:
                    lines.append(f"  • {item.get('title', 'N/A')} x{item.get('quantity', 1)}")
            
            lines.append("\n자세한 내용은 주문번호를 말씀해 주세요.")
            return "\n".join(lines)
        
        elif "status" in data:
            st = data["status"]
            status_kr = {
                "pending": "결제 대기 중",
                "processing": "상품 준비 중",
                "shipped": "배송 중",
                "delivered": "배송 완료",
                "cancelled": "취소됨"
            }.get(st.get("status", ""), st.get("status", ""))
            
            result = f"주문번호 {st.get('order_id', 'N/A')}의 현재 상태는 **{status_kr}**입니다."
            if st.get("estimated_delivery"):
                result += f"\n예상 배송일: {st.get('estimated_delivery')}"
            if st.get("tracking_number"):
                result += f"\n운송장 번호: {st.get('tracking_number')}"
            return result
        
        elif "detail" in data:
            d = data["detail"]
            order = d.get("order", {})
            items = d.get("items", [])
            
            status_kr = {
                "pending": "결제 대기",
                "processing": "처리 중",
                "shipped": "배송 중", 
                "delivered": "배송 완료",
                "cancelled": "취소됨"
            }.get(order.get("status", ""), order.get("status", ""))
            
            amount = order.get("total_amount", 0)
            amount_str = f"{int(amount):,}원" if amount else "금액 정보 없음"
            
            lines = [
                f"**주문 상세 정보**",
                f"• 주문번호: {order.get('order_id', 'N/A')}",
                f"• 상태: {status_kr}",
                f"• 주문일: {order.get('order_date', 'N/A')}",
                f"• 총액: {amount_str}",
                f"\n**주문 상품** ({len(items)}개):"
            ]
            for item in items[:10]:
                if hasattr(item, 'unit_price'):
                    # dataclass 객체
                    price = item.unit_price or 0
                    title = getattr(item, 'title', None) or getattr(item, 'product_id', 'N/A')
                    qty = item.quantity
                else:
                    # dict 객체
                    price = item.get("unit_price", 0)
                    title = item.get('product_name') or item.get('title', 'N/A')
                    qty = item.get('quantity', 1)
                price_str = f"{int(float(price)):,}원" if price else ""
                lines.append(f"  • {title} x{qty} {price_str}")
            
            return "\n".join(lines)
        
        elif "cancel_result" in data:
            res = data["cancel_result"]
            if res.get("success") or res.get("ok"):
                return f"주문번호 {res.get('order_id', '')}의 취소가 완료되었습니다. 환불은 영업일 기준 3-5일 내에 처리됩니다."
            else:
                return f"죄송합니다. 주문 취소에 실패했습니다. 사유: {res.get('error', '알 수 없는 오류')}. 고객센터로 문의해 주세요."
    
    elif intent == "claim":
        if "ticket" in data:
            t = data["ticket"]
            priority_kr = {"high": "긴급", "normal": "일반", "low": "낮음"}.get(t.get("priority", "normal"), "일반")
            return (
                f"클레임이 접수되었습니다.\n\n"
                f"• 티켓 번호: {t.get('ticket_id', 'N/A')}\n"
                f"• 우선순위: {priority_kr}\n"
                f"• 상태: 접수됨\n\n"
                f"담당자가 확인 후 연락드리겠습니다. 평균 처리 시간은 1-2 영업일입니다."
            )
        elif "error" in data:
            return f"클레임 접수 중 문제가 발생했습니다: {data.get('error')}. 다시 시도해 주세요."
    
    elif intent == "policy":
        hits = data.get("hits", [])
        if not hits:
            return "죄송합니다. 관련 정책을 찾을 수 없습니다. 다른 키워드로 검색하시거나 고객센터로 문의해 주세요."
        
        lines = ["관련 정책 안내입니다:\n"]
        for i, h in enumerate(hits[:3], 1):
            text = h.get("text", "")
            title = h.get("metadata", {}).get("title", f"정책 {i}")
            if len(text) > 300:
                text = text[:300] + "..."
            lines.append(f"**{title}**\n{text}\n")
        
        lines.append("추가 문의사항이 있으시면 말씀해 주세요.")
        return "\n".join(lines)
    
    elif intent == "recommend":
        products = data.get("products", [])
        rec_type = data.get("recommendation_type", sub_intent or "추천")
        
        type_kr = {
            "similar": "유사 상품",
            "personalized": "맞춤 추천",
            "trending": "인기 상품",
            "bought_together": "함께 구매하면 좋은 상품"
        }.get(rec_type, "추천 상품")
        
        if not products:
            return f"죄송합니다. 현재 {type_kr}을 찾을 수 없습니다. 다른 상품을 검색해 보세요."
        
        lines = [f"**{type_kr}** {len(products)}개를 찾았습니다:\n"]
        for i, p in enumerate(products[:5], 1):
            price = p.get("price", 0)
            price_str = f"₩{int(price):,}" if price else "가격 정보 없음"
            rating = p.get("rating") or p.get("avg_rating", 0)
            rating_str = f" ⭐{rating:.1f}" if rating else ""
            reason = p.get("reason", "")
            reason_str = f" - {reason}" if reason else ""
            lines.append(f"{i}. **{p.get('name', 'N/A')}** {price_str}{rating_str}{reason_str}")
        
        if data.get("is_fallback"):
            lines.append(f"\n(참고: {data.get('fallback_reason', '대체 추천 사용')})")
        
        return "\n".join(lines)
    
    return json.dumps(data, ensure_ascii=False, indent=2)


async def run(state: AgentState) -> AgentState:
    """의도별 처리 및 응답 생성"""
    start_time = time.time()
    use_llm = _is_llm_available()
    user_message = state.payload.get("query") or state.payload.get("description", "")

    add_trace(
        "orchestrator", "시작",
        input_data={"intent": state.intent, "sub_intent": state.sub_intent, "user_id": state.user_id},
        metadata={"llm_available": use_llm}
    )

    if user_message:
        guard_start = time.time()
        input_guard_result = process_input(user_message, strict_mode=True)
        guard_duration = (time.time() - guard_start) * 1000

        add_trace(
            "guard", "입력 가드레일",
            input_data={"message_length": len(user_message)},
            output_data={
                "blocked": input_guard_result.blocked,
                "pii_count": len(input_guard_result.pii_detected),
                "warnings": input_guard_result.warnings[:3] if input_guard_result.warnings else []
            },
            duration_ms=guard_duration,
            success=not input_guard_result.blocked
        )

        if input_guard_result.blocked:
            state.final_response = apply_guards({
                "error": input_guard_result.block_reason or "입력이 차단되었습니다.",
                "blocked": True,
            })
            return state

        if input_guard_result.pii_detected:
            logger.info(f"PII detected and masked: {len(input_guard_result.pii_detected)} items")

        if input_guard_result.warnings:
            logger.warning(f"Input guard warnings: {input_guard_result.warnings}")

    if state.intent == "order":
        tool_start = time.time()
        res = await handle_order_query(state.user_id, state.sub_intent or "list", state.payload)
        tool_duration = (time.time() - tool_start) * 1000
        
        add_trace(
            "tool", f"주문 도구: {state.sub_intent or 'list'}",
            input_data={"user_id": state.user_id, "payload": state.payload},
            output_data={"order_count": len(res.get("orders", [])) if isinstance(res, dict) else 0},
            duration_ms=tool_duration
        )
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
                llm_start = time.time()
                llm_config = get_llm_config()
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
                llm_duration = (time.time() - llm_start) * 1000
                add_trace(
                    "llm", "LLM 응답 생성",
                    input_data={"intent": "order", "context_size": len(str(res))},
                    output_data={"response_length": len(llm_response)},
                    metadata={"provider": llm_config.provider, "model": llm_config.model},
                    duration_ms=llm_duration
                )
                state.final_response = apply_guards({
                    "response": llm_response,
                    "data": res,
                })
            except Exception as e:
                logger.warning(f"LLM 응답 생성 실패, 템플릿 응답 사용: {e}")
                add_trace("llm", "LLM 실패 - 템플릿 폴백", success=False, error=str(e))
                template_response = _format_template_response(res, "order", state.sub_intent)
                state.final_response = apply_guards({"response": template_response, "data": res})
        else:
            add_trace("orchestrator", "템플릿 응답 사용", metadata={"reason": "LLM 미사용"})
            template_response = _format_template_response(res, "order", state.sub_intent)
            state.final_response = apply_guards({"response": template_response, "data": res})

        return state

    if state.intent == "claim":
        tool_start = time.time()
        res = await handle_claim(state.user_id, state.payload)
        add_trace("tool", "클레임 도구", input_data=state.payload, duration_ms=(time.time() - tool_start) * 1000)

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
                logger.warning(f"LLM 응답 생성 실패, 템플릿 응답 사용: {e}")
                template_response = _format_template_response(res, "claim", state.sub_intent)
                state.final_response = apply_guards({"response": template_response, "data": res})
        else:
            template_response = _format_template_response(res, "claim", state.sub_intent)
            state.final_response = apply_guards({"response": template_response, "data": res})

        return state

    if state.intent == "policy":
        q = state.payload.get("query", "")
        rag_start = time.time()
        hits = retriever.search_policy(q, top_k=int(state.payload.get("top_k", 5)))
        rag_duration = (time.time() - rag_start) * 1000
        res = {
            "query": q,
            "hits": [{"id": h.id, "score": h.score, "text": h.text, "metadata": h.metadata} for h in hits],
        }
        add_trace(
            "tool", "정책 RAG 검색",
            input_data={"query": q, "top_k": state.payload.get("top_k", 5)},
            output_data={"hit_count": len(hits)},
            duration_ms=rag_duration
        )

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
                logger.warning(f"LLM 응답 생성 실패, 템플릿 응답 사용: {e}")
                template_response = _format_template_response(res, "policy", state.sub_intent)
                state.final_response = apply_guards({"response": template_response, "data": res})
        else:
            template_response = _format_template_response(res, "policy", state.sub_intent)
            state.final_response = apply_guards({"response": template_response, "data": res})

        return state

    if state.intent == "recommend":
        tool_start = time.time()
        res = await handle_recommendation(state.user_id, state.sub_intent, state.payload)
        add_trace(
            "tool", f"추천 도구: {state.sub_intent}",
            input_data={"user_id": state.user_id, "type": state.sub_intent},
            output_data={"product_count": len(res.get("products", [])) if isinstance(res, dict) else 0},
            duration_ms=(time.time() - tool_start) * 1000
        )

        if use_llm:
            try:
                if generate_routed_response:
                    llm_response = await generate_routed_response(
                        context=res,
                        user_message=user_message or "상품 추천을 알려주세요.",
                        intent="recommend",
                    )
                else:
                    llm_response = await generate_response(
                        context=res,
                        user_message=user_message or "상품 추천을 알려주세요.",
                        intent="recommend",
                    )
                state.final_response = apply_guards({
                    "response": llm_response,
                    "data": res,
                })
            except Exception as e:
                logger.warning(f"LLM 응답 생성 실패, 템플릿 응답 사용: {e}")
                template_response = _format_template_response(res, "recommend", state.sub_intent)
                state.final_response = apply_guards({"response": template_response, "data": res})
        else:
            template_response = _format_template_response(res, "recommend", state.sub_intent)
            state.final_response = apply_guards({"response": template_response, "data": res})

        return state

    state.final_response = apply_guards({"error": f"unknown intent: {state.intent}"})
    return state
