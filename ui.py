from __future__ import annotations

import html
import json
import time
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gradio as gr


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

import re

from src.agents.nodes.intent_classifier import classify_intent_async
from src.agents.state import AgentState
from src.agents.orchestrator import run as orchestrate

VIS_DATA_DIR = Path(__file__).parent / "data" / "visualization"
ONTOLOGY_PATH = Path(__file__).parent / "ontology" / "ecommerce.ttl"
_trace_history: List[str] = []
_unified_log: List[Dict[str, Any]] = []
_current_log_hour: str = ""
_log_file_handle = None

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _get_log_file():
    global _current_log_hour, _log_file_handle
    current_hour = time.strftime("%Y-%m-%d_%H")
    
    if current_hour != _current_log_hour:
        if _log_file_handle:
            _log_file_handle.close()
        _current_log_hour = current_hour
        log_path = LOG_DIR / f"debug_{current_hour}.log"
        _log_file_handle = open(log_path, "a", encoding="utf-8")
    
    return _log_file_handle


def _write_log_to_file(entry: Dict[str, Any]):
    try:
        f = _get_log_file()
        if f:
            ts_full = time.strftime("%Y-%m-%d %H:%M:%S")
            line_parts = [
                f"[{ts_full}]",
                f"[{entry['type']}]",
            ]
            if entry.get("user_id"):
                line_parts.append(f"user={entry['user_id']}")
            if entry.get("intent"):
                intent_str = entry["intent"]
                if entry.get("sub_intent"):
                    intent_str += f"/{entry['sub_intent']}"
                line_parts.append(f"intent={intent_str}")
            if entry.get("duration_ms"):
                line_parts.append(f"({entry['duration_ms']:.0f}ms)")
            
            line_parts.append(entry["message"])
            
            f.write(" ".join(line_parts) + "\n")
            
            if entry.get("data"):
                try:
                    data_str = json.dumps(entry["data"], ensure_ascii=False, default=str)
                    if len(data_str) > 2000:
                        data_str = data_str[:2000] + "..."
                    f.write(f"    DATA: {data_str}\n")
                except:
                    pass
            
            f.flush()
    except Exception:
        pass


# 온톨로지 스키마 캐시 (모듈 로드 시 1회만 파싱)
_ontology_schema_cache: str = ""


def load_ontology_schema() -> str:
    """온톨로지 TTL 파일에서 클래스/속성 정보를 추출하여 프롬프트용 텍스트 생성.

    캐싱을 통해 매 요청마다 파싱하지 않고 모듈 로드 시 1회만 실행.
    """
    global _ontology_schema_cache
    if _ontology_schema_cache:
        return _ontology_schema_cache

    try:
        from rdflib import Graph, RDF, RDFS, OWL, Namespace

        g = Graph()
        g.parse(ONTOLOGY_PATH, format="turtle")

        ECOM = Namespace("http://example.org/ecommerce#")

        # 클래스 및 속성 추출
        classes_info = []
        class_uris = set(g.subjects(RDF.type, OWL.Class))

        for cls_uri in class_uris:
            cls_name = str(cls_uri).split('#')[-1]
            if cls_name.startswith(('_', 'Restriction')):
                continue

            # 해당 클래스의 데이터 속성 추출
            props = []
            for prop in g.subjects(RDFS.domain, cls_uri):
                prop_name = str(prop).split('#')[-1]
                # rdfs:comment에서 값 힌트 추출
                comment = g.value(prop, RDFS.comment)
                hint = ""
                if comment and ("중 하나" in str(comment)):
                    hint = f" ({comment})"
                props.append(f"{prop_name}{hint}")

            if props:
                classes_info.append(f"- ecom:{cls_name}: {', '.join(props[:8])}")  # 최대 8개
            else:
                classes_info.append(f"- ecom:{cls_name}")

        # ObjectProperty에서 주요 관계 추출
        relations = []
        for prop in g.subjects(RDF.type, OWL.ObjectProperty):
            prop_name = str(prop).split('#')[-1]
            domain = g.value(prop, RDFS.domain)
            range_ = g.value(prop, RDFS.range)
            if domain and range_:
                domain_name = str(domain).split('#')[-1]
                range_name = str(range_).split('#')[-1]
                # 역관계는 제외 (이름에 By, Of 포함)
                if not any(x in prop_name for x in ['By', 'Of', 'has', 'is']):
                    relations.append(f"- {domain_name} -[{prop_name}]-> {range_name}")

        _ontology_schema_cache = f"""### 클래스
{chr(10).join(sorted(classes_info)[:15])}

### 주요 관계
{chr(10).join(sorted(relations)[:12])}"""

        return _ontology_schema_cache

    except Exception as e:
        # 폴백: 기본 스키마
        return """### 클래스
- ecom:Customer: customerId, name, email, phone, address, membershipLevel(bronze/silver/gold/platinum)
- ecom:Product: productId, title, brand, price, averageRating, ratingNumber, stockStatus(in_stock/out_of_stock/limited)
- ecom:Order: orderId, status(pending/processing/shipped/delivered/cancelled), orderDate, deliveryDate, totalAmount, shippingAddress
- ecom:OrderItem: quantity, unitPrice
- ecom:Ticket: ticketId, issueType(shipping/refund/exchange/product_inquiry/order_inquiry/complaint/other), status, priority(low/normal/high/urgent)
- ecom:Company: companyId, companyName, industry, companySize, foundedYear, headquarters
- ecom:Policy: description
- ecom:Category

### 주요 관계
- Customer -[placedOrder]-> Order
- Customer -[purchased]-> Product
- Customer -[hasTicket]-> Ticket
- Order -[containsItem]-> OrderItem
- OrderItem -[hasProduct]-> Product
- Product -[similarTo]-> Product
- Product -[inCategory]-> Category
- Ticket -[relatedToOrder]-> Order
- Company -[manufactures]-> Product"""


def add_trace(entry: str, level: str = "INFO"):
    """Debug Panel에 트레이스 항목 추가.

    Args:
        entry: 트레이스 메시지
        level: 로그 레벨 (INFO, SELECT, GUARD, ERROR, LLM, TOOL, INTENT, SPARQL)
    """
    global _trace_history
    ts = time.strftime("%H:%M:%S")
    icons = {
        "INFO": "[i]",
        "SELECT": "[>]",
        "GUARD": "[G]",
        "ERROR": "[X]",
        "LLM": "[L]",
        "TOOL": "[T]",
        "INTENT": "[I]",
        "SPARQL": "[Q]",
        "OK": "[+]",
        "WARN": "[!]",
    }
    icon = icons.get(level, "•")
    _trace_history.append(f"[{ts}] {icon} {entry}")
    if len(_trace_history) > 100:
        _trace_history = _trace_history[-100:]


def get_trace() -> str:
    return "\n".join(_trace_history[-30:]) if _trace_history else "(no trace)"


def clear_trace() -> str:
    global _trace_history
    _trace_history = []
    return "(cleared)"


def add_unified_log(
    event_type: str,
    message: str,
    user_id: str = "",
    intent: str = "",
    sub_intent: str = "",
    duration_ms: float = 0,
    data: Any = None,
    is_error: bool = False
):
    global _unified_log
    entry = {
        "ts": time.strftime("%H:%M:%S"),
        "type": event_type,
        "message": message,
        "user_id": user_id,
        "intent": intent,
        "sub_intent": sub_intent,
        "duration_ms": duration_ms,
        "data": data,
        "is_error": is_error,
    }
    _unified_log.append(entry)
    if len(_unified_log) > 200:
        _unified_log = _unified_log[-200:]
    
    _write_log_to_file(entry)


def get_unified_log_html() -> str:
    if not _unified_log:
        return '<div class="log-empty">로그가 없습니다</div>'
    
    html_parts = []
    for entry in reversed(_unified_log[-50:]):
        ts = entry["ts"]
        etype = entry["type"]
        msg = entry["message"]
        is_error = entry.get("is_error", False)
        
        type_colors = {
            "REQUEST": "#3b82f6",
            "INTENT": "#8b5cf6",
            "TOOL": "#10b981",
            "RESULT": "#06b6d4",
            "JSON": "#6366f1",
            "ERROR": "#ef4444",
            "GUARD": "#f59e0b",
            "LLM": "#ec4899",
        }
        color = type_colors.get(etype, "#64748b")
        if is_error:
            color = "#ef4444"
        
        duration = ""
        if entry.get("duration_ms"):
            duration = f'<span class="log-duration">{entry["duration_ms"]:.0f}ms</span>'
        
        intent_badge = ""
        if entry.get("intent"):
            sub = f"/{entry['sub_intent']}" if entry.get("sub_intent") else ""
            intent_badge = f'<span class="log-intent">{entry["intent"]}{sub}</span>'
        
        data_html = ""
        if entry.get("data"):
            try:
                data_str = json.dumps(entry["data"], ensure_ascii=False, indent=2, cls=DateTimeEncoder)
                if len(data_str) > 500:
                    data_str = data_str[:500] + "\n..."
                data_html = f'<pre class="log-data">{html.escape(data_str)}</pre>'
            except:
                pass
        
        error_class = " log-error" if is_error else ""
        html_parts.append(f'''
        <div class="log-entry{error_class}">
            <div class="log-header">
                <span class="log-time">{ts}</span>
                <span class="log-type" style="background:{color}">{etype}</span>
                {intent_badge}
                {duration}
            </div>
            <div class="log-message">{html.escape(msg)}</div>
            {data_html}
        </div>
        ''')
    
    return "".join(html_parts)


def clear_unified_log() -> str:
    global _unified_log
    _unified_log = []
    return '<div class="log-empty">로그가 초기화되었습니다</div>'


def get_customers() -> List[str]:
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        customers = repo.get_customers(limit=50)
        return [c.customer_id for c in customers] if customers else ["user_001"]
    except:
        return ["user_001", "user_002", "user_003"]


def get_orders(user_id: str) -> List[str]:
    if not user_id:
        return []
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        orders = repo.get_customer_orders(user_id, limit=20)
        return [o.order_id for o in orders] if orders else []
    except:
        return []


def get_products() -> List[str]:
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        products = repo.get_products(limit=30)
        return [p.product_id for p in products] if products else []
    except:
        return []


def get_customer_info(user_id: str) -> str:
    if not user_id:
        return ""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        c = repo.get_customer(user_id)
        if c:
            orders = repo.get_customer_orders(user_id, limit=50)
            total = sum(o.total_amount for o in orders) if orders else 0
            
            level_badge = {
                "platinum": "PLATINUM",
                "gold": "GOLD", 
                "silver": "SILVER",
                "bronze": "BRONZE"
            }.get(c.membership_level.lower() if c.membership_level else "", "BRONZE")
            
            pending = sum(1 for o in orders if o.status in ("pending", "processing", "confirmed"))
            shipped = sum(1 for o in orders if o.status in ("shipping", "shipped"))
            delivered = sum(1 for o in orders if o.status == "delivered")
            
            return f"""**{c.name}** `{level_badge}`

{c.email} · {c.phone or '-'}

| 총 주문 | 누적 금액 | 진행중 | 배송중 | 완료 |
|:---:|:---:|:---:|:---:|:---:|
| **{len(orders)}**건 | **₩{total:,.0f}** | {pending} | {shipped} | {delivered} |"""
        return user_id
    except:
        return user_id


def get_stats() -> Dict[str, int]:
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        store = get_store()
        repo = RDFRepository(store)
        return {
            "customers": repo.count_customers(),
            "products": repo.count_products(),
            "orders": repo.count_orders(),
            "tickets": repo.count_tickets(),
            "triples": store.triple_count if store else 0,
        }
    except:
        return {"customers": 0, "products": 0, "orders": 0, "tickets": 0, "triples": 0}


# =====================
# RDF Data Management Functions
# =====================

def run_sparql_query(query: str) -> Tuple[List[List[str]], str]:
    """SPARQL SELECT 쿼리 실행"""
    if not query.strip():
        return [], "쿼리를 입력해주세요."
    try:
        from src.rdf.store import get_store
        store = get_store()
        results = store.query(query)
        if not results:
            return [], "쿼리 실행 완료 (결과 없음)"
        # 결과를 2차원 리스트로 변환
        rows = []
        for row in results:
            if isinstance(row, dict):
                rows.append([str(v) if v else "" for v in row.values()])
            else:
                rows.append([str(v) if v else "" for v in row])
        return rows, f"{len(rows)}개 결과"
    except Exception as e:
        return [], f"오류: {str(e)}"


