# Legal Knowledge Graph for Reasoning

> Authority-weighted Knowledge Graph of Brazilian STJ jurisprudence,
> automatically extracted from Corpus927 and structured around the CDC
> article hierarchy.

---

## The Problem

Legal reasoning over Brazilian case law requires navigating hundreds of
judicial decisions with varying levels of authority — from isolated rulings
to binding constitutional precedents. A lawyer or reasoning system consulting
CDC Art. 18, for example, must know not just *which* decisions exist, but
*how much weight each carries* and *how they relate to each other*.

No structured, machine-readable representation of this hierarchy existed.

## What This Repository Does

This project builds that representation. It extracts, transforms, and
validates STJ jurisprudential data from **Corpus927** (ENFAM/STJ) into a
typed, weighted **Knowledge Graph (KG)** rooted at CDC articles. Every node
in the graph corresponds to a real legal entity — a provision, a binding
thesis, a leading case, an isolated ruling — and every edge encodes the type
and strength of its interpretive relationship with the article above it.

The result is a queryable graph that answers questions like:
- *What binding theses does the STJ apply to CDC Art. 18?*
- *Which leading case cluster has the most interpretive weight?*
- *Does any case cite Art. 27 CDC while reasoning about Art. 18?*

---

## Authority Hierarchy

Brazilian law imposes an explicit, institutional hierarchy of judicial
authority (CPC Arts. 1.036–1.041). The KG encodes this as five tiers:

| Tier | Node Type | Relationship | Weight |
|---|---|---|---|
| 1 — Constitutional Control | `ConstitutionalControl` | `CONTROLLED_BY` | 1.0 |
| 2 — STJ Editions | `STJThesis` | `SUMMARIZED_BY_STJ_THESIS` | 0.8–0.9 |
| 3 — Repetitive Topics (binding) | `RepetitiveTopic` | `INTERPRETED_BY_BINDING_THESIS` | 0.8–1.0 |
| 4 — Leading Cases | `Case` | `INTERPRETED_BY_LEADING_CASE` | log-normalized |
| 5 — Isolated Cases | `Case` | `INTERPRETED_BY_ISOLATED_CASE` | 0.3 |

Additional nodes model legal text structure (`LegalProvision`,
`LegalSubProvision`) and external citations found in full-text VOTOs
(`ExternalCitation`). The full schema covers **7 node labels** and
**9 relationship types**.

---

## Repository Structure

```
01_kg_pilot/                  ← Pipeline + outputs (active)
│   kg_pilot.py               ← Full pipeline (source of truth)
│   explore_api.ipynb         ← Interactive exploration notebook
│   discover_articles.py      ← Corpus927 coverage scan
│   output/
│       cdc_art1_30/          ← Arts. 1–30 CDC exports
│           kg_cdc_art1_30.json
│           kg_cdc_art1_30.graphml
│           neo4j_data_importer/   ← CSVs for Neo4j Data Importer UI
│           neo4j_admin/           ← CSVs for neo4j-admin CLI
│           neo4j_aura_import.cypher
│
02_authority_kg_verifier/     ← Research design (EMNLP/ACL 2026)
│   authority_kg_verifier_design.md
│
papers/                       ← Reference papers (ACL/EMNLP/NLLP 2025)
```

---

## Current State — Arts. 1–30 CDC

| Metric | Value |
|---|---|
| Nodes | 2,325 |
| Edges | 2,814 |
| Node labels | 7 |
| Relationship types | 9 |
| `ExternalCitation` nodes | 633 |
| `CITES_EXTERNAL` edges | 722 |
| Validations | 4 / 4 passing |

---

## Running the Pipeline

```bash
# Setup
source .venv/bin/activate   # Python 3.13.2

# Single article
cd 01_kg_pilot
python kg_pilot.py          # defaults to Art. 18 CDC

# Multiple articles
# Edit the article list in __main__ and call run_multi_article()
```

Outputs are written to `01_kg_pilot/output/`: JSON, GraphML, per-label
CSVs, and a ready-to-run Neo4j Aura Cypher script.

---

## Importing into Neo4j

Three import paths are supported:

| Method | Path | How |
|---|---|---|
| Neo4j Aura (Browser) | `neo4j_aura_import.cypher` | Run blocks sequentially in the Query tab |
| Neo4j Data Importer (UI) | `neo4j_data_importer/` | Drag-and-drop CSVs at data-importer.neo4j.io |
| neo4j-admin (CLI) | `neo4j_admin/` | `neo4j-admin database import` |

---

## Data Source

**Corpus927** — `https://corpus927.enfam.jus.br`
Institutional database maintained by ENFAM/STJ. Organizes STJ
jurisprudence by legal article across all five authority layers.
Requires Laravel session authentication, handled automatically by
`Corpus927Extractor`. Rate limit: 1 request/second.

---

## Research Direction

`02_authority_kg_verifier/` contains the design for a follow-on research
project targeting EMNLP/ACL 2026: using this KG as a **symbolic,
parameter-free verifier** of LLM legal reasoning chains — a method called
**Legal Groundedness Score (LGS)**. Implementation has not yet started.
See [`authority_kg_verifier_design.md`](02_authority_kg_verifier/authority_kg_verifier_design.md)
for the full specification.
