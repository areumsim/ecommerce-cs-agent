from src.graphrag.context import build_explanation_context

class ExplanationCoverageEvaluator:
    def coverage(self, entity_id: str):
        ctx = build_explanation_context(entity_id)
        return {
            'relations_used': len(ctx.relations_used),
            'rules_used': len(ctx.rules_used),
            'missing_hops': ctx.missing_hops,
            'coverage_score': 1.0 if ctx.missing_hops == 0 else 0.5
        }