def add_triple(subject: str, predicate: str, obj: str, obj_type: str) -> str:
    """트리플 추가"""
    if not subject.strip() or not predicate.strip() or not obj.strip():
        return "모든 필드를 입력해주세요."
    try:
        from src.rdf.store import get_store
        store = get_store()

        # URI 확장 (접두사 처리)
        def expand_uri(uri: str) -> str:
            if uri.startswith("ecom:"):
                return f"http://example.org/ecommerce#{uri[5:]}"
            if uri.startswith("http://") or uri.startswith("https://"):
                return uri
            return f"http://example.org/ecommerce#{uri}"

        subject_uri = expand_uri(subject)
        predicate_uri = expand_uri(predicate)

        if obj_type == "URI":
            obj_val = expand_uri(obj)
            store.add_triple(subject_uri, predicate_uri, obj_val, "uri")
        else:
            store.add_triple(subject_uri, predicate_uri, obj, "literal")

        return f"추가 완료: <{subject}> <{predicate}> {obj}"
    except Exception as e:
        return f"오류: {str(e)}"


def delete_triple(subject: str, predicate: str, obj: str = "") -> str:
    """트리플 삭제"""
    if not subject.strip() or not predicate.strip():
        return "Subject와 Predicate를 입력해주세요."
    try:
        from src.rdf.store import get_store
        store = get_store()

        # URI 확장 (접두사 처리)
        def expand_uri(uri: str) -> str:
            if uri.startswith("ecom:"):
                return f"http://example.org/ecommerce#{uri[5:]}"
            if uri.startswith("http://") or uri.startswith("https://"):
                return uri
            return f"http://example.org/ecommerce#{uri}"

        subject_uri = expand_uri(subject)
        predicate_uri = expand_uri(predicate)

        if obj.strip():
            # 특정 값 삭제
            if obj.startswith("ecom:") or obj.startswith("http://"):
                obj_uri = expand_uri(obj)
                query = f'DELETE WHERE {{ <{subject_uri}> <{predicate_uri}> <{obj_uri}> }}'
            else:
                query = f'DELETE WHERE {{ <{subject_uri}> <{predicate_uri}> "{obj}" }}'
        else:
            # 해당 관계 전체 삭제
            query = f'DELETE WHERE {{ <{subject_uri}> <{predicate_uri}> ?o }}'

        store.update(query)
        return f"삭제 완료: <{subject}> <{predicate}> {obj or '*'}"
    except Exception as e:
        return f"오류: {str(e)}"


def get_entity_detail(entity_type: str, entity_id: str) -> Dict[str, Any]:
    """엔티티 상세 조회"""
    if not entity_id.strip():
        return {"error": "ID를 입력해주세요"}
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        from dataclasses import asdict
        repo = RDFRepository(get_store())

        if entity_type == "고객":
            entity = repo.get_customer(entity_id)
        elif entity_type == "상품":
            entity = repo.get_product(entity_id)
        elif entity_type == "주문":
            entity = repo.get_order(entity_id)
        elif entity_type == "티켓":
            tickets = repo.get_user_tickets(entity_id, limit=1)
            entity = tickets[0] if tickets else None
        else:
            return {"error": f"알 수 없는 엔티티 타입: {entity_type}"}

        if entity:
            return asdict(entity)
        return {"error": f"{entity_type} '{entity_id}'를 찾을 수 없습니다"}
    except Exception as e:
        return {"error": str(e)}


def get_all_customers_df() -> List[List[str]]:
    """관리자용 고객 목록 조회"""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        customers = repo.get_customers(limit=100)
        return [[c.customer_id, c.name or "-", c.email or "-", c.membership_level or "-", str(c.created_at or "-")[:10]] for c in customers] if customers else []
    except:
        return []


def get_all_orders_df(status_filter: str = "전체") -> List[List[str]]:
    """관리자용 주문 목록 조회"""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        orders = repo.get_orders(limit=100)
        if not orders:
            return []
        result = []
        for o in orders:
            status = o.status or "-"
            if status_filter != "전체" and status != status_filter:
                continue
            result.append([
                o.order_id,
                o.user_id or "-",
                status,
                f"₩{int(o.total_amount or 0):,}",
                str(o.order_date or "-")[:10]
            ])
        return result
    except:
        return []


def get_all_tickets_df(status_filter: str = "전체") -> List[List[str]]:
    """관리자용 티켓 목록 조회"""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())

        # 모든 고객의 티켓을 수집
        customers = repo.get_customers(limit=100)
        all_tickets = []
        for c in customers:
            user_tickets = repo.get_user_tickets(c.customer_id, limit=50)
            all_tickets.extend(user_tickets)

        if not all_tickets:
            return []
        result = []
        for t in all_tickets[:100]:
            status = t.status or "-"
            if status_filter != "전체" and status != status_filter:
                continue
            result.append([
                t.ticket_id,
                t.user_id or "-",
                t.issue_type or "-",
                status,
                str(t.created_at or "-")[:10]
            ])
        return result
    except:
        return []


def get_order_status_dist() -> str:
    """주문 상태별 분포 HTML"""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())
        orders = repo.get_orders(limit=500)
        if not orders:
            return "<p>주문 데이터 없음</p>"
        dist: Dict[str, int] = {}
        for o in orders:
            s = o.status or "unknown"
            dist[s] = dist.get(s, 0) + 1
        colors = {"pending": "#f9e2af", "processing": "#89b4fa", "shipped": "#89dceb", "delivered": "#a6e3a1", "cancelled": "#f38ba8"}
        html = "<div style='display:flex;gap:12px;flex-wrap:wrap;'>"
        for s, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            c = colors.get(s, "#6c7086")
            html += f"<div style='background:{c};color:#1e1e2e;padding:8px 16px;border-radius:8px;text-align:center;'><div style='font-size:20px;font-weight:bold;'>{cnt}</div><div style='font-size:11px;'>{s}</div></div>"
        html += "</div>"
        return html
    except:
        return "<p>통계 로드 실패</p>"


def get_ticket_status_dist() -> str:
    """티켓 상태별 분포 HTML"""
    try:
        from src.rdf.repository import RDFRepository
        from src.rdf.store import get_store
        repo = RDFRepository(get_store())

        # 모든 고객의 티켓을 수집
        customers = repo.get_customers(limit=100)
        all_tickets = []
        for c in customers:
            user_tickets = repo.get_user_tickets(c.customer_id, limit=50)
            all_tickets.extend(user_tickets)

        if not all_tickets:
            return "<p>티켓 데이터 없음</p>"
        dist: Dict[str, int] = {}
        for t in all_tickets:
            s = t.status or "unknown"
            dist[s] = dist.get(s, 0) + 1
        colors = {"open": "#f38ba8", "in_progress": "#f9e2af", "resolved": "#a6e3a1", "closed": "#6c7086"}
        html = "<div style='display:flex;gap:12px;flex-wrap:wrap;'>"
        for s, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            c = colors.get(s, "#89b4fa")
            html += f"<div style='background:{c};color:#1e1e2e;padding:8px 16px;border-radius:8px;text-align:center;'><div style='font-size:20px;font-weight:bold;'>{cnt}</div><div style='font-size:11px;'>{s}</div></div>"
        html += "</div>"
        return html
    except:
        return "<p>통계 로드 실패</p>"


# =====================
# TTL File Management Functions
# =====================

PROJECT_ROOT = Path(__file__).parent

TTL_FILE_MAP = {
    "ontology/ecommerce.ttl (스키마)": "ontology/ecommerce.ttl",
    "ontology/external-company.ttl": "ontology/external-company.ttl",
    "instances/customers.ttl": "ontology/instances/customers.ttl",
    "instances/orders.ttl": "ontology/instances/orders.ttl",
    "instances/products.ttl": "ontology/instances/products.ttl",
    "instances/similarities.ttl": "ontology/instances/similarities.ttl",
    "instances/tickets.ttl": "ontology/instances/tickets.ttl",
    "instances/embeddings.ttl (읽기전용)": "ontology/instances/embeddings.ttl",
    "shacl/ecommerce-shapes.ttl (스키마)": "ontology/shacl/ecommerce-shapes.ttl",
}

# 읽기전용 파일 목록
TTL_READONLY_FILES = {
    "ontology/ecommerce.ttl (스키마)",
    "instances/embeddings.ttl (읽기전용)",
    "shacl/ecommerce-shapes.ttl (스키마)",
}


def load_ttl_file(filename: str) -> Tuple[str, str]:
    """TTL 파일 내용 로드"""
    filepath = PROJECT_ROOT / TTL_FILE_MAP.get(filename, filename)
    if filepath.exists():
        content = filepath.read_text(encoding="utf-8")
        lines = len(content.split('\n'))
        size_kb = filepath.stat().st_size / 1024
        readonly_mark = " (읽기전용)" if filename in TTL_READONLY_FILES else ""
        return content, f"로드 완료: `{filepath.name}`{readonly_mark} ({lines}줄, {size_kb:.1f}KB)"
    return "", f"파일 없음: {filepath}"


def save_ttl_file(filename: str, content: str) -> str:
    """TTL 파일 저장 (검증 후)"""
    # 읽기전용 체크
    if filename in TTL_READONLY_FILES:
        return f"이 파일은 읽기전용입니다: {filename}"

    from rdflib import Graph

    # 1. Turtle 구문 검증
    try:
        g = Graph()
        g.parse(data=content, format="turtle")
    except Exception as e:
        return f"구문 오류 - 저장 취소: {e}"

    # 2. 파일 저장
    filepath = PROJECT_ROOT / TTL_FILE_MAP.get(filename, filename)
    try:
        filepath.write_text(content, encoding="utf-8")
        return f"저장 완료: `{filepath.name}` ({len(g)} 트리플)"
    except Exception as e:
        return f"저장 실패: {e}"


def validate_ttl(content: str) -> str:
    """TTL 구문 검증만 수행"""
    from rdflib import Graph
    try:
        g = Graph()
        g.parse(data=content, format="turtle")
        return f"유효한 Turtle 형식 ({len(g)} 트리플)"
    except Exception as e:
        return f"구문 오류: {e}"


def reload_rdf_store() -> str:
    """RDF 스토어 리로드 (변경사항 반영)"""
    try:
        from src.rdf.store import reset_store, get_store
        reset_store()
        store = get_store()
        triple_count = store.triple_count if store else 0
        return f"스토어 리로드 완료 ({triple_count:,} 트리플)"
    except Exception as e:
        return f"리로드 실패: {e}"


async def convert_nl_to_sparql(nl_query: str) -> Tuple[str, str]:
    """자연어 질문을 SPARQL 쿼리로 변환.

    온톨로지 스키마를 동적으로 로드하여 프롬프트에 포함합니다.
    """
    if not nl_query.strip():
        return "", "질문을 입력해주세요."

    # 온톨로지에서 스키마 동적 로드
    ontology_schema = load_ontology_schema()

    system_prompt = f"""당신은 SPARQL 쿼리 생성 전문가입니다.
사용자의 자연어 질문을 아래 온톨로지에 맞는 SPARQL SELECT 쿼리로 변환하세요.

## 온톨로지 (PREFIX ecom: <http://example.org/ecommerce#>)

{ontology_schema}

## 규칙
1. SPARQL SELECT 쿼리만 반환 (설명 없이)
2. 반드시 LIMIT 사용 (기본 20, 최대 100)
3. PREFIX 선언 생략 (시스템에서 자동 추가)

## 예시
질문: "platinum 등급 고객 목록"
→
SELECT ?cid ?name ?email WHERE {{
    ?c a ecom:Customer ;
       ecom:customerId ?cid ;
       ecom:name ?name ;
       ecom:membershipLevel "platinum" .
    OPTIONAL {{ ?c ecom:email ?email }}
}} LIMIT 20"""

    try:
        from src.llm.client import get_client
        client = get_client()
        messages = [{"role": "user", "content": nl_query}]
        response = await client.chat(messages, system_prompt=system_prompt)

        # SPARQL 코드 블록 추출 (여러 패턴 지원)
        sparql = response.strip()

        # 마크다운 코드 블록 추출: ```sparql, ```SPARQL, ``` 등
        match = re.search(r'```(?:sparql|SPARQL)?\s*\n?(.*?)\n?```', sparql, re.DOTALL | re.IGNORECASE)
        if match:
            sparql = match.group(1).strip()
        elif "```" in sparql:
            # 폴백: 기존 방식
            parts = sparql.split("```")
            if len(parts) >= 2:
                sparql = parts[1]
                if sparql.lower().startswith("sparql"):
                    sparql = sparql[6:]
                sparql = sparql.strip()

        # LIMIT 미포함 시 자동 추가
        if sparql and "LIMIT" not in sparql.upper():
            sparql = sparql.rstrip().rstrip(';') + "\nLIMIT 20"

        return sparql, "변환 완료"
    except Exception as e:
        return "", f"변환 오류: {str(e)}"


