# SCRIPTS MODULE

Numbered data pipeline for CSV → RDF → Fuseki.

## PIPELINE ORDER

| # | Script | Purpose |
|---|--------|---------|
| 00 | `download_base_model.py` | Sentence-transformers model |
| 01 | `download_data.py` | Raw Amazon data |
| 01a | `crawl_policies.py` | Policy document crawling |
| 01b | `fetch_policies.py` | Policy document fetching |
| 02 | `full_preprocess_stream.py` | Data preprocessing |
| 03 | `generate_mock_csv.py` | Generate mock CSV data |
| 03a | `expand_mock_data.py` | Expand mock dataset |
| 04 | `build_index.py` | RAG index (FAISS + text) |
| 05 | `migrate_to_sqlite.py` | CSV → SQLite migration |
| 08 | `e2e_order_claim.py` | E2E order/claim test |
| 09 | `run_evaluation.py` | Model evaluation |
| 12 | `generate_mock_ttl.py` | CSV → TTL conversion |
| 14 | `test_rdf_store.py` | RDF store tests |
| 15 | `generate_embeddings.py` | Product embeddings |

## COMMON WORKFLOWS

```bash
# Full data regeneration
python scripts/03_generate_mock_csv.py
python scripts/12_generate_mock_ttl.py
python scripts/15_generate_embeddings.py

# Load to Fuseki
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' -u admin:admin123 \
    -H 'Content-Type: text/turtle' --data-binary @"$f"
done

# RAG index rebuild
python scripts/04_build_index.py
```

## KEY SCRIPTS

| Script | Input | Output |
|--------|-------|--------|
| `03_generate_mock_csv.py` | - | `data/mock_csv/*.csv` |
| `12_generate_mock_ttl.py` | `data/mock_csv/` | `ontology/instances/*.ttl` |
| `15_generate_embeddings.py` | Products | `ontology/instances/embeddings.ttl` |

## CONVENTIONS

- **Numbered prefix**: Execution order (not all sequential)
- **Idempotent**: Safe to re-run
- **Logging**: Use `logging` module, not print

## ANTI-PATTERNS

- **Don't skip dependencies** - run in order when needed
- **Don't commit generated data** - regenerate from scripts
