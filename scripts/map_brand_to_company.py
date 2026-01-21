from rdflib import Graph, Namespace, Literal
from src.rdf.repository import RDFRepository
from src.rdf.store import get_store

EX = Namespace("http://example.org/")

def map_brands():
    repo = RDFRepository(get_store())
    g = Graph()
    for p in repo.get_products(limit=200):
        if not p.brand:
            continue
        cid = p.brand.replace(" ", "_")
        company = EX[cid]
        g.add((company, EX.type, EX.Company))
        g.add((EX[p.product_id], EX.relatedCompany, company))
    return g

if __name__ == '__main__':
    g = map_brands()
    g.serialize("data/product_company_links.ttl", format="turtle")
