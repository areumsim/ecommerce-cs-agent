#!/usr/bin/env python3
"""
Fuseki에서 시각화 데이터 추출 → JSON 파일 생성

사용법:
    python scripts/export_visualization_data.py
    python scripts/export_visualization_data.py --sample-size 50
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent


def decode_embedding(base64_str: str) -> np.ndarray:
    """Base64 임베딩을 numpy 배열로 디코딩"""
    raw = base64.b64decode(base64_str)
    return np.frombuffer(raw, dtype=np.float32)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """코사인 유사도 계산"""
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    return float(dot / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0


sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "data" / "visualization"


def get_store():
    from src.rdf.store import get_store
    return get_store()


def export_ontology_schema() -> dict:
    from rdflib import OWL, RDF, RDFS, Graph, Namespace

    ECOM = Namespace("http://example.org/ecommerce#")
    graph = Graph()
    graph.parse(PROJECT_ROOT / "ontology" / "ecommerce.ttl", format="turtle")

    nodes = []
    edges = []
    class_ids = {}

    # Category 클래스들 (Category와 그 서브클래스들)
    category_classes = {"Category", "Electronics", "MobilePhone", "Laptop", "Audio", "Accessories", "General"}

    for cls in graph.subjects(RDF.type, OWL.Class):
        name = str(cls).split("#")[-1]
        if name.startswith("_"):
            continue
        label = name
        for l in graph.objects(cls, RDFS.label):
            if hasattr(l, "language") and l.language == "ko":
                label = str(l)
                break
        class_ids[str(cls)] = name

        # 카테고리 클래스인지 일반 클래스인지 구분
        group = "category" if name in category_classes else "class"
        title_prefix = "카테고리" if name in category_classes else "클래스"

        nodes.append({
            "id": name,
            "label": label,
            "group": group,
            "title": f"{title_prefix}: {name}",
        })

    # 카테고리 계층 구조 추가 (subClassOf 관계)
    for subclass in graph.subjects(RDFS.subClassOf, None):
        subclass_name = str(subclass).split("#")[-1]
        if subclass_name.startswith("_") or subclass_name not in category_classes:
            continue
        for superclass in graph.objects(subclass, RDFS.subClassOf):
            superclass_name = str(superclass).split("#")[-1]
            if superclass_name in category_classes:
                edges.append({
                    "from": subclass_name,
                    "to": superclass_name,
                    "label": "하위 카테고리",
                    "arrows": "to",
                    "color": "#cba6f7",
                    "dashes": True,
                })

    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        name = str(prop).split("#")[-1]
        domain = None
        range_ = None
        for d in graph.objects(prop, RDFS.domain):
            domain = str(d).split("#")[-1]
        for r in graph.objects(prop, RDFS.range):
            range_ = str(r).split("#")[-1]

        if domain and range_ and domain in [n["id"] for n in nodes] and range_ in [n["id"] for n in nodes]:
            label = name
            for l in graph.objects(prop, RDFS.label):
                if hasattr(l, "language") and l.language == "ko":
                    label = str(l)
                    break

            is_symmetric = (prop, RDF.type, OWL.SymmetricProperty) in graph

            # inCategory 관계는 다른 색상 사용
            color = "#f9e2af" if name == "inCategory" else "#78e08f"

            edges.append({
                "from": domain,
                "to": range_,
                "label": label,
                "arrows": "to" if not is_symmetric else "to, from",
                "color": color,
            })

    return {"nodes": nodes, "edges": edges, "type": "ontology_schema"}


def export_instance_graph(sample_size: int = 0) -> dict:
    """인스턴스 그래프 내보내기. sample_size=0이면 전체 데이터."""
    store = get_store()
    if not store:
        return {"nodes": [], "edges": [], "type": "instance_graph", "error": "Store not available"}

    nodes = []
    edges = []
    node_ids = set()

    # sample_size=0이면 전체, 아니면 LIMIT 적용
    limit_clause = "" if sample_size == 0 else f"LIMIT {sample_size}"

    customers_query = f"""
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?cid ?name ?level WHERE {{
        ?c a ecom:Customer ;
           ecom:customerId ?cid ;
           ecom:name ?name ;
           ecom:membershipLevel ?level .
    }} {limit_clause}
    """

    for row in store.query(customers_query):
        cid = str(row.get("cid") if isinstance(row, dict) else row.cid)
        name = str(row.get("name") if isinstance(row, dict) else row.name)
        level = str(row.get("level") if isinstance(row, dict) else row.level)
        node_ids.add(cid)
        nodes.append({
            "id": cid,
            "label": name[:10],
            "group": "customer",
            "title": f"고객: {name}\n등급: {level}",
            "level": level,
        })

    # 주문: 전체 또는 고객 수 * 10
    order_limit = "" if sample_size == 0 else f"LIMIT {sample_size * 10}"
    orders_query = f"""
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?oid ?cid ?status ?amount WHERE {{
        ?customer a ecom:Customer ;
                  ecom:customerId ?cid ;
                  ecom:placedOrder ?o .
        ?o ecom:orderId ?oid ;
           ecom:status ?status ;
           ecom:totalAmount ?amount .
    }} {order_limit}
    """

    order_ids = set()
    for row in store.query(orders_query):
        oid = str(row.get("oid") if isinstance(row, dict) else row.oid)
        cid = str(row.get("cid") if isinstance(row, dict) else row.cid)
        status = str(row.get("status") if isinstance(row, dict) else row.status)
        amount = float(row.get("amount") if isinstance(row, dict) else row.amount)
        if cid not in node_ids:
            continue
        order_ids.add(oid)
        node_ids.add(oid)
        nodes.append({
            "id": oid,
            "label": oid[-8:],
            "group": "order",
            "title": f"주문: {oid}\n상태: {status}\n금액: ₩{amount:,.0f}",
            "status": status,
        })
        edges.append({
            "from": cid,
            "to": oid,
            "label": "주문",
            "color": "#54a0ff",
        })

    # 상품: 전체 또는 고객 수 * 20
    product_limit = "" if sample_size == 0 else f"LIMIT {sample_size * 20}"
    products_query = f"""
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT DISTINCT ?pid ?title ?price ?oid WHERE {{
        ?order ecom:orderId ?oid ;
               ecom:containsItem ?item .
        ?item ecom:hasProduct ?product .
        ?product ecom:productId ?pid ;
                 ecom:title ?title ;
                 ecom:price ?price .
    }} {product_limit}
    """

    for row in store.query(products_query):
        pid = str(row.get("pid") if isinstance(row, dict) else row.pid)
        oid = str(row.get("oid") if isinstance(row, dict) else row.oid)
        title = str(row.get("title") if isinstance(row, dict) else row.title)
        price = float(row.get("price") if isinstance(row, dict) else row.price)
        if oid not in order_ids:
            continue
        if pid not in node_ids:
            node_ids.add(pid)
            nodes.append({
                "id": pid,
                "label": title[:12] + "...",
                "group": "product",
                "title": f"상품: {title}\n가격: ₩{price:,.0f}",
            })
        edges.append({
            "from": oid,
            "to": pid,
            "label": "",
            "color": "#ffeaa7",
            "dashes": True,
        })

    return {"nodes": nodes, "edges": edges, "type": "instance_graph"}


def export_similarity_graph(sample_size: int = 0) -> dict:
    """유사도 그래프 내보내기. sample_size=0이면 전체 데이터."""
    store = get_store()
    if not store:
        return {"nodes": [], "edges": [], "type": "similarity_graph", "error": "Store not available"}

    nodes = []
    edges = []
    node_ids = set()
    edge_set = set()  # 중복 엣지 방지

    limit_clause = "" if sample_size == 0 else f"LIMIT {sample_size}"

    # 1. 모든 임베딩 로드
    embeddings_query = """
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?pid ?emb WHERE {
        ?p a ecom:Product ;
           ecom:productId ?pid ;
           ecom:embedding ?emb .
    }
    """
    embeddings = {}
    try:
        for row in store.query(embeddings_query):
            def get_val(key):
                return row.get(key) if isinstance(row, dict) else getattr(row, key, None)
            pid = str(get_val("pid"))
            emb = get_val("emb")
            if emb:
                try:
                    embeddings[pid] = decode_embedding(str(emb))
                except Exception:
                    pass
    except Exception:
        pass

    # 2. 유사도 관계 및 상품 정보 조회
    query = f"""
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?pid1 ?title1 ?price1 ?pid2 ?title2 ?price2 WHERE {{
        ?p1 ecom:productId ?pid1 ;
            ecom:title ?title1 ;
            ecom:price ?price1 ;
            ecom:similarTo ?p2 .
        ?p2 ecom:productId ?pid2 ;
            ecom:title ?title2 ;
            ecom:price ?price2 .
    }} {limit_clause}
    """

    for row in store.query(query):
        def get_val(key):
            return row.get(key) if isinstance(row, dict) else getattr(row, key, None)

        pid1, pid2 = str(get_val("pid1")), str(get_val("pid2"))
        title1 = str(get_val("title1") or "")
        title2 = str(get_val("title2") or "")
        price1 = float(get_val("price1") or 0)
        price2 = float(get_val("price2") or 0)

        # 노드 추가
        if pid1 not in node_ids:
            node_ids.add(pid1)
            nodes.append({
                "id": pid1,
                "label": title1[:15],
                "group": "product",
                "title": f"{title1}\n₩{price1:,.0f}",
            })

        if pid2 not in node_ids:
            node_ids.add(pid2)
            nodes.append({
                "id": pid2,
                "label": title2[:15],
                "group": "product",
                "title": f"{title2}\n₩{price2:,.0f}",
            })

        # 3. 코사인 유사도 계산
        score = 0.0
        if pid1 in embeddings and pid2 in embeddings:
            score = cosine_similarity(embeddings[pid1], embeddings[pid2])

        # 중복 엣지 방지 (정렬된 튜플로 체크)
        edge_key = tuple(sorted([pid1, pid2]))
        if edge_key not in edge_set:
            edge_set.add(edge_key)

            # 점수에 따른 엣지 두께 및 색상 (점수 높을수록 진한 색)
            width = 1 + score * 4
            color = f"rgba(253, 121, 168, {0.4 + score * 0.6:.2f})"

            edges.append({
                "from": pid1,
                "to": pid2,
                "label": f"{score:.2f}" if score > 0 else "",
                "color": color,
                "width": width,
                "score": score,  # 필터링용 점수 필드
                "title": f"{title1[:20]} ↔ {title2[:20]}\n유사도: {score:.3f}",
            })

    # 점수 기준으로 정렬 (높은 점수 우선)
    edges.sort(key=lambda e: e.get("score", 0), reverse=True)

    return {"nodes": nodes, "edges": edges, "type": "similarity_graph"}


def export_stats() -> dict:
    store = get_store()
    if not store:
        return {"error": "Store not available"}

    stats = {
        "customers": 0,
        "products": 0,
        "orders": 0,
        "tickets": 0,
        "similarities": 0,
        "triples": store.triple_count if hasattr(store, "triple_count") else 0,
        "updated_at": datetime.now().isoformat(),
    }

    count_query = """
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT 
        (COUNT(DISTINCT ?c) as ?customers)
        (COUNT(DISTINCT ?p) as ?products)
        (COUNT(DISTINCT ?o) as ?orders)
        (COUNT(DISTINCT ?t) as ?tickets)
    WHERE {
        { ?c a ecom:Customer }
        UNION { ?p a ecom:Product }
        UNION { ?o a ecom:Order }
        UNION { ?t a ecom:Ticket }
    }
    """

    try:
        for row in store.query(count_query):
            def get_val(key):
                return row.get(key) if isinstance(row, dict) else getattr(row, key, 0)
            stats["customers"] = int(get_val("customers") or 0)
            stats["products"] = int(get_val("products") or 0)
            stats["orders"] = int(get_val("orders") or 0)
            stats["tickets"] = int(get_val("tickets") or 0)
    except:
        pass

    sim_query = """
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT (COUNT(*) as ?cnt) WHERE { ?p1 ecom:similarTo ?p2 }
    """
    try:
        for row in store.query(sim_query):
            cnt = row.get("cnt") if isinstance(row, dict) else getattr(row, "cnt", 0)
            stats["similarities"] = int(cnt or 0)
    except:
        pass

    return stats


def main():
    parser = argparse.ArgumentParser(description="시각화 데이터 추출")
    parser.add_argument("--sample-size", type=int, default=0, help="샘플 크기 (0=전체)")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="출력 디렉토리")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    print("시각화 데이터 추출 시작...")

    print("  1/4 온톨로지 스키마...")
    schema = export_ontology_schema()
    (args.output / "ontology_schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      → 노드 {len(schema['nodes'])}개, 엣지 {len(schema['edges'])}개")

    print("  2/4 인스턴스 그래프...")
    instance = export_instance_graph(args.sample_size)
    (args.output / "instance_graph.json").write_text(
        json.dumps(instance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      → 노드 {len(instance['nodes'])}개, 엣지 {len(instance['edges'])}개")

    print("  3/4 유사도 그래프...")
    similarity = export_similarity_graph(args.sample_size)
    (args.output / "similarity_graph.json").write_text(
        json.dumps(similarity, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      → 노드 {len(similarity['nodes'])}개, 엣지 {len(similarity['edges'])}개")

    print("  4/4 통계 정보...")
    stats = export_stats()
    (args.output / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      → {stats}")

    print(f"\n완료! 출력 디렉토리: {args.output}")


if __name__ == "__main__":
    main()
