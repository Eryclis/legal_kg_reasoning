"""
Corpus927 KG Pilot — Art. 18 CDC
Pipeline orchestrator: Extract → Transform → NLP → Validate → Export
"""

import json
import os
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime

import networkx as nx

from config import NORMA_ID, ARTIGO_ID, BASE_URL
from export_csv import export_neo4j_csv, export_data_importer_csv
from extractor import Corpus927Extractor
from graph import build_networkx_graph, print_graph_summary
from models import NormaNode, NormaSubNode, CaseNode, Edge
from nlp import extract_citations, resolve_citations, segment_full_text
from transformer import KGTransformer


def run_pilot(fetch_full_text: bool = False) -> tuple[dict, list[Edge], nx.DiGraph]:
    extractor = Corpus927Extractor()
    nlp_edges: list[Edge] = []

    # ── Step 1: Fetch API data ────────────────────────────────────
    print(f"[Step 1] Fetching jurisprudencia for nrm:{NORMA_ID}|art:{ARTIGO_ID}...")
    api_data = extractor.fetch_jurisprudencia(NORMA_ID, ARTIGO_ID)

    jurs     = api_data.get("jurisprudencias", {})
    temas    = api_data.get("temas", {})
    grouped  = api_data.get("posicionamentos_agrupados_stj", [])
    isolated = api_data.get("posicionamentos_isolados_stj", [])

    print(f"  Constitutional Control (type 90)  : {len(jurs.get('90', []))}")
    print(f"  RG_STF (type 70)                  : {len(jurs.get('70', []))}")
    print(f"  STJ Theses (type 110)             : {len(jurs.get('110', []))}")
    print(f"  Repetitive Topics (key '60')      : {len(temas.get('60', []))}")
    print(f"  Grouped positions                 : {len(grouped)}")
    print(f"  Isolated positions                : {len(isolated)}")

    # ── Step 1b: Fetch article text ───────────────────────────────
    print(f"\n[Step 1b] Parsing article text from legislation page...")
    article_data = extractor.fetch_article_text(NORMA_ID, ARTIGO_ID)
    if article_data:
        total_incises = sum(len(v) for v in article_data["incises"].values())
        print(f"  Caput     : {article_data['caput'][:70]}...")
        print(f"  Paragraphs: {len(article_data['paragraphs'])}")
        print(f"  Incises   : {total_incises}")
    else:
        print("  WARNING: Could not extract article text from legislation page")

    # ── Step 2: Transform → KG ────────────────────────────────────
    print("\n[Step 2] Building Knowledge Graph...")
    norma_node  = NormaNode(node_id="CDC_art18", law="CDC", article=18)
    transformer = KGTransformer(norma_node)
    nodes, edges = transformer.build(api_data)
    print(f"  Nodes : {len(nodes)}")
    print(f"  Edges : {len(edges)}")

    # ── Step 2b: Expand into sub-article nodes ────────────────────
    print("\n[Step 2b] Expanding NormaNode into sub-article nodes...")
    transformer.populate_norma_sub_nodes(article_data)
    nodes = transformer.nodes
    edges = transformer.edges
    sub_nodes = [n for n in nodes.values() if isinstance(n, NormaSubNode)]
    print(
        f"  Sub-nodes added : {len(sub_nodes)}"
        f"  ({sum(1 for n in sub_nodes if n.sub_type == 'paragraph')} paragraphs, "
        f"{sum(1 for n in sub_nodes if n.sub_type == 'incise')} incises)"
    )
    print(f"  Total nodes now : {len(nodes)}")

    # ── Step 3: NLP enrichment (optional) ────────────────────────
    if fetch_full_text:
        print("\n[Step 3] Fetching full text + extracting citations (top-5 leading cases)...")
        top5 = sorted(grouped, key=lambda x: x.get("semelhantes", 0), reverse=True)[:5]
        raw_cit_edges: list[Edge] = []
        for item in top5:
            hash_it = item.get("hash_it", "")
            if not hash_it:
                continue
            title = item.get("titulo", hash_it)
            print(f"  Fetching: {title[:60]}...")
            full_text = extractor.fetch_full_text(hash_it)
            if full_text:
                case_id   = transformer._make_case_id(title)
                segments  = segment_full_text(full_text)
                vote_text = segments.get("vote") or full_text
                cit_edges = extract_citations(vote_text, case_id)
                raw_cit_edges.extend(cit_edges)
                print(f"    → {len(cit_edges)} raw citations extracted")

        resolved_edges, stub_nodes = resolve_citations(raw_cit_edges, nodes)
        nodes.update(stub_nodes)
        nlp_edges.extend(resolved_edges)
        kg_hits  = sum(1 for e in resolved_edges if e.relation == "CITES_KG_NODE")
        ext_hits = sum(1 for e in resolved_edges if e.relation == "CITES_EXTERNAL")
        print(f"  Citation resolution: {kg_hits} KG matches, {ext_hits} external stubs ({len(stub_nodes)} unique)")
        edges = edges + nlp_edges
        print(f"  Total edges after NLP: {len(edges)}")
    else:
        print("\n[Step 3] Skipped (fetch_full_text=False)")

    # ── Step 4: Symbolic validation ───────────────────────────────
    print("\n[Step 4] Running symbolic validations...")
    validations: dict[str, bool] = {}

    v1 = any(e.relation == "INTERPRETED_BY_BINDING_THESIS" for e in edges)
    validations["V1_binding_thesis_exists"] = v1
    print(f"  V1 – Binding thesis edge exists          : {'PASS' if v1 else 'FAIL'}")

    v2 = all(0.0 <= e.weight <= 1.0 for e in edges)
    validations["V2_weights_in_range"] = v2
    print(f"  V2 – All weights in [0.0, 1.0]           : {'PASS' if v2 else 'FAIL'}")

    v3 = all(getattr(n, "node_type", "") != "" for n in nodes.values())
    validations["V3_all_nodes_typed"] = v3
    print(f"  V3 – All nodes have non-empty node_type  : {'PASS' if v3 else 'FAIL'}")

    v4 = all(
        getattr(nodes.get(e.source), "node_type", "") == "LegalProvision"
        for e in edges if e.relation == "CONTROLLED_BY"
    )
    validations["V4_controlled_by_source"] = v4
    print(f"  V4 – CONTROLLED_BY from LegalProvision   : {'PASS' if v4 else 'FAIL'}")

    # ── Step 5: Build graph and export ───────────────────────────
    print("\n[Step 5] Building NetworkX graph and exporting...")
    G = build_networkx_graph(nodes, edges)
    print_graph_summary(G, f"CDC Art. {ARTIGO_ID}")

    case_nodes = [(nid, n) for nid, n in nodes.items() if isinstance(n, CaseNode)]
    top5_cases = sorted(case_nodes, key=lambda x: x[1].authority_weight, reverse=True)[:5]
    if top5_cases:
        print("  Top-5 cases by authority_weight:")
        for _, n in top5_cases:
            print(f"    [{n.authority_weight:.4f}]  {n.title[:60]}")
        print()

    os.makedirs("output", exist_ok=True)

    kg_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "norma_id": NORMA_ID,
            "artigo_id": ARTIGO_ID,
            "source": BASE_URL,
            "fetch_full_text": fetch_full_text,
        },
        "nodes": [asdict(n) for n in nodes.values()],
        "edges": [asdict(e) for e in edges],
        "validations": validations,
    }

    json_path = "output/kg_pilot_art18.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)
    print(f"  Exported: {json_path}")

    graphml_path = "output/kg_pilot_art18.graphml"
    nx.write_graphml(G, graphml_path)
    print(f"  Exported: {graphml_path}")

    export_neo4j_csv(nodes, edges)
    export_data_importer_csv(nodes, edges)

    return nodes, edges, G


