from __future__ import annotations
"""Gradio UI (대화형 데모).

기능
- 메시지 → 의도 분류 → 오케스트레이터 → 응답 요약 렌더
- 우측 패널에 원본 JSON 응답 표시
"""

import asyncio
import json
from typing import Any, Dict, List, Tuple

import gradio as gr

from src.agents.nodes.intent_classifier import classify_intent_async
from src.agents.state import AgentState
from src.agents.orchestrator import run as orchestrate


async def handle_message(user_id: str, message: str) -> Dict[str, Any]:
    result = await classify_intent_async(message)
    intent, sub_intent, payload = result.intent, result.sub_intent, result.payload
    if intent == "unknown":
        intent = "policy"
        payload = {"query": message, "top_k": 5}
    if intent == "order" and sub_intent in {"status", "detail", "cancel"} and not payload.get("order_id"):
        return {"need": "order_id", "message": "주문번호(ORD-...)를 포함해 주세요."}
    state = AgentState(user_id=user_id, intent=intent, sub_intent=sub_intent, payload=payload)
    state = await orchestrate(state)
    return state.final_response or {}


async def chat_fn(user_id: str, message: str, history: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], str]:
    if not user_id.strip():
        user_id = "user_001"
    if not message.strip():
        return history, ""

    res = await handle_message(user_id, message)

    if "orders" in res:
        orders = res["orders"]
        lines = ["주문 목록:"] + [f"- {o.get('order_id')} | {o.get('status')} | {o.get('order_date')}" for o in orders]
        # 최근 구매 아이템 요약이 있으면 함께 표시
        if res.get("recent_items"):
            items = res["recent_items"]
            lines += ["", "최근 구매한 상품:"] + [f"  · {it.get('title')} x{it.get('quantity')}" for it in items]
        reply = "\n".join(lines)
    elif "detail" in res:
        od = res["detail"]["order"]
        items = res["detail"].get("items", [])
        lines = [f"주문 상세: {od.get('order_id')} ({od.get('status')})"] + [f"  · {it.get('title')} x{it.get('quantity')}" for it in items]
        reply = "\n".join(lines)
    elif "status" in res:
        st = res["status"]
        reply = f"주문 상태: {st.get('status')} | 예정 배송: {st.get('estimated_delivery')}"
    elif "cancel_result" in res:
        cr = res["cancel_result"]
        ok = cr.get("ok")
        reply = "취소 완료" if ok else f"취소 불가: {cr.get('error')}"
    elif "ticket" in res:
        t = res["ticket"]
        reply = f"티켓: {t.get('ticket_id')} | 상태: {t.get('status')}"
    elif "hits" in res and "query" in res:
        hits = res["hits"]
        lines = [f"정책 검색 결과: {len(hits)}건"] + [f"- {h.get('metadata',{}).get('title','')} ({h.get('metadata',{}).get('doc_type','')})" for h in hits[:5]]
        reply = "\n".join(lines)
    elif res.get("need") == "order_id":
        reply = res.get("message", "주문번호가 필요합니다.")
    elif res.get("error"):
        reply = f"에러: {res.get('error')}"
    else:
        reply = json.dumps(res, ensure_ascii=False, indent=2)

    history = history + [(message, reply)]
    return history, json.dumps(res, ensure_ascii=False, indent=2)


