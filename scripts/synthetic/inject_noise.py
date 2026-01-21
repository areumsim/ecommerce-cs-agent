import random
from rdflib import Graph, Namespace

EX = Namespace("http://example.org/")

def inject_conflicts(input_ttl: str, output_ttl: str, rate: float = 0.1):
    g = Graph()
    g.parse(input_ttl, format="turtle")
    triples = list(g)
    n_conflict = int(len(triples) * rate)
    for _ in range(n_conflict):
        s, p, o = random.choice(triples)
        g.add((s, EX.avoids, o))
    g.serialize(output_ttl, format="turtle")

if __name__ == '__main__':
    inject_conflicts(
        "data/synthetic_relations.ttl",
        "data/synthetic_relations_noisy.ttl",
        rate=0.15
    )
