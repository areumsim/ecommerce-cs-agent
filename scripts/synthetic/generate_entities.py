import random
from rdflib import Graph, Namespace, URIRef, Literal

EX = Namespace("http://example.org/")

def generate_entities(n_customers=100, n_products=200):
    g = Graph()
    for i in range(n_customers):
        g.add((EX[f"Customer{i}"], EX.type, EX.Customer))
    for i in range(n_products):
        g.add((EX[f"Product{i}"], EX.type, EX.Product))
    return g

if __name__ == '__main__':
    g = generate_entities()
    g.serialize("data/synthetic_entities.ttl", format="turtle")
