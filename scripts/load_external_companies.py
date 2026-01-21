from rdflib import Graph, Namespace, Literal
from datetime import datetime

EX = Namespace("http://example.org/")

def load_company(info: dict):
    g = Graph()
    cid = info.get("name", "Unknown").replace(" ", "_")
    company = EX[cid]
    g.add((company, EX.type, EX.Company))
    event = EX[f"Rel_{cid}"]
    g.add((event, EX.type, EX.CompanyRelationEvent))
    g.add((event, EX.subject, company))
    g.add((event, EX.source, Literal(info.get("source"))))
    g.add((event, EX.confidence, Literal(0.6)))
    g.add((event, EX.observedAt, Literal(datetime.utcnow().isoformat())))
    return g

if __name__ == '__main__':
    from crawl_wikipedia_companies import crawl_company
    info = crawl_company("Apple Inc.")
    g = load_company(info)
    g.serialize("data/external_company.ttl", format="turtle")