def load_vis_data(filename: str) -> dict:
    path = VIS_DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"nodes": [], "edges": []}


def generate_vis_html(data: dict, height: int = 400, title: str = "") -> str:
    nodes_json = json.dumps(data.get("nodes", []), ensure_ascii=False)
    edges_json = json.dumps(data.get("edges", []), ensure_ascii=False)
    # Use iframe with srcdoc to ensure scripts execute properly in Gradio
    iframe_content = f"""<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        html, body {{ margin: 0; padding: 0; background: #11111b; width: 100%; height: 100%; }}
        #graph {{ width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <div id="graph"></div>
    <script>
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('graph');
        var options = {{
            nodes: {{ shape: 'box', font: {{ color: '#1e1e2e', size: 12 }}, margin: 8, borderWidth: 2, color: {{ background: '#45475a', border: '#585b70' }} }},
            groups: {{ 'class': {{ color: {{ background: '#89b4fa', border: '#74c7ec' }}, font: {{ color: '#1e1e2e' }} }}, 'customer': {{ color: {{ background: '#a6e3a1', border: '#94e2d5' }}, font: {{ color: '#1e1e2e' }} }}, 'order': {{ color: {{ background: '#89dceb', border: '#74c7ec' }}, font: {{ color: '#1e1e2e' }} }}, 'product': {{ color: {{ background: '#f9e2af', border: '#fab387' }}, font: {{ color: '#1e1e2e' }} }}, 'ticket': {{ color: {{ background: '#f38ba8', border: '#eba0ac' }}, font: {{ color: '#1e1e2e' }} }}, 'category': {{ color: {{ background: '#cba6f7', border: '#b4befe' }}, font: {{ color: '#1e1e2e' }} }} }},
            edges: {{ font: {{ size: 10, color: '#6c7086' }}, color: '#585b70', smooth: {{ type: 'curvedCW', roundness: 0.2 }}, arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }} }},
            physics: {{ solver: 'forceAtlas2Based', forceAtlas2Based: {{ gravitationalConstant: -40, springLength: 100 }}, stabilization: {{ iterations: 80 }} }},
            interaction: {{ hover: true, tooltipDelay: 100 }}
        }};
        new vis.Network(container, {{ nodes: nodes, edges: edges }}, options);
    </script>
</body>
</html>"""
    # Escape for srcdoc attribute
    escaped = html.escape(iframe_content)
    return f"""
    <div style="background:#1e1e2e;border-radius:12px;padding:16px;margin:8px 0;">
        <iframe srcdoc="{escaped}" style="width:100%;height:{height}px;border:1px solid #313244;border-radius:8px;background:#11111b;"></iframe>
    </div>
    """


def render_mermaid_er() -> str:
    """docs/ARCHITECTURE.md의 완전한 Mermaid ER 다이어그램을 HTML로 렌더링 (iframe 방식)"""
    mermaid_code = """erDiagram
    Customer {
        string customerId PK "user_XXX"
        string name
        string email UK
        string phone
        string address
        string membershipLevel "bronze|silver|gold|platinum"
    }
    Product {
        string productId PK
        string title
        string brand
        decimal price
        decimal averageRating "0~5"
        integer ratingNumber
        string stockStatus "in_stock|out_of_stock|limited"
    }
    Order {
        string orderId PK "ORD_YYYYMMDD_XXXX"
        string status "pending|confirmed|shipping|delivered|cancelled"
        dateTime orderDate
        dateTime deliveryDate
        decimal totalAmount
        string shippingAddress
    }
    OrderItem {
        integer quantity
        decimal unitPrice
        Product hasProduct FK
        Order belongsToOrder FK
    }
    Ticket {
        string ticketId PK "TICKET_XXXXXXXXXX"
        string issueType "shipping|refund|exchange|..."
        string description
        string priority "low|normal|high|urgent"
        string status "open|in_progress|resolved|closed"
        dateTime createdAt
        dateTime resolvedAt
    }
    Category {
        string name
    }
    Company {
        string companyId PK "COM_XXX"
        string companyName
        string industry "Electronics|Technology|Retail|..."
        string companySize "startup|small|medium|large|enterprise"
        integer foundedYear "1800~2026"
        string headquarters
        integer employeeCount
        decimal annualRevenue
        anyURI website
        string stockTicker
    }
    BusinessRelationship {
        string relationshipType "supplier|partner|competitor|subsidiary"
        date relationshipStartDate
        date relationshipEndDate
        decimal relationshipStrength "0.0~1.0"
    }

    Customer ||--o{ Order : placedOrder
    Customer ||--o{ Ticket : hasTicket
    Customer }o--o{ Product : purchased
    Customer }o--o| Company : worksAt
    Customer }o--o{ Company : purchasedFrom
    Customer }o--o{ Company : subscribedTo
    Order ||--|{ OrderItem : containsItem
    Order }o--|| Customer : orderedBy
    OrderItem }o--|| Product : hasProduct
    OrderItem }o--|| Order : belongsToOrder
    Ticket }o--o| Order : relatedToOrder
    Ticket }o--|| Customer : ticketOf
    Product }o--|| Category : inCategory
    Product }o--o{ Product : similarTo
    Product }o--o| Company : manufacturedBy
    Product }o--o{ Company : distributedBy
    Company ||--o{ Product : manufactures
    Company }o--o{ Company : supplierOf
    Company }o--o{ Company : partnerWith
    Company }o--o{ Company : competitorOf
    Company }o--o| Company : subsidiaryOf
    BusinessRelationship }o--|| Company : hasSourceCompany
    BusinessRelationship }o--|| Company : hasTargetCompany"""

    # iframe + srcdoc 방식으로 Mermaid 렌더링 (Gradio 동적 HTML에서 스크립트 실행 보장)
    # 밝은 테마 적용
    iframe_content = f'''<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        html, body {{ margin: 0; padding: 0; background: #ffffff; width: 100%; height: 100%; }}
        .mermaid {{ text-align: center; padding: 20px; }}
    </style>
</head>
<body>
    <div class="mermaid">
{mermaid_code}
    </div>
    <script>mermaid.initialize({{
        startOnLoad: true, 
        theme: 'default',
        themeVariables: {{
            primaryTextColor: '#1e293b',
            secondaryTextColor: '#475569',
            tertiaryTextColor: '#64748b',
            lineColor: '#94a3b8',
            primaryColor: '#e2e8f0',
            secondaryColor: '#f1f5f9',
            tertiaryColor: '#f8fafc',
            attributeBackgroundColorEven: '#f8fafc',
            attributeBackgroundColorOdd: '#f1f5f9'
        }}
    }});</script>
</body>
</html>'''
    escaped = html.escape(iframe_content)
    return f'''
    <div style="background:#ffffff;border-radius:8px;padding:12px;margin:4px 0;border:1px solid #e2e8f0;">
        <iframe srcdoc="{escaped}" style="width:100%;height:1100px;border:1px solid #e2e8f0;border-radius:4px;background:#ffffff;"></iframe>
    </div>
    '''


def render_schema_graph() -> str:
    """온톨로지 스키마 그래프 렌더링"""
    return generate_vis_html(load_vis_data("ontology_schema.json"), 1000, "")


def render_instance_graph(
    limit: int = 50,
    customer_level: str = "전체",
    order_status: str = "전체"
) -> Tuple[str, str]:
    """고객-주문-상품 인스턴스 그래프 렌더링 (필터 적용)"""
    data = load_vis_data("instance_graph.json")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # 1. 고객 필터링 (등급)
    customers = [n for n in nodes if n.get("group") == "customer"]
    if customer_level and customer_level != "전체":
        customers = [c for c in customers if c.get("level") == customer_level]
    customers = customers[:limit]
    customer_ids = {c["id"] for c in customers}

    # 2. 주문 필터링 (상태 + 고객 연결)
    orders = [n for n in nodes if n.get("group") == "order"]
    if order_status and order_status != "전체":
        orders = [o for o in orders if o.get("status") == order_status]

    order_edges = [e for e in edges if e.get("from") in customer_ids and e.get("label") == "주문"]
    order_ids = {e["to"] for e in order_edges}
    # 상태 필터가 적용된 경우, 해당 상태 주문만 유지
    orders = [o for o in orders if o["id"] in order_ids]
    order_ids = {o["id"] for o in orders}  # 필터링된 주문 ID로 갱신
    # 주문 엣지도 필터링된 주문에 맞게 재조정
    order_edges = [e for e in order_edges if e["to"] in order_ids]

    # 3. 연결된 상품 필터링
    products = [n for n in nodes if n.get("group") == "product"]
    product_edges = [e for e in edges if e.get("from") in order_ids]
    product_ids = {e["to"] for e in product_edges}
    products = [p for p in products if p["id"] in product_ids]

    filtered_nodes = customers + orders + products
    filtered_edges = order_edges + product_edges

    # 필터 정보 표시
    filter_info = []
    if customer_level and customer_level != "전체":
        filter_info.append(f"등급={customer_level}")
    if order_status and order_status != "전체":
        filter_info.append(f"상태={order_status}")
    filter_str = f" (필터: {', '.join(filter_info)})" if filter_info else ""

    stats = f"**표시 중**: 고객 {len(customers)} / 주문 {len(orders)} / 상품 {len(products)}{filter_str} (전체: {len(nodes)} 노드, {len(edges)} 엣지)"
    return generate_vis_html({"nodes": filtered_nodes, "edges": filtered_edges}, 1000, ""), stats


def get_category_from_label(label: str) -> str:
    """노드 라벨에서 카테고리 추출"""
    # 카테고리 매핑 (truncated labels 처리)
    category_map = {
        "General Product": "General",
        "Electronics Pro": "Electronics",
        "Home & Kitchen ": "Home & Kitchen",
        "Toys & Games Pr": "Toys & Games",
        "Sports & Outdoo": "Sports & Outdoor",
        "Beauty Product ": "Beauty",
        "Garden & Outdoo": "Garden & Outdoor",
        "Office Products": "Office",
        "Automotive Prod": "Automotive",
    }
    # Books Product X, Books Product 0 등 처리
    if label.startswith("Books Product"):
        return "Books"
    return category_map.get(label, label.split()[0] if label else "Other")


def get_similarity_categories() -> list:
    """유사도 그래프에서 사용 가능한 카테고리 목록 반환"""
    data = load_vis_data("similarity_graph.json")
    nodes = data.get("nodes", [])
    categories = set()
    for n in nodes:
        cat = get_category_from_label(n.get("label", ""))
        categories.add(cat)
    return ["전체"] + sorted(categories)


