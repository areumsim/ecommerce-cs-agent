from src.rdf.relation_query import RelationQuery
from src.rdf.repository import RDFRepository

class RulePrecisionEvaluator:
    def __init__(self, repo: RDFRepository):
        self.repo = repo

    def evaluate(self, derived_type: str, ground_truth_type: str, min_confidence: float = 0.7):
        derived = self.repo.get_relations(RelationQuery(
            relation_type=derived_type,
            min_confidence=min_confidence,
            derived_only=True
        ))
        ground = self.repo.get_relations(RelationQuery(
            relation_type=ground_truth_type,
            include_derived=False
        ))
        gt_pairs = {(r.subject, r.object) for r in ground}
        correct = sum(1 for r in derived if (r.subject, r.object) in gt_pairs)
        precision = correct / len(derived) if derived else 0.0
        recall = correct / len(gt_pairs) if gt_pairs else 0.0
        return precision, recall
