# EVALUATION MODULE

Automated agent performance benchmarking with test scenarios.

## STRUCTURE

```
evaluation/
├── scenarios.py   # TestScenario dataclass, load_scenarios()
├── evaluator.py   # LLMEvaluator, RuleBasedEvaluator
├── benchmark.py   # BenchmarkRunner, BenchmarkResult
└── runner.py      # run_evaluation() CLI interface
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add test scenario | `scenarios.py` | Add to scenario YAML |
| Change scoring weights | `evaluator.py` | Modify score calculation |
| Add evaluation metric | `benchmark.py` | Add to `BenchmarkResult` |
| Run evaluation | `runner.py` | `python -m src.evaluation.runner` |

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `TestScenario` | Input, expected output, category, difficulty |
| `LLMEvaluator` | LLM-based response scoring |
| `RuleBasedEvaluator` | Deterministic keyword/pattern scoring |
| `BenchmarkRunner` | Orchestrates scenario execution |
| `BenchmarkResult` | Aggregated stats, latency percentiles |

## EVALUATION METRICS

| Metric | Range | Description |
|--------|-------|-------------|
| `relevance` | 0-1 | Response addresses query |
| `accuracy` | 0-1 | Facts are correct |
| `completeness` | 0-1 | All aspects covered |
| `tone` | 0-1 | Appropriate CS tone |
| `clarity` | 0-1 | Easy to understand |
| `overall` | 0-1 | Weighted average |

## BENCHMARK OUTPUT

```python
BenchmarkResult(
    total_scenarios=100,
    passed_scenarios=85,
    pass_rate=85.0,
    avg_latency_ms=450,
    p99_latency_ms=1200,
    category_pass_rate={"order": 90%, "claim": 80%},
)
```

## USAGE

```bash
# Run full benchmark
python scripts/09_run_evaluation.py

# Programmatic
from src.evaluation import run_evaluation
result = await run_evaluation(scenarios, evaluator)
```

## CONVENTIONS

- **Korean scenarios**: Test data in Korean
- **Async execution**: All evaluations are async
- **Idempotent**: Safe to re-run

## ANTI-PATTERNS

- **Don't hardcode scenarios** - load from YAML/JSON
- **Don't skip latency tracking** - always measure
