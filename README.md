# Linkup vs Perplexity — Benchmark Report

Two-part evaluation comparing Linkup and Perplexity across both output modes: **sourced answers** (LLM-generated) and **raw search results**.

---

## Part 1: Sourced Answers (LLM-Generated)

**238 queries** (75 SimpleQA + 163 production) comparing Linkup Standard (`sourcedAnswer`) vs Perplexity Sonar and Sonar Pro.

Production queries span 10 categories from real Linkup customer organizations: company research, place verification, multilingual queries, deep research, classification, and more.

### Providers
| Provider | Mode | Pricing |
|---|---|---|
| Linkup Standard | `sourcedAnswer` | €0.005/query (flat) |
| Perplexity Sonar | `sonar` model | $1/$1 per M tokens + $5/1K requests |
| Perplexity Sonar Pro | `sonar-pro` model | $3/$15 per M tokens + $6/1K requests |

### SimpleQA Accuracy (75 queries with ground truth)

| Provider | Exact Match | Rate |
|---|---|---|
| **Linkup Standard** | 51/75 | **68%** |
| Perplexity Sonar | 42/75 | 56% |
| Perplexity Sonar Pro | 40/75 | 53% |

### LLM Judge Quality (163 production queries)

| Provider | Avg Score |
|---|---|
| **Linkup Standard** | **4.12 / 5** |
| Perplexity Sonar Pro | 3.86 / 5 |
| Perplexity Sonar | 3.85 / 5 |

### Head-to-Head (163 production queries)

| Matchup | W / T / L |
|---|---|
| Linkup vs Sonar | **44W** / 78T / 31L |
| Linkup vs Sonar Pro | **39W** / 83T / 28L |

### Cost & Latency

| Provider | Avg Cost/Query | Avg Latency |
|---|---|---|
| Perplexity Sonar | $0.0053 | 4.08s |
| **Linkup Standard** | $0.0058 | 4.36s |
| Perplexity Sonar Pro | $0.0098 | 4.20s |

### Eval Method
- **Judge:** Claude Opus 4.6
- **Method:** Side-by-side comparison of all three answers per query
- **Criteria:** Relevance, Accuracy, Completeness, Usefulness (each 1-5)
- **Overall:** Holistic score weighted toward accuracy and relevance

---

## Part 2: Search Results (Raw)

**250 queries** (114 coding agent + 136 end user app) comparing Linkup Standard (`searchResults`) vs Perplexity Search API (`/search`).

### Providers
| Provider | Mode | Pricing |
|---|---|---|
| Linkup Standard | `searchResults` | €0.005/query (flat) |
| Perplexity Search API | `/search` (max_results=20) | $5/1K requests (flat) |

### Weighted Quality Score

| Provider | **Score** | Relevance | Source Quality | Coverage | Freshness | Agent Use |
|---|---|---|---|---|---|---|
| **Linkup** | **4.528** | **4.73** | **4.41** | **4.43** | **4.44** | **4.40** |
| Perplexity | 4.331 | 4.55 | 4.21 | 4.25 | 4.13 | 4.22 |

### Head-to-Head

| | Count | % |
|---|---|---|
| **Linkup wins** | **130** | **52%** |
| Perplexity wins | 91 | 36% |
| Ties | 29 | 12% |

### By Category

| Category | Linkup | Perplexity | Linkup W / Pplx W |
|---|---|---|---|
| **Coding Agent** (114q) | **4.349** | 3.972 | 74 / 34 |
| **End User App** (136q) | **4.678** | 4.632 | 56 / 57 |

### Latency

| Provider | Avg | p50 | p95 |
|---|---|---|---|
| Linkup | 2,368ms | 1,730ms | 3,619ms |
| Perplexity | 546ms | 518ms | 724ms |

### Eval Method
- **Judge:** Claude Haiku 4.5
- **Method:** Pairwise A/B with randomized label assignment (seed=42) to avoid position bias
- **Criteria:** Relevance (35%), Source Quality (25%), Coverage (20%), Freshness (10%), AI Agent Usefulness (10%)
- **Weighted score:** `0.35×relevance + 0.25×source_quality + 0.20×coverage + 0.10×freshness + 0.10×agent_usefulness`

---

## Repository Structure

```
├── README.md
├── Linkup_vs_Perplexity_Benchmark.xlsx
├── Linkup_vs_Perplexity_Benchmark.csv
├── sourced-answer/
│   ├── queries.json              ← 238 queries (75 SimpleQA + 163 production)
│   ├── results.json              ← Full answers + grades + costs from all 3 providers
│   ├── llm_judge_scores.csv      ← Per-query quality scores (163 production queries)
│   └── eval_config.json          ← Eval prompt, model, criteria, provider config
└── search-results/
    ├── queries.json              ← 250 queries (coding agent + end user app)
    ├── search_results_raw.json   ← Full search results from both providers
    ├── llm_judge_scores.json     ← Pairwise judge scores with per-criterion breakdown
    └── eval_config.json          ← Eval prompt, model, criteria, weights
```

## Key Findings

1. **Sourced answers:** Linkup is 12pp more accurate on factual QA (68% vs 56%) and scores 4.12/5 vs 3.85/5 on production queries
2. **Search results:** Linkup wins 52% of head-to-head comparisons vs 36% for Perplexity
3. **Cost:** Linkup and Sonar are nearly identical (~$0.005/query); Sonar Pro costs ~2x more
4. **Latency:** Perplexity is faster on raw search (546ms vs 2.4s); comparable on sourced answers
5. **Pricing:** Linkup is flat and predictable; Perplexity varies by query complexity

## Date
April 2026