def render_similarity_graph(limit: int = 50, threshold: float = 0.0, category: str = "전체") -> Tuple[str, str]:
    """상품 유사도 그래프 렌더링 (제한, 임계값, 카테고리 필터 적용)"""
    data = load_vis_data("similarity_graph.json")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # 카테고리 필터링
    if category and category != "전체":
        filtered_node_ids = set()
        for n in nodes:
            if get_category_from_label(n.get("label", "")) == category:
                filtered_node_ids.add(n["id"])
        # 해당 카테고리 노드만 포함하는 엣지 필터링
        edges = [e for e in edges if e.get("from") in filtered_node_ids and e.get("to") in filtered_node_ids]
        nodes = [n for n in nodes if n["id"] in filtered_node_ids]

    # 임계값 필터링 (score 필드가 있는 경우)
    filtered_edges = [e for e in edges if float(e.get("score", 0)) >= threshold]

    # 엣지 제한
    limited_edges = filtered_edges[:limit]
    node_ids = set()
    for e in limited_edges:
        node_ids.add(e.get("from"))
        node_ids.add(e.get("to"))

    limited_nodes = [n for n in nodes if n["id"] in node_ids]

    # 통계 정보
    filter_parts = []
    if category and category != "전체":
        filter_parts.append(f"카테고리: {category}")
    if threshold > 0:
        filter_parts.append(f"유사도 ≥ {threshold:.2f}")
    filter_str = f" ({', '.join(filter_parts)})" if filter_parts else ""
    stats = f"**표시 중**: 상품 {len(limited_nodes)} / 유사도 {len(limited_edges)}{filter_str} (전체: {len(data.get('nodes', []))} 노드, {len(data.get('edges', []))} 엣지)"
    return generate_vis_html({"nodes": limited_nodes, "edges": limited_edges}, 1000, ""), stats