with gr.Blocks(title="Ecommerce Agent (PoC)") as demo:
    gr.Markdown("""
    # 🛒 Ecommerce Agent (PoC)
    CSV 기반 Mock + 정책 검색 통합 데모
    """)
    with gr.Row():
        with gr.Column(scale=2):
            user_id = gr.Textbox(label="User ID", value="user_001")
            chat = gr.Chatbot(label="대화")
            msg = gr.Textbox(label="메시지", placeholder="예) 주문 상태 알려줘 ORD-... 또는 환불 정책 알려줘")
            with gr.Row():
                send = gr.Button("보내기", variant="primary")
                clear = gr.Button("초기화")

            gr.Markdown("""
            ### 🧭 빠른 액션
            최근 주문 불러오기 후, 주문 선택 → 상세/상태/취소/티켓 생성 버튼을 사용하세요.
            """)

            with gr.Row():
                btn_list = gr.Button("최근 주문 불러오기")
                order_select = gr.Dropdown(choices=[], label="주문 선택", interactive=True)
            with gr.Row():
                btn_detail = gr.Button("상세")
                btn_status = gr.Button("상태")
                btn_cancel = gr.Button("취소")
                btn_ticket = gr.Button("티켓 생성")
            with gr.Row():
                cancel_reason = gr.Textbox(label="취소 사유", value="UI 요청")
                ticket_desc = gr.Textbox(label="티켓 설명", value="UI 생성")

            gr.Markdown("""
            ### 📜 정책 검색
            """)
            with gr.Row():
                policy_q = gr.Textbox(label="질의", placeholder="예) 환불 정책, 배송 지연 보상")
                btn_policy = gr.Button("검색")
            with gr.Row():
                hits_select = gr.Dropdown(choices=[], label="결과 선택", interactive=True)
            hit_text = gr.Textbox(label="선택 결과 내용", lines=10)
        with gr.Column(scale=1):
            res_json = gr.Code(label="원본 응답(JSON)")

    async def on_send(m, h, uid):
        return await chat_fn(uid, m, h)

    send.click(on_send, inputs=[msg, chat, user_id], outputs=[chat, res_json])
    msg.submit(on_send, inputs=[msg, chat, user_id], outputs=[chat, res_json])
    clear.click(lambda: ([], ""), outputs=[chat, res_json])

    # 액션 핸들러
    async def do_list_orders(uid, h):
        s = AgentState(user_id=uid or "user_001", intent="order", sub_intent="list", payload={"limit": 5})
        s = await orchestrate(s)
        res = s.final_response or {}
        orders = res.get("orders", [])
        lines = ["주문 목록:"] + [f"- {o.get('order_id')} | {o.get('status')} | {o.get('order_date')}" for o in orders]
        reply = "\n".join(lines)
        h = h + [("/주문 목록", reply)]
        return h, json.dumps(res, ensure_ascii=False, indent=2), [o.get("order_id") for o in orders]

    async def do_order_action(uid, oid, action, reason=None, desc=None):
        if not oid:
            return {"error": "주문을 선택하세요."}
        if action == "detail":
            s = AgentState(user_id=uid or "user_001", intent="order", sub_intent="detail", payload={"order_id": oid})
        elif action == "status":
            s = AgentState(user_id=uid or "user_001", intent="order", sub_intent="status", payload={"order_id": oid})
        elif action == "cancel":
            s = AgentState(user_id=uid or "user_001", intent="order", sub_intent="cancel", payload={"order_id": oid, "reason": reason or "UI 요청"})
        else:
            return {"error": "알 수 없는 액션"}
        s = await orchestrate(s)
        return s.final_response or {}

    async def on_detail(uid, oid, h):
        res = await do_order_action(uid, oid, "detail")
        if "detail" in res:
            od = res["detail"]["order"]
            items = res["detail"].get("items", [])
            lines = [f"주문 상세: {od.get('order_id')} ({od.get('status')})"] + [f"  · {it.get('title')} x{it.get('quantity')}" for it in items]
            reply = "\n".join(lines)
        else:
            reply = json.dumps(res, ensure_ascii=False, indent=2)
        return h + [("/상세", reply)], json.dumps(res, ensure_ascii=False, indent=2)

    async def on_status(uid, oid, h):
        res = await do_order_action(uid, oid, "status")
        if "status" in res:
            st = res["status"]
            reply = f"주문 상태: {st.get('status')} | 예정 배송: {st.get('estimated_delivery')}"
        else:
            reply = json.dumps(res, ensure_ascii=False, indent=2)
        return h + [("/상태", reply)], json.dumps(res, ensure_ascii=False, indent=2)

    async def on_cancel(uid, oid, reason, h):
        res = await do_order_action(uid, oid, "cancel", reason=reason)
        if "cancel_result" in res:
            cr = res["cancel_result"]
            reply = "취소 완료" if cr.get("ok") else f"취소 불가: {cr.get('error')}"
        else:
            reply = json.dumps(res, ensure_ascii=False, indent=2)
        return h + [("/취소", reply)], json.dumps(res, ensure_ascii=False, indent=2)

    async def on_ticket(uid, oid, desc, h):
        if not oid:
            res = {"error": "주문을 선택하세요."}
        else:
            s = AgentState(user_id=uid or "user_001", intent="claim", payload={"action": "create", "order_id": oid, "issue_type": "refund", "description": desc or "UI 생성"})
            s = await orchestrate(s)
            res = s.final_response or {}
        if "ticket" in res:
            t = res["ticket"]
            reply = f"티켓 생성: {t.get('ticket_id')}"
        else:
            reply = json.dumps(res, ensure_ascii=False, indent=2)
        return h + [("/티켓", reply)], json.dumps(res, ensure_ascii=False, indent=2)

    hits_state = gr.State([])

    async def on_policy(uid, q, h):
        if not q.strip():
            return h, "", None, [], ""
        s = AgentState(user_id=uid or "user_001", intent="policy", payload={"query": q, "top_k": 5})
        s = await orchestrate(s)
        res = s.final_response or {}
        if "hits" in res:
            hits = res["hits"]
            lines = [f"정책 검색 결과: {len(hits)}건"] + [f"- {h.get('metadata',{}).get('title','')} ({h.get('metadata',{}).get('doc_type','')})" for h in hits[:5]]
            reply = "\n".join(lines)
            choices = [f"{i+1}. {h.get('metadata',{}).get('title','') or h.get('id')}" for i, h in enumerate(hits)]
            return h + [("/정책", reply)], json.dumps(res, ensure_ascii=False, indent=2), hits, choices, ""
        else:
            reply = json.dumps(res, ensure_ascii=False, indent=2)
        return h + [("/정책", reply)], json.dumps(res, ensure_ascii=False, indent=2), [], [], ""

    def on_hit_select(hits, label):
        if not hits or not label:
            return ""
        try:
            idx = int(label.split(".")[0]) - 1
        except Exception:
            return ""
        if idx < 0 or idx >= len(hits):
            return ""
        return hits[idx].get("text", "")

    btn_list.click(do_list_orders, inputs=[user_id, chat], outputs=[chat, res_json, order_select])
    btn_detail.click(on_detail, inputs=[user_id, order_select, chat], outputs=[chat, res_json])
    btn_status.click(on_status, inputs=[user_id, order_select, chat], outputs=[chat, res_json])
    btn_cancel.click(on_cancel, inputs=[user_id, order_select, cancel_reason, chat], outputs=[chat, res_json])
    btn_ticket.click(on_ticket, inputs=[user_id, order_select, ticket_desc, chat], outputs=[chat, res_json])

    btn_policy.click(on_policy, inputs=[user_id, policy_q, chat], outputs=[chat, res_json, hits_state, hits_select, hit_text])
    hits_select.change(on_hit_select, inputs=[hits_state, hits_select], outputs=[hit_text])


if __name__ == "__main__":
    import os
    try:
        from src.config import get_config
        cfg = get_config().app
        default_host = cfg.host
        default_port = cfg.ui_port
    except Exception:
        default_host = "0.0.0.0"
        default_port = 7860
    host = os.environ.get("UI_HOST", default_host)
    try:
        port = int(os.environ.get("UI_PORT", str(default_port)))
    except ValueError:
        port = default_port
    demo.queue().launch(server_name=host, server_port=port)
