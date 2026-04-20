# Legal KG for Reasoning — Progress Report
**Date:** March 13, 2026 | **Status:** Pilot completed (Art. 18 CDC)

---

## Conceptualization

### Problem
Legal reasoning over Brazilian case law requires navigating hundreds of judicial decisions with varying levels of authority — from isolated rulings to binding constitutional precedents. No structured representation exists to connect a legal provision to the body of jurisprudence that interprets it.

### Design Approach
The project models legal argumentation as a **directed Knowledge Graph** rooted at a legal article. Each node represents an entity in the legal reasoning chain; each edge represents the *type* and *strength* of the interpretive relationship.

The central design decision was to organize jurisprudence into **5 authority layers**, reflecting the actual hierarchy of Brazilian judicial precedent:

```
Legal Provision (Art. 18 CDC)
    │
    ├── Constitutional Control  (ADI/ADC/ADPF)         → validity of the norm
    ├── STJ Theses in Editions  (curated summaries)    → doctrinal synthesis
    ├── Repetitive Topics       (binding thesis)        → canonical interpretation
    ├── Leading Cases           (cluster representatives) → dominant case law
    └── Isolated Cases          (individual decisions)  → long tail
```

Each layer receives a distinct **edge relation type** and a **quantitative authority weight**, allowing downstream reasoning systems to rank and filter interpretations by legal force.

### Data Source
**Corpus927** (ENFAM/STJ) — an institutional database that organizes STJ jurisprudence by legal article, providing all five layers through a single API endpoint. This alignment between the data structure and our graph model was the key technical fit for this pilot.

---

## Pipeline Overview

```
Corpus927 API
     │
     ▼
[1] Extract       Authenticated GET → full JSON with all 5 layers
     │
     ▼
[2] Transform     JSON → typed nodes + weighted edges (KGTransformer)
     │
     ▼
[3] NLP (opt.)    Citation extraction from full-text decisions
     │
     ▼
[4] Validate      4 symbolic checks (binding thesis, weights, typing, provenance)
     │
     ▼
[5] Export        kg_pilot_art18.json  +  kg_pilot_art18.graphml
```

---

## What Was Built

### Authority Layers → Graph Edges

| Layer | Node Type | Edge Relation | Weight |
|---|---|---|---|
| Constitutional Control | `ConstitutionalControl` | `CONTROLLED_BY` | 1.0 |
| STJ Theses (Editions) | `STJThesis` | `SUMMARIZED_BY_STJ_THESIS` | 0.9 |
| Repetitive Topics | `RepetitiveTopic` | `INTERPRETED_BY_BINDING_THESIS` | 0.8 – 1.0 |
| Leading Cases | `Case` | `INTERPRETED_BY_LEADING_CASE` | log-normalized |
| Isolated Cases | `Case` | `INTERPRETED_BY_CASE` | 0.3 |

Leading case weights use logarithmic normalization over the count of similar decisions, preventing high-volume clusters from dominating linearly.

### Key Files

| File | Role |
|---|---|
| `kg_pilot.py` | Full pipeline: extractor, transformer, NLP, graph, export |
| `explore_api.ipynb` | Step-by-step interactive testing and inspection notebook |

---

## Current Scope

- **Article:** Art. 18 CDC (Consumer Defense Code) — product liability
- **Court:** STJ (Superior Tribunal de Justiça)
- **Outputs:** JSON + GraphML, ready for Gephi/Cytoscape visualization

---

## Next Steps

1. Validate node/edge quality from the pilot outputs
2. Expand to additional CDC articles
3. Activate LLM citation classifier (`classify_citations_llm` — implemented, pending)
4. Design reasoning layer on top of the KG
