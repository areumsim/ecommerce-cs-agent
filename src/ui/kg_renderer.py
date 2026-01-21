"""Render Customer-Order-Product knowledge graph as SVG using Mermaid."""
from src.rdf.repository import RDFRepository
from src.rdf.store import get_store


def render_customer_order_product_mermaid(customer_id: str | None = None) -> str:
    repo = RDFRepository(get_store())

    customers = [customer_id] if customer_id else [c.customer_id for c in repo.get_customers(limit=3)]

    edges = []
    nodes = set()

    for cid in customers:
        orders = repo.get_customer_orders(cid, limit=5)
        nodes.add((cid, "customer"))
        for o in orders:
            oid = o.order_id
            nodes.add((oid, "order"))
            edges.append((cid, oid, "placesOrder"))
            items = repo.get_order_items(oid)
            for it in items:
                pid = it.product_id
                nodes.add((pid, "product"))
                edges.append((oid, pid, "hasItem"))

    lines = ["flowchart LR"]
    lines += [
        "classDef customer fill:#2563eb,color:#fff,font-weight:bold",
        "classDef order fill:#f97316,color:#fff,font-weight:bold",
        "classDef product fill:#16a34a,color:#fff,font-weight:bold",
    ]

    for nid, typ in nodes:
        safe_id = nid.replace('-', '_')
        lines.append(f"{safe_id}[{nid}]:::{typ}")

    for s, o, r in edges:
        s_id = s.replace('-', '_')
        o_id = o.replace('-', '_')
        lines.append(f"{s_id} -->|{r}| {o_id}")

    return "\n".join(lines)