def classify_citations_llm(
    edges: list[Edge],
    llm_fn: Callable[[str], str],
    confidence_threshold: float = 0.7,
) -> list[Edge]:
    RELATION_WEIGHTS: dict[str, float] = {
        "SUPPORTS":      0.9,
        "ANALOGIZES":    0.7,
        "DISTINGUISHES": 0.4,
        "OVERRULES":     0.1,
    }
    PROMPT_TEMPLATE = (
        "You are a legal AI assistant. Classify how the following citation is used "
        "in the excerpt. Answer with exactly one word chosen from: "
        "SUPPORTS, ANALOGIZES, DISTINGUISHES, OVERRULES.\n\n"
        "Citation: {citation_text}\n"
        "Excerpt  : {context}\n\n"
        "Classification:"
    )

    classified = needs_review = 0
    for edge in edges:
        if edge.relation != "CITES" or not edge.metadata.get("needs_llm_classification"):
            continue
        prompt = PROMPT_TEMPLATE.format(
            citation_text=edge.metadata.get("citation_text", ""),
            context=edge.metadata.get("context", ""),
        )
        try:
            raw = llm_fn(prompt)
            label = raw.strip().upper()
            valid = label in RELATION_WEIGHTS
            if not valid:
                label = "SUPPORTS"
            edge.relation = label
            edge.weight   = RELATION_WEIGHTS[label]
            edge.metadata["llm_raw_output"]          = raw.strip()
            edge.metadata["needs_llm_classification"] = False
            edge.metadata["needs_expert_review"]      = not valid or edge.weight < confidence_threshold
            classified += 1
            if edge.metadata["needs_expert_review"]:
                needs_review += 1
        except Exception as exc:
            edge.metadata["llm_error"] = str(exc)

    print(f"[LLM] Classified: {classified} | Needs expert review: {needs_review}")
    return edges


if __name__ == "__main__":
    nodes, edges, G = run_pilot(fetch_full_text=True)

    # ── LLM integration (uncomment to activate) ──────────────────
    # import openai
    # client = openai.OpenAI()
    #
    # def llm_fn(prompt: str) -> str:
    #     resp = client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[{"role": "user", "content": prompt}],
    #         max_tokens=10,
    #     )
    #     return resp.choices[0].message.content
    #
    # edges = classify_citations_llm(edges, llm_fn)
    # G_classified = build_networkx_graph(nodes, edges)
    # nx.write_graphml(G_classified, "output/kg_pilot_art18_classified.graphml")

    #── Neo4j AuraDB export (uncomment and fill credentials) ─────
    from export_neo4j import export_to_neo4j
    export_to_neo4j(
        nodes, edges,
        uri="https://e90aaf5d.databases.neo4j.io",
        user="neo4j",
        password="zx6KR6f5G-P2wQBTUtqJ6Z5IhG_E7qV8yW4ykbhtPuQ",
    )
