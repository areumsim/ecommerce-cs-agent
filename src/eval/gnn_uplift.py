from src.recommendation.service import RecommendationService

class GNNUpliftEvaluator:
    def __init__(self, service: RecommendationService):
        self.service = service

    def uplift_at_k(self, user_id: str, ground_truth: set[str], k: int = 10):
        rule_only = self.service.recommend(user_id, use_gnn=False, k=k)
        rule_gnn = self.service.recommend(user_id, use_gnn=True, k=k)
        def hit(recs): return any(r in ground_truth for r in recs)
        return hit(rule_gnn) - hit(rule_only)
