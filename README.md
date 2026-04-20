# Legal Knowledge Graph for Reasoning

Research project building an authority-weighted Knowledge Graph of Brazilian jurisprudence (STJ/STF) to support legal reasoning over the Consumer Defense Code (CDC).

## Structure

- `01_kg_pilot/` — Pilot: KG pipeline for Consumer Protection Code
- `02_authority_kg_verifier/` — Research design: KG as a symbolic verifier for LLM reasoning chains

## Pilot Overview

Extracts all jurisprudential layers from [Corpus927](https://corpus927.enfam.jus.br) (ENFAM/STJ) and builds a typed, weighted KG with 6 authority levels:

| Layer | Node Type | Weight |
|---|---|---|
| Constitutional Control (ADI/ADC/ADPF) | `ConstitutionalControl` | 1.00 |
| STF Repercussão Geral | `RG_STF` | 0.95 |
| STJ Repetitive Topics (Temas) | `RepetitiveTopic` | 0.90 |
| STJ Theses in Editions | `STJThesis` | 0.80 |
| Leading Cases (log-normalized) | `Case` | varies |
| Isolated Cases | `Case` | 0.30 |


