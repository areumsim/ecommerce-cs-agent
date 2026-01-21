import json
from datetime import datetime
from pathlib import Path
from src.eval.rule_precision import RulePrecisionEvaluator
from src.eval.derived_consistency import DerivedConsistencyEvaluator
from src.rdf.repository import RDFRepository
from src.rdf.store import get_store

OUT = Path("data/eval_runs")
OUT.mkdir(exist_ok=True)

repo = RDFRepository(get_store())
rule_eval = RulePrecisionEvaluator(repo)
consistency_eval = DerivedConsistencyEvaluator(repo)

DERIVED_TYPES = [
    "PreferenceRelation",
    "AvoidanceRelation",
    "BiasRiskRelation",
]

for t in DERIVED_TYPES:
    precision, recall = rule_eval.evaluate(t, "PurchaseRelation")
    conflict = consistency_eval.conflict_rate([t])
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "derived_type": t,
        "precision": precision,
        "recall": recall,
        "conflict_rate": conflict,
    }
    out = OUT / f"{t}_{int(datetime.utcnow().timestamp())}.json"
    out.write_text(json.dumps(record, indent=2))
    print(f"Saved {out}")
