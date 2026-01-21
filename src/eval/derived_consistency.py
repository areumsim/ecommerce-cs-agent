from collections import defaultdict
from src.rdf.relation_query import RelationQuery
from src.rdf.repository import RDFRepository

class DerivedConsistencyEvaluator:
    def __init__(self, repo: RDFRepository):
        self.repo = repo

    def conflict_rate(self, derived_types: list[str]):
        relations = []
        for t in derived_types:
            relations.extend(self.repo.get_relations(RelationQuery(
                relation_type=t,
                derived_only=True
            )))
        pair_map = defaultdict(set)
        for r in relations:
            pair_map[(r.subject, r.object)].add(r.relation_type)
        conflicts = sum(1 for v in pair_map.values() if len(v) > 1)
        total = len(pair_map)
        return conflicts / total if total else 0.0