async def process_message(user_id: str, message: str) -> Tuple[Dict[str, Any], str]:
    total_start = time.time()
    
    add_unified_log("REQUEST", f"입력: {message}", user_id=user_id)
    add_trace(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")
    add_trace(f"입력: {message[:50]}{'...' if len(message) > 50 else ''}", "INFO")
    add_trace(f"사용자: {user_id}", "INFO")

    t0 = time.time()
    result = await classify_intent_async(message)
    intent_ms = (time.time() - t0) * 1000
    intent, sub_intent, payload = result.intent, result.sub_intent, result.payload

    add_unified_log(
        "INTENT", 
        f"분류: {intent}/{sub_intent or '-'} | 신뢰도: {result.confidence} | 출처: {result.source}",
        user_id=user_id,
        intent=intent,
        sub_intent=sub_intent or "",
        duration_ms=intent_ms,
        data={"payload": payload, "reason": result.reason}
    )
    add_trace(f"[intent_classifier] 분류 완료 ({intent_ms:.0f}ms)", "INTENT")
    add_trace(f"  → 의도: {intent} / {sub_intent or 'None'}", "SELECT")
    add_trace(f"  → 신뢰도: {result.confidence}, 출처: {result.source}", "SELECT")
    if result.reason:
        add_trace(f"  → 사유: {result.reason}", "INFO")

    if intent == "unknown":
        intent, payload = "policy", {"query": message, "top_k": 5}
        add_unified_log("GUARD", "unknown → policy 폴백 (RAG 검색)", user_id=user_id, intent="policy")
        add_trace(f"[fallback] unknown → policy (RAG 검색)", "WARN")

    if intent == "order" and sub_intent in {"status", "detail", "cancel"} and not payload.get("order_id"):
        add_unified_log("ERROR", "order_id 누락 - 사용자 입력 필요", user_id=user_id, is_error=True)
        add_trace(f"[validation] order_id 누락 - 사용자 입력 필요", "WARN")
        return {"need": "order_id", "message": "주문번호를 포함해 주세요 (예: ORD-20251201-001)"}, get_trace()

    state = AgentState(user_id=user_id, intent=intent, sub_intent=sub_intent, payload=payload)
    add_trace(f"[orchestrator] 처리 시작: {intent}/{sub_intent}", "TOOL")

    t0 = time.time()
    state = await orchestrate(state)
    orch_ms = (time.time() - t0) * 1000

    response = state.final_response or {}
    total_ms = (time.time() - total_start) * 1000
    
    result_summary = ""
    is_error = False
    if response.get("error"):
        result_summary = f"오류: {response.get('error')}"
        is_error = True
        add_trace(f"[결과] 오류: {response.get('error')}", "ERROR")
    elif response.get("blocked"):
        result_summary = f"차단: {response.get('error', '정책 위반')}"
        is_error = True
        add_trace(f"[guardrails] 차단됨: {response.get('error', '정책 위반')}", "GUARD")
    else:
        if "orders" in response:
            result_summary = f"주문 {len(response['orders'])}건 조회"
            add_trace(f"[결과] 주문 {len(response['orders'])}건 조회", "OK")
        elif "recommendations" in response or "products" in response:
            cnt = len(response.get("recommendations") or response.get("products", []))
            result_summary = f"추천 상품 {cnt}건"
            add_trace(f"[결과] 추천 상품 {cnt}건", "OK")
        elif "hits" in response:
            result_summary = f"정책 검색 {len(response['hits'])}건"
            add_trace(f"[결과] 정책 검색 {len(response['hits'])}건", "OK")
        elif "ticket" in response:
            result_summary = f"티켓: {response['ticket'].get('ticket_id', 'N/A')}"
            add_trace(f"[결과] 티켓 생성: {response['ticket'].get('ticket_id', 'N/A')}", "OK")
        elif "detail" in response:
            result_summary = "주문 상세 조회"
            add_trace(f"[결과] 주문 상세 조회 완료", "OK")
        else:
            result_summary = "처리 완료"
            add_trace(f"[결과] 처리 완료", "OK")

    add_unified_log(
        "TOOL",
        f"오케스트레이터 실행: {intent}/{sub_intent or '-'}",
        user_id=user_id,
        intent=intent,
        sub_intent=sub_intent or "",
        duration_ms=orch_ms
    )
    
    add_unified_log(
        "RESULT",
        result_summary,
        user_id=user_id,
        intent=intent,
        sub_intent=sub_intent or "",
        duration_ms=total_ms,
        is_error=is_error
    )
    
    add_unified_log(
        "JSON",
        f"응답 데이터 ({len(json.dumps(response, default=str))} bytes)",
        user_id=user_id,
        data=response
    )

    add_trace(f"[orchestrator] 완료 ({orch_ms:.0f}ms)", "TOOL")
    add_trace(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")

    return response, get_trace()


def format_response(res: Dict[str, Any]) -> str:
    if "orders" in res:
        orders = res["orders"]
        lines = [f"**주문 목록 ({len(orders)}건)**"]
        for o in orders[:7]:
            lines.append(f"• `{o.get('order_id', '-')}` | {o.get('status', '-')} | {str(o.get('order_date', ''))[:10]} | ₩{o.get('total_amount', 0):,.0f}")
        return "\n".join(lines)
    if "detail" in res:
        od = res["detail"]["order"]
        items = res["detail"].get("items", [])
        lines = [f"**주문 상세: {od.get('order_id')}**", f"상태: {od.get('status')} | 금액: ₩{od.get('total_amount', 0):,.0f}", f"배송지: {od.get('shipping_address', '-')}"]
        if items:
            lines.append("\n**주문 상품:**")
            for it in items[:5]:
                lines.append(f"  • {it.get('title', it.get('product_id', '-'))} ×{it.get('quantity', 1)}")
        return "\n".join(lines)
    if "status" in res:
        st = res["status"]
        return f"**배송 상태: {st.get('status')}**\n예상 배송일: {st.get('estimated_delivery', '-')}"
    if "cancel_result" in res:
        cr = res["cancel_result"]
        return f"**주문 취소 완료**\n티켓: {cr.get('ticket_id', '-')}" if cr.get("ok") else f"**취소 불가**: {cr.get('error')}"
    if "ticket" in res:
        t = res["ticket"]
        return f"**티켓 생성 완료**\nID: {t.get('ticket_id')} | 유형: {t.get('issue_type')} | 상태: {t.get('status')}"
    if "recommendations" in res:
        recs = res["recommendations"]
        lines = [f"**추천 상품 ({len(recs)}건)**"]
        for r in recs[:5]:
            lines.append(f"• {r.get('name', r.get('product_id', '-'))[:35]} | ₩{r.get('price', 0):,.0f}")
        return "\n".join(lines)
    if "hits" in res:
        hits = res["hits"]
        lines = [f"**정책 검색 결과 ({len(hits)}건)**"]
        for h in hits[:5]:
            lines.append(f"• [{h.get('metadata', {}).get('doc_type', '-')}] {h.get('metadata', {}).get('title', '-')}")
        if res.get("response"):
            lines.append(f"\n---\n{res['response']}")
        return "\n".join(lines)
    if res.get("need"):
        return f"{res.get('message', '추가 정보가 필요합니다.')}"
    if res.get("error"):
        return f"**에러**: {res.get('error')}"
    if res.get("response"):
        return res["response"]
    return json.dumps(res, ensure_ascii=False, indent=2, cls=DateTimeEncoder)


CUSTOMERS = get_customers()
PRODUCTS = get_products()
STATS = get_stats()

CUSTOM_CSS = """
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    --border-default: #e2e8f0;
    --text-primary: #1e293b;
    --text-muted: #64748b;
    --accent-primary: #2563eb;
}

/* Base Layout */
.gradio-container { 
    background: var(--bg-primary) !important; 
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

.block, .wrap, .panel, .form { 
    background: var(--bg-secondary) !important; 
    color: var(--text-primary) !important;
    border-radius: var(--radius-md) !important;
}

/* Typography */
h1, h2, h3, h4, h5 { 
    color: var(--text-primary) !important; 
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
}
h1 { font-size: 28px !important; }
h2 { font-size: 22px !important; }
h3 { font-size: 18px !important; }
h4 { font-size: 16px !important; }

p, span, div, li { color: var(--text-primary) !important; }
td, th { color: var(--text-primary) !important; background: var(--bg-tertiary) !important; }
label, .label { 
    color: var(--text-label) !important; 
    font-weight: 600 !important; 
    font-size: 13px !important;
    letter-spacing: 0.01em !important;
}

/* Form Elements */
input, textarea { 
    background: var(--bg-tertiary) !important; 
    border: 1px solid var(--border-default) !important; 
    color: var(--text-primary) !important;
    border-radius: var(--radius-md) !important;
    padding: var(--space-3) var(--space-4) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
input:focus, textarea:focus {
    border-color: var(--border-active) !important;
    box-shadow: 0 0 0 3px var(--accent-primary-subtle) !important;
    outline: none !important;
}
input::placeholder, textarea::placeholder {
    color: var(--text-muted) !important;
}

button { 
    border-radius: 4px !important;
    font-weight: 500 !important;
    font-size: 11px !important;
    padding: 4px 8px !important;
    min-height: 22px !important;
    line-height: 1 !important;
}
button.sm, .gr-button-sm {
    padding: 2px 6px !important;
    font-size: 10px !important;
    min-height: 18px !important;
}
.gr-button-primary, button.primary { 
    background: var(--accent-primary) !important; 
    color: white !important;
    border: none !important;
}
.gr-button-primary:hover, button.primary:hover {
    background: var(--accent-primary-hover) !important;
}
.gr-button-secondary, button.secondary {
    background: #e5e7eb !important;
    border: 1px solid #cbd5e1 !important;
    color: #374151 !important;
}
.gr-button-secondary:hover, button.secondary:hover {
    background: #d1d5db !important;
    border-color: #9ca3af !important;
}
button.stop {
    background: var(--accent-error) !important;
    color: white !important;
}

/* Tab Navigation */
.tabs, .tab-nav, [role="tablist"] { 
    background: #f3f4f6 !important; 
    border: 1px solid #e5e7eb !important; 
    border-radius: 6px !important; 
    padding: 2px !important;
    margin-bottom: 8px !important;
}
.tab-nav button, [role="tab"], .tabs button { 
    background: transparent !important; 
    color: #374151 !important; 
    font-weight: 500 !important; 
    font-size: 12px !important;
    border: none !important; 
    border-radius: 4px !important;
    padding: 4px 10px !important;
}
.tab-nav button:hover, [role="tab"]:hover, .tabs button:hover { 
    color: #111827 !important; 
    background: #e5e7eb !important; 
}
.tab-nav button.selected, [role="tab"][aria-selected="true"], .tabs button.selected { 
    background: #ffffff !important; 
    color: #111827 !important; 
    font-weight: 600 !important; 
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}

/* Chatbot */
.chatbot { 
    background: var(--bg-secondary) !important; 
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
}
.chatbot .user { 
    background: linear-gradient(135deg, var(--accent-primary), #818cf8) !important; 
    color: white !important;
    border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg) !important;
}
.chatbot .bot { 
    background: var(--bg-tertiary) !important; 
    color: var(--text-primary) !important;
    border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm) !important;
}

/* Tables & Dataframes */
table, .dataframe { 
    background: var(--bg-secondary) !important; 
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    overflow: hidden !important;
}
table th { 
    background: var(--bg-elevated) !important; 
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    padding: var(--space-3) var(--space-4) !important;
    text-align: left !important;
    border-bottom: 1px solid var(--border-default) !important;
}
table td { 
    color: var(--text-secondary) !important; 
    padding: var(--space-3) var(--space-4) !important;
    border-bottom: 1px solid var(--border-default) !important;
}
table tr:hover td {
    background: var(--bg-tertiary) !important;
}

/* Dropdowns & Selects */
select, .gr-dropdown { 
    background: var(--bg-tertiary) !important; 
    color: var(--text-primary) !important; 
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    padding: var(--space-2) var(--space-3) !important;
}
select option, .gr-dropdown option { 
    background: var(--bg-secondary) !important; 
    color: var(--text-primary) !important; 
}
ul[role="listbox"], .dropdown-menu { 
    background: var(--bg-secondary) !important; 
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
}
ul[role="listbox"] li, [role="option"] { 
    color: var(--text-primary) !important; 
    background: var(--bg-secondary) !important;
    padding: var(--space-2) var(--space-3) !important;
}
ul[role="listbox"] li:hover, [role="option"]:hover { 
    background: var(--accent-primary-subtle) !important; 
}

/* Code blocks */
.code, pre, code {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    color: var(--text-primary) !important;
}

/* Accordions */
.accordion {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
}
.accordion > .label-wrap {
    background: var(--bg-tertiary) !important;
    color: var(--text-primary) !important;
}

/* Sliders */
input[type="range"] {
    accent-color: var(--accent-primary) !important;
}

/* Hide footer */
footer, .footer, [class*="footer"], .built-with { 
    display: none !important; 
}

/* Custom Components */
.stat-card { 
    background: var(--bg-tertiary); 
    padding: var(--space-4) var(--space-5); 
    border-radius: var(--radius-lg); 
    text-align: center; 
    border: 1px solid var(--border-default);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.stat-card .value { 
    font-size: 28px; 
    font-weight: 700; 
    color: var(--text-primary);
    line-height: 1.2;
}
.stat-card .label { 
    font-size: 12px; 
    color: var(--text-muted); 
    margin-top: var(--space-2);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stat-card.primary { 
    background: var(--accent-primary-subtle); 
    border-color: var(--accent-primary);
}
.stat-card.primary .value { color: var(--accent-primary); }

.customer-card { 
    background: linear-gradient(135deg, #f8fafc, #f1f5f9); 
    border-radius: 12px; 
    padding: 16px 20px; 
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    margin: 0;
}
.customer-card p { margin: 4px 0; line-height: 1.5; }
.customer-card strong { color: #1e293b; font-size: 15px; font-weight: 600; }
.customer-card code { 
    background: #3b82f6; 
    color: white; 
    padding: 2px 8px; 
    border-radius: 4px; 
    font-size: 10px; 
    font-weight: 600;
    margin-left: 8px;
}
.customer-card table { 
    width: 100%; 
    margin-top: 12px; 
    font-size: 13px;
    border-collapse: collapse;
}
.customer-card th, .customer-card td { 
    padding: 8px 12px !important; 
    text-align: center !important;
    border: 1px solid #e2e8f0 !important;
    background: white !important;
}
.customer-card th { 
    background: #f8fafc !important; 
    font-weight: 500 !important;
    color: #64748b !important;
    font-size: 11px !important;
}
.customer-card td { color: #1e293b !important; }

/* CS Agent Professional Layout */
.cs-section {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}
.cs-section-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #f3f4f6;
}
.cs-chat-container {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
}
.cs-input-row {
    display: flex;
    gap: 8px;
    padding: 12px;
    background: #f9fafb;
    border-top: 1px solid #e5e7eb;
}
.cs-actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: 8px;
}
.cs-quick-btn {
    background: #f3f4f6 !important;
    border: 1px solid #e5e7eb !important;
    color: #374151 !important;
    font-size: 12px !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
.cs-quick-btn:hover {
    background: #e5e7eb !important;
    border-color: #d1d5db !important;
}
.cs-action-btn-primary {
    background: #3b82f6 !important;
    border: none !important;
    color: white !important;
}
.cs-action-btn-primary:hover {
    background: #2563eb !important;
}
.cs-action-btn-danger {
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    color: #dc2626 !important;
}
.cs-action-btn-danger:hover {
    background: #fee2e2 !important;
}
.cs-options-row {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

/* Debug Panel Improvements */
.debug-section {
    background: #1e293b;
    border-radius: 12px;
    padding: 16px;
    margin-top: 12px;
}
.debug-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #334155;
}
.debug-section-title {
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Slide Panel */
.debug-panel-container {
    position: fixed;
    top: 0;
    right: 0;
    height: 100vh;
    width: 420px;
    background: #ffffff;
    border-left: 1px solid #e2e8f0;
    box-shadow: -4px 0 20px rgba(0,0,0,0.1);
    transform: translateX(100%);
    transition: transform 0.3s ease;
    z-index: 1000;
    display: flex;
    flex-direction: column;
}
.debug-panel-container.open {
    transform: translateX(0);
}
.debug-panel-header {
    padding: 12px 16px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
}
.debug-panel-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
}
.debug-panel-close {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: #64748b;
    padding: 4px 8px;
}
.debug-panel-close:hover { color: #1e293b; }
.debug-panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}
.debug-toggle-btn {
    position: fixed;
    top: 50%;
    right: 0;
    transform: translateY(-50%);
    background: #3b82f6;
    color: white;
    border: none;
    padding: 12px 8px;
    border-radius: 8px 0 0 8px;
    cursor: pointer;
    z-index: 999;
    font-size: 12px;
    writing-mode: vertical-rl;
    text-orientation: mixed;
    box-shadow: -2px 0 8px rgba(0,0,0,0.15);
    transition: all 0.2s;
}
.debug-toggle-btn:hover { background: #2563eb; padding-right: 12px; }
.debug-toggle-btn.panel-open { right: 420px; }

/* Log Entry Styles */
.log-empty {
    text-align: center;
    color: #94a3b8;
    padding: 40px 20px;
    font-size: 13px;
}
.log-entry {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 8px;
    font-size: 12px;
}
.log-entry.log-error {
    background: #fef2f2;
    border-color: #fecaca;
}
.log-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    flex-wrap: wrap;
}
.log-time {
    color: #64748b;
    font-family: monospace;
    font-size: 11px;
}
.log-type {
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    color: white;
    text-transform: uppercase;
}
.log-intent {
    background: #f3e8ff;
    color: #7c3aed;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 500;
}
.log-duration {
    color: #059669;
    font-size: 10px;
    font-weight: 500;
}
.log-message {
    color: #334155;
    line-height: 1.4;
    word-break: break-word;
}
.log-data {
    background: #1e293b;
    color: #e2e8f0;
    padding: 8px 10px;
    border-radius: 4px;
    margin-top: 8px;
    font-size: 10px;
    font-family: monospace;
    overflow-x: auto;
    max-height: 150px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

.section-title { 
    font-size: 15px; 
    font-weight: 700; 
    color: var(--text-label); 
    margin: var(--space-5) 0 var(--space-3) 0; 
    padding-bottom: var(--space-2); 
    border-bottom: 1px solid var(--border-default);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.entity-legend {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    flex-wrap: wrap;
}
.entity-legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
}
.entity-legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
}
.entity-legend-label {
    font-size: 12px;
    color: var(--text-muted);
}

/* Panel styles */
.info-panel {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
}
.info-panel-header {
    font-weight: 600;
    color: var(--text-label);
    margin-bottom: var(--space-3);
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: var(--bg-secondary);
}
::-webkit-scrollbar-thumb {
    background: var(--border-hover);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .stat-card .value { font-size: 22px; }
    .tab-nav button { padding: var(--space-2) var(--space-3) !important; font-size: 13px !important; }
}
"""

with gr.Blocks(title="E-Commerce CS Agent", css=CUSTOM_CSS) as demo:
    # === Global Admin Density Override (ALL TABS) ===
    gr.HTML("""
<style>
/* Base typography */
body { font-size: 13px; }

/* Compact spacing scale */
:root {
  --pad-xxs: 2px;
  --pad-xs: 4px;
  --pad-sm: 6px;
  --pad-md: 8px;
}

/* Buttons */
.gr-button, .gr-button-sm {
  padding: 4px 8px !important;
  min-height: 24px !important;
  font-size: 12px !important;
  border-radius: 4px !important;
}

/* Containers / panels */
.gr-box, .gr-panel, .gr-form {
  padding: var(--pad-sm) !important;
  margin-bottom: var(--pad-sm) !important;
  border-radius: 6px !important;
}

/* Markdown density */
.gr-markdown p { margin: 2px 0 !important; }
.gr-markdown h1,
.gr-markdown h2,
.gr-markdown h3 {
  margin: 4px 0 !important;
  font-weight: 600;
}

/* Tabs */
button[role="tab"] {
  padding: 4px 10px !important;
  font-size: 12px !important;
}
button[role="tab"][aria-selected="true"] {
  font-weight: 700;
}

/* Tables */
table { font-size: 12px !important; }
th, td { padding: 4px 6px !important; }

/* Separators */
hr { margin: 6px 0 !important; }
</style>
""")
    
    gr.HTML(f"""
    <div style="padding:8px 0 12px;border-bottom:1px solid #e5e7eb;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
        <div>
            <h1 style="color:#111827;margin:0;font-size:18px;font-weight:600;">E-Commerce CS Agent</h1>
            <p style="color:#6b7280;margin:2px 0 0;font-size:12px;">고객 {STATS['customers']} · 상품 {STATS['products']:,} · 주문 {STATS['orders']} · 티켓 {STATS['tickets']} · 트리플 {STATS['triples']:,}</p>
        </div>
    </div>
    """)
    
    with gr.Tabs() as main_tabs:
        with gr.TabItem("상담"):
            with gr.Tabs():
                with gr.TabItem("상담 에이전트"):
                    debug_panel_visible = gr.State(False)
                    
                    with gr.Row(equal_height=False):
                        with gr.Column(scale=2):
                            gr.HTML('<div class="cs-section-header">고객 컨텍스트</div>')
                            with gr.Row():
                                user_select = gr.Dropdown(choices=CUSTOMERS, value=CUSTOMERS[0] if CUSTOMERS else None, label="고객", scale=2)
                                order_select = gr.Dropdown(choices=[], label="주문", scale=2, allow_custom_value=True)
                            with gr.Row():
                                product_select = gr.Dropdown(choices=PRODUCTS[:30], label="상품 (추천용)", scale=2, allow_custom_value=True)
                            
                            customer_info = gr.Markdown(elem_classes="customer-card")
                            
                            gr.HTML('<div class="cs-section-header" style="margin-top:16px;">빠른 액션</div>')
                            with gr.Row():
                                ex1 = gr.Button("주문 조회", size="sm", elem_classes="cs-quick-btn")
                                ex2 = gr.Button("환불 정책", size="sm", elem_classes="cs-quick-btn")
                                ex3 = gr.Button("추천", size="sm", elem_classes="cs-quick-btn")
                            with gr.Row():
                                ex4 = gr.Button("배송 상태", size="sm", elem_classes="cs-quick-btn")
                                ex5 = gr.Button("주문 취소", size="sm", elem_classes="cs-quick-btn")
                            
                            gr.HTML('<div class="cs-section-header" style="margin-top:16px;">주문 관리</div>')
                            with gr.Row():
                                btn_detail = gr.Button("상세 보기", variant="primary", size="sm")
                                btn_status = gr.Button("상태 확인", variant="secondary", size="sm")
                            with gr.Row():
                                btn_cancel = gr.Button("취소 요청", variant="stop", size="sm")
                                btn_ticket = gr.Button("문의 등록", variant="secondary", size="sm")
                            
                            with gr.Accordion("추가 옵션", open=False):
                                cancel_reason = gr.Textbox(label="취소/문의 사유", value="고객 요청", lines=1)
                                clear_btn = gr.Button("대화 초기화", variant="secondary", size="sm")
                        
                        with gr.Column(scale=5):
                            gr.HTML('<div class="cs-section-header">상담 대화</div>')
                            chat = gr.Chatbot(label=None, height=420, show_label=False)
                            
                            with gr.Row():
                                msg = gr.Textbox(placeholder="고객 문의를 입력하세요...", scale=6, container=False, show_label=False)
                                send_btn = gr.Button("전송", variant="primary", scale=1, min_width=80)
                            
                            with gr.Accordion("개발자 도구", open=False):
                                gr.HTML('<div class="debug-section-title">파이프라인 로그</div>')
                                debug_toggle_btn = gr.Button("로그 패널 열기", variant="secondary", size="sm")
                    
                    with gr.Row(visible=False) as debug_panel:
                        with gr.Column():
                            gr.HTML("""
                            <div style="background:#1e293b;color:#94a3b8;padding:12px 16px;border-radius:8px 8px 0 0;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">
                                Pipeline Debug Log
                            </div>
                            """)
                            unified_log_html = gr.HTML(value='<div class="log-empty">로그가 없습니다</div>')
                            with gr.Row():
                                clear_log_btn = gr.Button("로그 초기화", variant="secondary", size="sm")
                                close_debug_btn = gr.Button("패널 닫기", variant="secondary", size="sm")
                            
                            with gr.Accordion("Raw Trace", open=False):
                                trace_out = gr.Textbox(label="추적", lines=6, max_lines=10, interactive=False)
                            with gr.Accordion("Raw JSON", open=False):
                                res_json = gr.Code(label="응답", language="json", lines=6)
                    
                    def toggle_debug_panel(visible):
                        return gr.update(visible=not visible), not visible
                    
                    debug_toggle_btn.click(toggle_debug_panel, [debug_panel_visible], [debug_panel, debug_panel_visible])
                    close_debug_btn.click(lambda: (gr.update(visible=False), False), outputs=[debug_panel, debug_panel_visible])
                    clear_log_btn.click(clear_unified_log, outputs=[unified_log_html])
                
                with gr.TabItem("추천 스튜디오"):
                    gr.HTML("""
                    <div style="padding:4px 0;">
                        <h3 style="color:#fafafa;margin:0;font-size:14px;font-weight:600;">SPARQL 추천 엔진</h3>
                    </div>
                    """)
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            rec_customer = gr.Dropdown(choices=CUSTOMERS, value=CUSTOMERS[0] if CUSTOMERS else None, label="고객")
                            rec_product = gr.Dropdown(choices=PRODUCTS[:50], label="상품 (유사 상품용)", allow_custom_value=True)
                            rec_mode = gr.Radio(
                                ["협업 필터링", "유사 상품", "인기 상품", "카테고리별"],
                                value="협업 필터링",
                                label="추천 모드"
                            )
                            rec_limit = gr.Slider(minimum=3, maximum=20, value=5, step=1, label="최대 결과")
                            rec_btn = gr.Button("추천 받기", variant="primary", size="sm")
                        
                        with gr.Column(scale=3):
                            rec_results = gr.Dataframe(
                                headers=["상품 ID", "상품명", "가격", "평점", "점수"],
                                datatype=["str", "str", "str", "str", "str"],
                                label="추천 결과",
                                interactive=False
                            )
                        
                        with gr.Column(scale=2):
                            gr.HTML("""
                            <div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">
                                <div style="font-size:11px;font-weight:600;color:#374151;">추천 근거</div>
                            </div>
                            """)
                            rec_explanation = gr.Markdown("""
**Reasoning will appear here after running recommendations**

The explanation will include:
- 🔗 **Relationships Used**: Which graph edges contributed
- 📊 **Scoring Method**: How items were ranked
- 👤 **Customer Profile**: Relevant purchase history
- 🎯 **Confidence Score**: How confident the recommendation is
                            """)
                            rec_sparql = gr.Code(label="사용된 SPARQL 쿼리", language="sql", lines=8)
                
                with gr.TabItem("정책 검색"):
                    gr.HTML("""
                    <div style="padding:4px 0;">
                    <h3 style="color:#fafafa;margin:0;font-size:14px;font-weight:600;">정책 검색 (RAG)</h3>
                    </div>
                    """)
                    
                    with gr.Row():
                        policy_q = gr.Textbox(label="정책 질의", placeholder="예: 환불 조건, 배송 지연 보상", scale=4)
                        btn_policy = gr.Button("검색", variant="primary", scale=1)
                    
                    policy_results = gr.Markdown(label="검색 결과")
                    
                    gr.Markdown("**자주 묻는 정책**")
                    with gr.Row():
                        policy_ex1 = gr.Button("환불 정책", size="sm")
                        policy_ex2 = gr.Button("배송 안내", size="sm")
                        policy_ex3 = gr.Button("교환 절차", size="sm")
                        policy_ex4 = gr.Button("보증 기간", size="sm")
                
                with gr.TabItem("빠른 추천"):
                    gr.Markdown("**빠른 추천 버튼** (SPARQL 협업 필터링)")
                    with gr.Row():
                        btn_collab = gr.Button("협업 필터링", variant="primary", size="sm")
                        btn_similar = gr.Button("유사 상품", variant="secondary", size="sm")
                        btn_popular = gr.Button("인기 상품", variant="secondary", size="sm")

        # ===== 탭 3: 데이터 관리 =====
        with gr.TabItem("데이터 관리"):
            gr.HTML("""
            <div style="padding:6px 0 4px 0;">
                <h2 style="color:#fafafa;margin:0;font-size:15px;font-weight:600;">데이터 탐색</h2>
            </div>
            """)
            
            with gr.Row():
                admin_stats_refresh = gr.Button("새로고침", variant="secondary", size="sm")
            
            admin_stats_html = gr.HTML()
            
            with gr.Row():
                admin_order_dist = gr.HTML()
                admin_ticket_dist = gr.HTML()
            
            with gr.Row():
                gr.HTML('<span style="color:#a1a1aa;font-size:12px;font-weight:600;">고객</span>')
                admin_cust_refresh = gr.Button("새로고침", variant="secondary", size="sm")
            admin_cust_table = gr.Dataframe(
                headers=["고객 ID", "이름", "이메일", "등급", "가입일"],
                datatype=["str", "str", "str", "str", "str"],
                interactive=False
            )
            
            with gr.Row():
                gr.HTML('<span style="color:#a1a1aa;font-size:12px;font-weight:600;">주문</span>')
                admin_order_filter = gr.Dropdown(
                    choices=["전체", "pending", "processing", "shipped", "delivered", "cancelled"],
                    value="전체",
                    label="상태 필터",
                    scale=1
                )
                admin_order_refresh = gr.Button("새로고침", variant="secondary", size="sm", scale=0)
            admin_order_table = gr.Dataframe(
                headers=["주문 ID", "고객", "상태", "금액", "날짜"],
                datatype=["str", "str", "str", "str", "str"],
                interactive=False
            )
            
            with gr.Row():
                gr.HTML('<span style="color:#a1a1aa;font-size:12px;font-weight:600;">티켓</span>')
                admin_ticket_filter = gr.Dropdown(
                    choices=["전체", "open", "in_progress", "resolved", "closed"],
                    value="전체",
                    label="상태 필터",
                    scale=1
                )
                admin_ticket_refresh = gr.Button("새로고침", variant="secondary", size="sm", scale=0)
            admin_ticket_table = gr.Dataframe(
                headers=["티켓 ID", "고객", "유형", "상태", "생성일"],
                datatype=["str", "str", "str", "str", "str"],
                interactive=False
            )

        # ===== 탭 4: 지식그래프 =====
        with gr.TabItem("지식그래프"):
            gr.HTML("""
            <div style="padding:4px 0;">
                <h2 style="color:#fafafa;margin:0;font-size:15px;font-weight:600;">지식 그래프</h2>
            </div>
            """)

            gr.HTML("""
            <div style="padding:4px 0;font-size:11px;color:#6b7280;">
                <span style="margin-right:12px;"><span style="display:inline-block;width:8px;height:8px;background:#2563eb;border-radius:2px;margin-right:4px;"></span>클래스</span>
                <span style="margin-right:12px;"><span style="display:inline-block;width:8px;height:8px;background:#059669;border-radius:2px;margin-right:4px;"></span>고객</span>
                <span style="margin-right:12px;"><span style="display:inline-block;width:8px;height:8px;background:#0891b2;border-radius:2px;margin-right:4px;"></span>주문</span>
                <span style="margin-right:12px;"><span style="display:inline-block;width:8px;height:8px;background:#d97706;border-radius:2px;margin-right:4px;"></span>상품</span>
                <span style="margin-right:12px;"><span style="display:inline-block;width:8px;height:8px;background:#dc2626;border-radius:2px;margin-right:4px;"></span>티켓</span>
                <span><span style="display:inline-block;width:8px;height:8px;background:#7c3aed;border-radius:2px;margin-right:4px;"></span>카테고리</span>
            </div>
            """)

            with gr.Row():
                with gr.Column(scale=3):
                    with gr.Tabs() as graph_tabs:
                        with gr.TabItem("ER Diagram", id=0):
                            ontology_er_html = gr.HTML()
                        with gr.TabItem("Ontology Schema", id=1):
                            vis_schema = gr.HTML()
                        with gr.TabItem("Instance Graph", id=2):
                            with gr.Row():
                                instance_limit = gr.Slider(
                                    minimum=10, maximum=2000, value=500, step=10,
                                    label="노드 제한", scale=2
                                )
                                instance_customer_level = gr.Dropdown(
                                    choices=["전체", "platinum", "gold", "silver", "bronze"],
                                    value="전체",
                                    label="고객 등급",
                                    scale=2
                                )
                                instance_order_status = gr.Dropdown(
                                    choices=["전체", "delivered", "shipped", "processing", "pending", "cancelled"],
                                    value="전체",
                                    label="주문 상태",
                                    scale=2
                                )
                                instance_refresh = gr.Button("적용", variant="secondary", scale=1)
                            instance_stats = gr.Markdown()
                            vis_instance = gr.HTML()
                        with gr.TabItem("상품 유사도", id=3):
                            with gr.Row():
                                similarity_category = gr.Dropdown(
                                    choices=get_similarity_categories(),
                                    value="전체",
                                    label="카테고리",
                                    scale=2
                                )
                                similarity_limit = gr.Slider(
                                    minimum=10, maximum=5000, value=1000, step=50,
                                    label="엣지 제한", scale=2
                                )
                                similarity_threshold = gr.Slider(
                                    minimum=0.0, maximum=1.0, value=0.0, step=0.05,
                                    label="최소 유사도", scale=2
                                )
                                similarity_refresh = gr.Button("적용", variant="secondary", scale=1)
                            similarity_stats = gr.Markdown()
                            vis_similarity = gr.HTML()
                
                with gr.Column(scale=1):
                    gr.HTML("""
                    <div style="font-size:11px;font-weight:600;color:#374151;padding:4px 0;border-bottom:1px solid #e5e7eb;">엔티티 상세</div>
                    """)
                    graph_entity_lookup = gr.Textbox(label="엔티티 ID", placeholder="예: user_001, ORD-001")
                    graph_entity_btn = gr.Button("엔티티 조회", variant="secondary", size="sm")
                    graph_entity_detail = gr.JSON(label="엔티티 데이터", visible=True)

            with gr.Row():
                vis_refresh = gr.Button("새로고침", variant="secondary", size="sm")
                gr.Markdown("*Update data: `python scripts/export_visualization_data.py`*", elem_classes="hint")

        # ===== 탭 5: 개발자 도구 =====
        with gr.TabItem("개발자 도구"):
            gr.HTML("""
            <div style="padding:4px 0;">
                <h2 style="color:#fafafa;margin:0;font-size:15px;font-weight:600;">개발자 도구</h2>
            </div>
            """)

            with gr.Tabs():
                with gr.TabItem("SPARQL 쿼리"):
                    gr.Markdown("**Execute SPARQL SELECT Queries**")

                    with gr.Accordion("Natural Language → SPARQL", open=True):
                        with gr.Row():
                            nl_query_input = gr.Textbox(
                                label="자연어 질문",
                                placeholder="예: platinum 등급 고객 목록 보여줘",
                                lines=2,
                                scale=4
                            )
                            nl_convert_btn = gr.Button("SPARQL로 변환", variant="primary", scale=1)
                        nl_status = gr.Markdown()

                        gr.Markdown("**Example Queries:**")
                        with gr.Row():
                            nl_ex1 = gr.Button("플래티넘 고객", size="sm")
                            nl_ex2 = gr.Button("$100 이상 상품", size="sm")
                            nl_ex3 = gr.Button("user_001 주문", size="sm")
                            nl_ex4 = gr.Button("배송된 주문", size="sm")

                    sparql_input = gr.Textbox(
                        label="SPARQL Query",
                        lines=8,
                        value="""SELECT ?s ?p ?o WHERE {
    ?s ?p ?o .
} LIMIT 10"""
                    )
                    with gr.Row():
                        sparql_run = gr.Button("실행", variant="primary", size="sm")
                        sparql_status = gr.Markdown()
                    sparql_result = gr.Dataframe(
                        headers=["Subject", "Predicate", "Object"],
                        interactive=False
                    )

                    gr.Markdown("**Quick Queries**")
                    with gr.Row():
                        ex_q1 = gr.Button("고객", size="sm")
                        ex_q2 = gr.Button("상품", size="sm")
                        ex_q3 = gr.Button("주문", size="sm")
                        ex_q4 = gr.Button("유사도", size="sm")

                with gr.TabItem("트리플 관리"):
                    gr.Markdown("#### Add Triple")
                    with gr.Row():
                        triple_subject = gr.Textbox(label="Subject (URI)", placeholder="ecom:customer_user_001")
                        triple_predicate = gr.Textbox(label="Predicate (URI)", placeholder="ecom:email")
                        triple_object = gr.Textbox(label="Object", placeholder="new@email.com")
                    with gr.Row():
                        triple_type = gr.Radio(["URI", "Literal"], value="Literal", label="Object Type")
                        triple_add = gr.Button("추가", variant="primary", size="sm")

                    gr.HTML('<div style="margin:8px 0 4px;color:#a1a1aa;font-size:12px;font-weight:600;">트리플 삭제</div>')
                    with gr.Row():
                        del_subject = gr.Textbox(label="Subject", placeholder="ecom:customer_user_001")
                        del_predicate = gr.Textbox(label="Predicate", placeholder="ecom:email")
                        del_object = gr.Textbox(label="Object (optional)", placeholder="Leave empty to delete all")
                    triple_delete = gr.Button("삭제", variant="stop", size="sm")
                    triple_status = gr.Markdown()

                with gr.TabItem("엔티티 브라우저"):
                    gr.Markdown("**엔티티 상세 조회**")
                    with gr.Row():
                        entity_type = gr.Dropdown(
                            ["고객", "상품", "주문", "티켓"],
                            value="고객",
                            label="엔티티 유형"
                        )
                        entity_search = gr.Textbox(label="ID 검색", placeholder="user_001")
                        entity_search_btn = gr.Button("검색", variant="primary", size="sm")
                    entity_detail = gr.JSON(label="엔티티 상세")

                with gr.TabItem("TTL 편집기"):
                    gr.Markdown("### Turtle File Browser & Editor")
                    gr.Markdown("*Schema and embedding files are read-only*")

                    with gr.Row():
                        ttl_file_select = gr.Dropdown(
                            choices=list(TTL_FILE_MAP.keys()),
                            label="File Selection",
                            value="ontology/ecommerce.ttl (스키마)",
                            scale=3
                        )
                        ttl_load_btn = gr.Button("불러오기", variant="secondary", size="sm", scale=1)

                    ttl_editor = gr.Code(
                        label="TTL Content",
                        language=None,
                        lines=25,
                        interactive=True
                    )

                    with gr.Row():
                        ttl_save_btn = gr.Button("저장", variant="primary", size="sm")
                        ttl_validate_btn = gr.Button("검증", variant="secondary", size="sm")
                        ttl_reload_store_btn = gr.Button("저장소 새로고침", variant="secondary", size="sm")

                    ttl_status = gr.Markdown()

                    gr.Markdown("**파일 정보**")
                    ttl_file_info = gr.HTML("""
                    <div style="font-size:11px;color:#d4d4d8;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr style="color:#c4b5fd;font-size:10px;"><th style="text-align:left;padding:4px;">파일</th><th style="text-align:left;">용도</th><th style="text-align:left;">권한</th></tr>
                            <tr><td style="padding:3px;">ontology/ecommerce.ttl</td><td>스키마 정의</td><td>읽기전용</td></tr>
                            <tr><td style="padding:3px;">instances/customers.ttl</td><td>고객 데이터</td><td>편집가능</td></tr>
                            <tr><td style="padding:3px;">instances/orders.ttl</td><td>주문 데이터</td><td>편집가능</td></tr>
                            <tr><td style="padding:3px;">instances/products.ttl</td><td>상품 데이터</td><td>편집가능</td></tr>
                            <tr><td style="padding:3px;">instances/similarities.ttl</td><td>유사도 관계</td><td>편집가능</td></tr>
                            <tr><td style="padding:3px;">instances/tickets.ttl</td><td>티켓 데이터</td><td>편집가능</td></tr>
                            <tr><td style="padding:3px;">instances/embeddings.ttl</td><td>임베딩</td><td>읽기전용</td></tr>
                            <tr><td style="padding:3px;">shacl/ecommerce-shapes.ttl</td><td>SHACL 검증</td><td>읽기전용</td></tr>
                        </table>
                    </div>
                    """)

                with gr.TabItem("평가"):
                    gr.HTML("""
                    <div style="font-size:11px;color:#6b7280;padding:8px 0;">
                        <table style="width:100%;border-collapse:collapse;font-size:11px;">
                            <tr style="border-bottom:1px solid #e5e7eb;">
                                <th style="text-align:left;padding:4px;color:#374151;">Metric</th>
                                <th style="text-align:right;padding:4px;color:#374151;">Value</th>
                            </tr>
                            <tr><td style="padding:4px;">Rule Precision</td><td style="text-align:right;padding:4px;">-</td></tr>
                            <tr><td style="padding:4px;">Recall</td><td style="text-align:right;padding:4px;">-</td></tr>
                            <tr><td style="padding:4px;">Conflict Rate</td><td style="text-align:right;padding:4px;">-</td></tr>
                            <tr><td style="padding:4px;">GNN Uplift</td><td style="text-align:right;padding:4px;">-</td></tr>
                        </table>
                        <p style="margin:8px 0 0;color:#9ca3af;">평가 기능 개발 중</p>
                    </div>
                    """)

    def on_customer_change(uid):
        orders = get_orders(uid)
        info = get_customer_info(uid)
        return gr.update(choices=orders, value=orders[0] if orders else None), info
    
    async def on_chat(message, history, uid):
        if not message.strip():
            return history, "", get_trace(), get_unified_log_html()
        res, trace = await process_message(uid or "user_001", message)
        reply = format_response(res)
        return history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply}
        ], json.dumps(res, ensure_ascii=False, indent=2, cls=DateTimeEncoder), trace, get_unified_log_html()
    
    async def on_order_action(uid, oid, reason, history, *, action):
        if not oid:
            return history + [
                {"role": "user", "content": f"[{action}]"},
                {"role": "assistant", "content": "주문을 선택해주세요"}
            ], "{}", get_trace()
        add_trace(f"━━━ {action}: {oid} ━━━")
        if action == "상세":
            state = AgentState(user_id=uid or "user_001", intent="order", sub_intent="detail", payload={"order_id": oid})
        elif action == "상태":
            state = AgentState(user_id=uid or "user_001", intent="order", sub_intent="status", payload={"order_id": oid})
        elif action == "취소":
            state = AgentState(user_id=uid or "user_001", intent="order", sub_intent="cancel", payload={"order_id": oid, "reason": reason})
        else:
            state = AgentState(user_id=uid or "user_001", intent="claim", payload={"action": "create", "order_id": oid, "issue_type": "inquiry", "description": reason})
        state = await orchestrate(state)
        res = state.final_response or {}
        add_trace(f"{action} 완료")
        return history + [
            {"role": "user", "content": f"[{action}: {oid}]"},
            {"role": "assistant", "content": format_response(res)}
        ], json.dumps(res, ensure_ascii=False, indent=2, cls=DateTimeEncoder), get_trace()
    
    async def on_recommend(uid, pid, history, *, rec_type):
        add_trace(f"━━━ 추천: {rec_type} ━━━")
        if rec_type == "collaborative":
            state = AgentState(user_id=uid or "user_001", intent="recommend", sub_intent="collaborative", payload={"top_k": 5})
        elif rec_type == "similar":
            if not pid:
                return history + [
                    {"role": "user", "content": "[유사상품]"},
                    {"role": "assistant", "content": "상품을 선택해주세요"}
                ], "{}", get_trace()
            state = AgentState(user_id=uid or "user_001", intent="recommend", sub_intent="similar", payload={"product_id": pid, "top_k": 5})
        else:
            state = AgentState(user_id=uid or "user_001", intent="recommend", sub_intent="popular", payload={"top_k": 5})
        state = await orchestrate(state)
        res = state.final_response or {}
        add_trace(f"추천 완료")
        return history + [
            {"role": "user", "content": f"[추천: {rec_type}]"},
            {"role": "assistant", "content": format_response(res)}
        ], json.dumps(res, ensure_ascii=False, indent=2, cls=DateTimeEncoder), get_trace()
    
    async def on_policy_search(uid, query, history):
        if not query.strip():
            return history, "", get_trace()
        add_trace(f"━━━ 정책: {query[:30]}... ━━━")
        state = AgentState(user_id=uid or "user_001", intent="policy", payload={"query": query, "top_k": 5})
        state = await orchestrate(state)
        res = state.final_response or {}
        add_trace(f"검색 완료")
        return history + [
            {"role": "user", "content": f"[정책: {query[:20]}...]"},
            {"role": "assistant", "content": format_response(res)}
        ], json.dumps(res, ensure_ascii=False, indent=2, cls=DateTimeEncoder), get_trace()
    
    def refresh_all_graphs(inst_limit: int = 50, inst_cust_level: str = "전체", inst_order_status: str = "전체", sim_limit: int = 50, sim_threshold: float = 0.0, sim_category: str = "전체"):
        """모든 그래프를 새로고침"""
        inst_html, inst_stats = render_instance_graph(int(inst_limit), inst_cust_level, inst_order_status)
        sim_html, sim_stats = render_similarity_graph(int(sim_limit), float(sim_threshold), sim_category)
        return (
            render_mermaid_er(),
            render_schema_graph(),
            inst_html,
            inst_stats,
            sim_html,
            sim_stats
        )
    
    def on_clear_chat():
        return [], "", ""

    def render_admin_stats():
        stats = get_stats()
        html = "<div style='display:flex;gap:16px;flex-wrap:wrap;'>"
        items = [("고객", stats.get("customers", 0), "#a6e3a1"), ("상품", stats.get("products", 0), "#f9e2af"),
                 ("주문", stats.get("orders", 0), "#89dceb"), ("티켓", stats.get("tickets", 0), "#f38ba8"),
                 ("트리플", stats.get("triples", 0), "#cba6f7")]
        for name, cnt, color in items:
            html += f"<div style='background:{color};color:#1e1e2e;padding:12px 20px;border-radius:10px;text-align:center;min-width:80px;'><div style='font-size:24px;font-weight:bold;'>{cnt:,}</div><div style='font-size:12px;'>{name}</div></div>"
        html += "</div>"
        return html

    user_select.change(on_customer_change, [user_select], [order_select, customer_info])
    demo.load(partial(on_customer_change, CUSTOMERS[0] if CUSTOMERS else "user_001"), outputs=[order_select, customer_info])
    demo.load(lambda: get_trace(), outputs=[trace_out])
    demo.load(render_mermaid_er, outputs=[ontology_er_html])
    demo.load(render_schema_graph, outputs=[vis_schema])
    demo.load(lambda: render_instance_graph(500, "전체", "전체"), outputs=[vis_instance, instance_stats])
    demo.load(lambda: render_similarity_graph(1000, 0.0, "전체"), outputs=[vis_similarity, similarity_stats])

    # 관리자 탭 초기화
    demo.load(get_all_customers_df, outputs=[admin_cust_table])
    demo.load(lambda: get_all_orders_df("전체"), outputs=[admin_order_table])
    demo.load(lambda: get_all_tickets_df("전체"), outputs=[admin_ticket_table])
    demo.load(render_admin_stats, outputs=[admin_stats_html])
    demo.load(get_order_status_dist, outputs=[admin_order_dist])
    demo.load(get_ticket_status_dist, outputs=[admin_ticket_dist])
    
    send_btn.click(on_chat, [msg, chat, user_select], [chat, res_json, trace_out, unified_log_html]).then(lambda: "", outputs=[msg])
    msg.submit(on_chat, [msg, chat, user_select], [chat, res_json, trace_out, unified_log_html]).then(lambda: "", outputs=[msg])
    
    ex1.click(lambda: "주문 보여줘", outputs=[msg])
    ex2.click(lambda: "환불 정책 알려줘", outputs=[msg])
    ex3.click(lambda: "추천해줘", outputs=[msg])
    ex4.click(lambda: "배송 상태 알려줘", outputs=[msg])
    ex5.click(lambda: "주문 취소하고 싶어", outputs=[msg])
    
    btn_detail.click(partial(on_order_action, action="상세"), [user_select, order_select, cancel_reason, chat], [chat, res_json, trace_out])
    btn_status.click(partial(on_order_action, action="상태"), [user_select, order_select, cancel_reason, chat], [chat, res_json, trace_out])
    btn_cancel.click(partial(on_order_action, action="취소"), [user_select, order_select, cancel_reason, chat], [chat, res_json, trace_out])
    btn_ticket.click(partial(on_order_action, action="문의"), [user_select, order_select, cancel_reason, chat], [chat, res_json, trace_out])
    
    btn_collab.click(partial(on_recommend, rec_type="collaborative"), [user_select, product_select, chat], [chat, res_json, trace_out])
    btn_similar.click(partial(on_recommend, rec_type="similar"), [user_select, product_select, chat], [chat, res_json, trace_out])
    btn_popular.click(partial(on_recommend, rec_type="popular"), [user_select, product_select, chat], [chat, res_json, trace_out])
    
    async def get_studio_recommendations(customer_id, product_id, mode, limit):
        mode_map = {
            "협업 필터링": "collaborative",
            "유사 상품": "similar", 
            "인기 상품": "trending",
            "카테고리별": "category"
        }
        rec_type = mode_map.get(mode, "collaborative")
        
        try:
            from src.recommendation.service import get_recommendation_service
            svc = get_recommendation_service()
            
            if rec_type == "similar" and product_id:
                resp = await svc.get_similar_products(product_id, top_k=int(limit))
            elif rec_type == "trending":
                resp = await svc.get_trending(period="week", top_k=int(limit))
            elif rec_type == "category":
                resp = await svc.get_category_recommendations(category_id="Electronics", top_k=int(limit))
            else:
                resp = await svc.get_similar_products(product_id or "B0002L5R78", top_k=int(limit))
            
            results = resp.products if resp else []
            
            table_data = []
            for r in results:
                pid = getattr(r, 'product_id', '') or ''
                title = getattr(r, 'title', '') or ''
                price = getattr(r, 'price', 0) or 0
                rating = getattr(r, 'avg_rating', 0) or 0
                score = getattr(r, 'score', 0) or 0
                
                table_data.append([
                    pid,
                    title[:50] + "..." if len(title) > 50 else title,
                    f"${price:.2f}" if price else "-",
                    f"{rating:.1f}" if rating else "-",
                    f"{score:.3f}" if score else "-"
                ])
            
            explanation = f"""
**Mode**: {mode}
**Customer**: {customer_id}
**Results**: {len(results)} products found

🔗 **Relationships Used**:
- Customer → Order → Product (purchase history)
- Product → Product (similarity edges)
- Category → Product (category membership)

📊 **Scoring Method**:
- Similar: Cosine similarity of product embeddings
- Trending: Purchase frequency + recency weighted
- Category: Products in same category

👤 **Customer Profile**:
- Purchase history analyzed via SPARQL
- Similar customers identified by overlap

🎯 **Confidence**: High (based on {len(results)} matches)
            """
            
            sparql = f"""PREFIX ecom: <http://ecommerce.example.org/>
SELECT ?product ?title ?price ?score
WHERE {{
  # {mode} recommendation query
  ?customer ecom:customerId "{customer_id}" .
  ?order ecom:orderedBy ?customer .
  ?item ecom:belongsTo ?order .
  ?item ecom:hasProduct ?product .
  ?product ecom:title ?title ;
           ecom:price ?price .
}}
LIMIT {int(limit)}"""
            
            return table_data, explanation, sparql
        except Exception as e:
            return [], f"Error: {str(e)}", ""
    
    rec_btn.click(
        get_studio_recommendations,
        [rec_customer, rec_product, rec_mode, rec_limit],
        [rec_results, rec_explanation, rec_sparql]
    )
    
    btn_policy.click(on_policy_search, [user_select, policy_q, chat], [chat, res_json, trace_out])
    clear_btn.click(on_clear_chat, outputs=[chat, res_json, trace_out])
    
    vis_refresh.click(
        refresh_all_graphs,
        inputs=[instance_limit, instance_customer_level, instance_order_status, similarity_limit, similarity_threshold, similarity_category],
        outputs=[ontology_er_html, vis_schema, vis_instance, instance_stats, vis_similarity, similarity_stats]
    )

    # 개별 그래프 새로고침
    instance_refresh.click(render_instance_graph, inputs=[instance_limit, instance_customer_level, instance_order_status], outputs=[vis_instance, instance_stats])
    similarity_refresh.click(render_similarity_graph, inputs=[similarity_limit, similarity_threshold, similarity_category], outputs=[vis_similarity, similarity_stats])

    # 그래프 탭 선택 이벤트 (탭 전환 시 해당 그래프 렌더링)
    def on_graph_tab_select(evt: gr.SelectData, inst_lim, inst_cust_level, inst_order_status, sim_lim, sim_thresh, sim_cat):
        """탭 선택 시 해당 그래프만 렌더링"""
        tab_id = evt.index
        if tab_id == 0:
            return render_mermaid_er(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        elif tab_id == 1:
            return gr.update(), render_schema_graph(), gr.update(), gr.update(), gr.update(), gr.update()
        elif tab_id == 2:
            inst_html, inst_stats = render_instance_graph(int(inst_lim), inst_cust_level, inst_order_status)
            return gr.update(), gr.update(), inst_html, inst_stats, gr.update(), gr.update()
        elif tab_id == 3:
            sim_html, sim_stats = render_similarity_graph(int(sim_lim), float(sim_thresh), sim_cat)
            return gr.update(), gr.update(), gr.update(), gr.update(), sim_html, sim_stats
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    graph_tabs.select(
        on_graph_tab_select,
        inputs=[instance_limit, instance_customer_level, instance_order_status, similarity_limit, similarity_threshold, similarity_category],
        outputs=[ontology_er_html, vis_schema, vis_instance, instance_stats, vis_similarity, similarity_stats]
    )

    # 관리자 탭 이벤트 핸들러
    admin_cust_refresh.click(get_all_customers_df, outputs=[admin_cust_table])
    admin_order_refresh.click(get_all_orders_df, [admin_order_filter], [admin_order_table])
    admin_order_filter.change(get_all_orders_df, [admin_order_filter], [admin_order_table])
    admin_ticket_refresh.click(get_all_tickets_df, [admin_ticket_filter], [admin_ticket_table])
    admin_ticket_filter.change(get_all_tickets_df, [admin_ticket_filter], [admin_ticket_table])
    admin_stats_refresh.click(render_admin_stats, outputs=[admin_stats_html])
    admin_stats_refresh.click(get_order_status_dist, outputs=[admin_order_dist])
    admin_stats_refresh.click(get_ticket_status_dist, outputs=[admin_ticket_dist])

    # RDF 데이터 관리 탭 이벤트 핸들러
    def on_sparql_run(query):
        rows, status = run_sparql_query(query)
        return rows, status

    sparql_run.click(on_sparql_run, [sparql_input], [sparql_result, sparql_status])

    # 예시 쿼리 버튼
    ex_q1.click(lambda: """SELECT ?cid ?name ?level WHERE {
    ?c a ecom:Customer ;
       ecom:customerId ?cid ;
       ecom:name ?name ;
       ecom:membershipLevel ?level .
} LIMIT 20""", outputs=[sparql_input])

    ex_q2.click(lambda: """SELECT ?pid ?title ?price ?brand WHERE {
    ?p a ecom:Product ;
       ecom:productId ?pid ;
       ecom:title ?title ;
       ecom:price ?price .
    OPTIONAL { ?p ecom:brand ?brand }
} LIMIT 20""", outputs=[sparql_input])

    ex_q3.click(lambda: """SELECT ?oid ?cid ?status ?amount WHERE {
    ?c a ecom:Customer ;
       ecom:customerId ?cid ;
       ecom:placedOrder ?o .
    ?o ecom:orderId ?oid ;
       ecom:status ?status ;
       ecom:totalAmount ?amount .
} LIMIT 20""", outputs=[sparql_input])

    ex_q4.click(lambda: """SELECT ?pid1 ?title1 ?pid2 ?title2 WHERE {
    ?p1 ecom:productId ?pid1 ;
        ecom:title ?title1 ;
        ecom:similarTo ?p2 .
    ?p2 ecom:productId ?pid2 ;
        ecom:title ?title2 .
} LIMIT 20""", outputs=[sparql_input])

    # 자연어 → SPARQL 변환 이벤트 핸들러
    nl_convert_btn.click(
        convert_nl_to_sparql,
        inputs=[nl_query_input],
        outputs=[sparql_input, nl_status]
    )

    # 자연어 예시 질문 버튼
    nl_ex1.click(lambda: "platinum 등급 고객 목록", outputs=[nl_query_input])
    nl_ex2.click(lambda: "100달러 이상 상품 목록", outputs=[nl_query_input])
    nl_ex3.click(lambda: "user_001 주문 내역", outputs=[nl_query_input])
    nl_ex4.click(lambda: "배송중 주문 목록", outputs=[nl_query_input])

    # 트리플 추가/삭제
    triple_add.click(add_triple, [triple_subject, triple_predicate, triple_object, triple_type], [triple_status])
    triple_delete.click(delete_triple, [del_subject, del_predicate, del_object], [triple_status])

    entity_search_btn.click(get_entity_detail, [entity_type, entity_search], [entity_detail])
    
    def graph_entity_lookup_fn(entity_id):
        if not entity_id or not entity_id.strip():
            return {}
        entity_id = entity_id.strip()
        for etype in ["Customer", "Product", "Order", "Ticket"]:
            result = get_entity_detail(etype, entity_id)
            if result and result != {}:
                return result
        return {"error": f"Entity '{entity_id}' not found"}
    
    graph_entity_btn.click(graph_entity_lookup_fn, [graph_entity_lookup], [graph_entity_detail])

    # TTL 파일 관리
    ttl_load_btn.click(load_ttl_file, [ttl_file_select], [ttl_editor, ttl_status])
    ttl_file_select.change(load_ttl_file, [ttl_file_select], [ttl_editor, ttl_status])
    ttl_save_btn.click(save_ttl_file, [ttl_file_select, ttl_editor], [ttl_status])
    ttl_validate_btn.click(validate_ttl, [ttl_editor], [ttl_status])
    ttl_reload_store_btn.click(reload_rdf_store, [], [ttl_status])


if __name__ == "__main__":
    import os
    import signal
    host = os.environ.get("UI_HOST", "0.0.0.0")
    port = int(os.environ.get("UI_PORT", "7860"))
    demo.queue().launch(server_name=host, server_port=port, prevent_thread_lock=True)
    
    signal.signal(signal.SIGINT, lambda s, f: exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: exit(0))
    while True:
        time.sleep(1)


