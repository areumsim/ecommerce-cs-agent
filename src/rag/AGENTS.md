# RAG MODULE

Policy document retrieval with keyword/embedding/hybrid search.

## STRUCTURE

```
rag/
├── retriever.py   # PolicyRetriever: main search interface
├── embedder.py    # Embedder: sentence-transformers wrapper
├── indexer.py     # Index builder (text + FAISS)
└── reranker.py    # Optional reranking (heuristic fallback)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Change search mode | `configs/rag.yaml` | `retrieval.mode: keyword|embedding|hybrid` |
| Adjust hybrid weight | `configs/rag.yaml` | `retrieval.hybrid_alpha` (0=keyword, 1=embedding) |
| Add embedding model | `embedder.py` | Update `Embedder.encode_query()` |
| Modify ranking | `retriever.py` | `_keyword_search()`, `_embedding_search()` |
| Build index | `scripts/04_build_index.py` | Reads `data/processed/policies.jsonl` |

## FLOW

```
query
  ↓
PolicyRetriever.search_policy(query, top_k)
  ├── keyword: TF scoring + length normalization
  ├── embedding: FAISS cosine similarity
  └── hybrid: weighted combination (alpha)
  ↓
Optional reranking (query-title overlap boost)
  ↓
List[PolicyHit(id, score, text, metadata)]
```

## CONVENTIONS

- **Lazy loading**: FAISS index, embedder loaded on first search
- **Auto-fallback**: if FAISS unavailable → keyword mode
- **Min score filter**: `retrieval.min_score` in config (default 0.0)

## ANTI-PATTERNS

- **Don't import faiss at module level**: wrapped in try/except for optional dependency
- **Don't cache embeddings**: query embeddings computed per-request
