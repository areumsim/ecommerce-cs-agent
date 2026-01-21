import random
from rdflib import Graph, Namespace, URIRef, Literal

EX = Namespace("http://example.org/")

def generate_relations(n_relations=500):
    g = Graph()
    for i in range(n_relations):
        c = EX[f"Customer{random.randint(0,99)}"]
        p = EX[f"Product{random.randint(0,199)}"]
        g.add((c, EX.purchased, p))
    return g

if __name__ == '__main__':
    g = generate_relations()
    g.serialize("data/synthetic_relations.ttl", format="turtle")
