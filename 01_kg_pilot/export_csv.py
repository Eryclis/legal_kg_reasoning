import csv
import os
import re
import unicodedata

from config import AUTHORITY_WEIGHTS
from models import Edge


def _sanitize_id(node_id: str) -> str:
    nfkd = unicodedata.normalize("NFKD", node_id)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9_\-]", "_", ascii_str)


def _clean(text: str, limit: int = 0) -> str:
    out = re.sub(r"\s+", " ", text or "").strip()
    return out[:limit] if limit else out


def _bool(val) -> str:
    return "true" if val else "false"


_TYPE_WEIGHTS: dict[str, float] = {
    "LegalProvision":    1.0,
    "LegalSubProvision": 1.0,
    **AUTHORITY_WEIGHTS,
}


def _weight(node) -> float:
    w = getattr(node, "authority_weight", None)
    if isinstance(w, (int, float)):
        return round(float(w), 4)
    return _TYPE_WEIGHTS.get(getattr(node, "node_type", ""), 0.0)


def export_neo4j_csv(
    nodes: dict,
    edges: list[Edge],
    output_dir: str = "output/neo4j_admin",
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    id_map: dict[str, str] = {nid: _sanitize_id(nid) for nid in nodes}

    by_type: dict[str, list] = {}
    for node in nodes.values():
        by_type.setdefault(getattr(node, "node_type", "Unknown"), []).append(node)

    def _path(label: str) -> str:
        return os.path.join(output_dir, f"nodes_{label}.csv")

    total_nodes = 0

    items = by_type.get("LegalProvision", [])
    if items:
        with open(_path("LegalProvision"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "law", "article:int", "text", "is_stub:boolean"])
            for n in items:
                w.writerow([id_map[n.node_id], "LegalProvision", n.law, n.article, _clean(n.text), _bool(n.is_stub)])
        total_nodes += len(items)
        print(f"  nodes_LegalProvision.csv       → {len(items):>3} rows")

    items = by_type.get("LegalSubProvision", [])
    if items:
        with open(_path("LegalSubProvision"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "law", "article:int", "sub_ref", "sub_type", "text", "parent_id"])
            for n in items:
                w.writerow([id_map[n.node_id], "LegalSubProvision", n.law, n.article,
                             n.sub_ref, n.sub_type, _clean(n.text), id_map.get(n.parent_id, n.parent_id)])
        total_nodes += len(items)
        print(f"  nodes_LegalSubProvision.csv    → {len(items):>3} rows")

    items = by_type.get("Case", [])
    if items:
        with open(_path("Case"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "title", "case_class", "full_text_hash",
                         "publication_date", "rapporteur", "adjudicating_body",
                         "summary", "full_text_url", "authority_weight:float", "similar_count:int",
                         "temporal_status", "has_rg:boolean", "origin_state", "court", "corpus_id:int"])
            for n in items:
                w.writerow([id_map[n.node_id], "Case", _clean(n.title), n.case_class, n.full_text_hash,
                             n.publication_date, _clean(n.rapporteur), _clean(n.adjudicating_body),
                             _clean(n.summary), n.full_text_url, _weight(n), n.similar_count,
                             n.temporal_status, _bool(n.has_rg), n.origin_state, n.court, n.corpus_id])
        total_nodes += len(items)
        print(f"  nodes_Case.csv                 → {len(items):>3} rows")

    items = by_type.get("RepetitiveTopic", [])
    if items:
        with open(_path("RepetitiveTopic"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "title", "thesis", "ementa", "question",
                         "status", "status_confirmed:boolean", "publication_date",
                         "source_url", "temporal_status", "has_rg:boolean", "authority_weight:float"])
            for n in items:
                w.writerow([id_map[n.node_id], "RepetitiveTopic", _clean(n.title), _clean(n.thesis),
                             _clean(n.ementa), _clean(n.question), n.status, _bool(n.status_confirmed),
                             n.publication_date, n.source_url, n.temporal_status, _bool(n.has_rg), _weight(n)])
        total_nodes += len(items)
        print(f"  nodes_RepetitiveTopic.csv      → {len(items):>3} rows")

    items = by_type.get("STJThesis", [])
    if items:
        with open(_path("STJThesis"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "edition", "thesis_text",
                         "source_url", "temporal_status", "authority_weight:float"])
            for n in items:
                w.writerow([id_map[n.node_id], "STJThesis", _clean(n.edition), _clean(n.thesis_text),
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)
        print(f"  nodes_STJThesis.csv            → {len(items):>3} rows")

    items = by_type.get("ConstitutionalControl", [])
    if items:
        with open(_path("ConstitutionalControl"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "title", "process_number", "summary",
                         "publication_date", "source_url", "temporal_status", "authority_weight:float"])
            for n in items:
                w.writerow([id_map[n.node_id], "ConstitutionalControl", _clean(n.title),
                             n.process_number, _clean(n.summary), n.publication_date,
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)
        print(f"  nodes_ConstitutionalControl.csv → {len(items):>3} rows")

    items = by_type.get("RG_STF", [])
    if items:
        with open(_path("RG_STF"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "title", "thesis", "status",
                         "has_rg_recognized:boolean", "publication_date",
                         "source_url", "temporal_status", "authority_weight:float"])
            for n in items:
                w.writerow([id_map[n.node_id], "RG_STF", _clean(n.title), _clean(n.thesis),
                             n.status, _bool(n.has_rg_recognized), n.publication_date,
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)
        print(f"  nodes_RG_STF.csv               → {len(items):>3} rows")

    items = by_type.get("ExternalCitation", [])
    if items:
        with open(_path("ExternalCitation"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId:ID", ":LABEL", "citation_raw", "inferred_type", "court",
                         "authority_weight:float", "case_number", "origin_state",
                         "adjudicating_body", "rapporteur", "decision_date", "cited_ementa"])
            for n in items:
                w.writerow([id_map[n.node_id], "ExternalCitation", _clean(n.citation_raw),
                             n.inferred_type, n.court, _weight(n), n.case_number, n.origin_state,
                             _clean(n.adjudicating_body), _clean(n.rapporteur),
                             n.decision_date, _clean(n.cited_ementa)])
        total_nodes += len(items)
        print(f"  nodes_ExternalCitation.csv     → {len(items):>3} rows")

    rels_path = os.path.join(output_dir, "relationships.csv")
    with open(rels_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([":START_ID", ":END_ID", ":TYPE", "weight:float"])
        for edge in edges:
            start = id_map.get(edge.source, _sanitize_id(edge.source))
            end   = id_map.get(edge.target, _sanitize_id(edge.target))
            w.writerow([start, end, edge.relation, round(edge.weight, 4)])

    print(f"  relationships.csv              → {len(edges):>3} rows")
    print(f"  Total nodes: {total_nodes}  |  Total relationships: {len(edges)}")


def export_data_importer_csv(
    nodes: dict,
    edges: list[Edge],
    output_dir: str = "output/neo4j_data_importer",
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    id_map: dict[str, str] = {nid: _sanitize_id(nid) for nid in nodes}

    by_type: dict[str, list] = {}
    for node in nodes.values():
        by_type.setdefault(getattr(node, "node_type", "Unknown"), []).append(node)

    def _npath(label: str) -> str:
        return os.path.join(output_dir, f"nodes_{label}.csv")

    def _rpath(rel_type: str) -> str:
        return os.path.join(output_dir, f"rel_{rel_type}.csv")

    total_nodes = 0

    items = by_type.get("LegalProvision", [])
    if items:
        with open(_npath("LegalProvision"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "law", "article", "text", "is_stub"])
            for n in items:
                w.writerow([id_map[n.node_id], n.law, n.article, _clean(n.text), _bool(n.is_stub)])
        total_nodes += len(items)

    items = by_type.get("LegalSubProvision", [])
    if items:
        with open(_npath("LegalSubProvision"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "law", "article", "sub_ref", "sub_type", "text", "parent_id"])
            for n in items:
                w.writerow([id_map[n.node_id], n.law, n.article, n.sub_ref, n.sub_type,
                             _clean(n.text), id_map.get(n.parent_id, n.parent_id)])
        total_nodes += len(items)

    items = by_type.get("Case", [])
    if items:
        with open(_npath("Case"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "title", "case_class", "full_text_hash",
                         "publication_date", "rapporteur", "adjudicating_body",
                         "summary", "full_text_url", "authority_weight",
                         "similar_count", "temporal_status", "has_rg",
                         "origin_state", "court", "corpus_id"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.title), n.case_class, n.full_text_hash,
                             n.publication_date, _clean(n.rapporteur), _clean(n.adjudicating_body),
                             _clean(n.summary), n.full_text_url, _weight(n), n.similar_count,
                             n.temporal_status, _bool(n.has_rg), n.origin_state, n.court, n.corpus_id])
        total_nodes += len(items)

    items = by_type.get("RepetitiveTopic", [])
    if items:
        with open(_npath("RepetitiveTopic"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "title", "thesis", "ementa", "question",
                         "status", "status_confirmed", "publication_date",
                         "source_url", "temporal_status", "has_rg", "authority_weight"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.title), _clean(n.thesis),
                             _clean(n.ementa), _clean(n.question), n.status,
                             _bool(n.status_confirmed), n.publication_date,
                             n.source_url, n.temporal_status, _bool(n.has_rg), _weight(n)])
        total_nodes += len(items)

    items = by_type.get("STJThesis", [])
    if items:
        with open(_npath("STJThesis"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "edition", "thesis_text", "source_url", "temporal_status", "authority_weight"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.edition), _clean(n.thesis_text),
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)

    items = by_type.get("ConstitutionalControl", [])
    if items:
        with open(_npath("ConstitutionalControl"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "title", "process_number", "summary",
                         "publication_date", "source_url", "temporal_status", "authority_weight"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.title), n.process_number,
                             _clean(n.summary), n.publication_date,
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)

    items = by_type.get("RG_STF", [])
    if items:
        with open(_npath("RG_STF"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "title", "thesis", "status", "has_rg_recognized",
                         "publication_date", "source_url", "temporal_status", "authority_weight"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.title), _clean(n.thesis),
                             n.status, _bool(n.has_rg_recognized), n.publication_date,
                             n.source_url, n.temporal_status, _weight(n)])
        total_nodes += len(items)

    items = by_type.get("ExternalCitation", [])
    if items:
        with open(_npath("ExternalCitation"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nodeId", "citation_raw", "inferred_type", "court",
                         "authority_weight", "case_number", "origin_state",
                         "adjudicating_body", "rapporteur", "decision_date", "cited_ementa"])
            for n in items:
                w.writerow([id_map[n.node_id], _clean(n.citation_raw), n.inferred_type, n.court,
                             _weight(n), n.case_number, n.origin_state, _clean(n.adjudicating_body),
                             _clean(n.rapporteur), n.decision_date, _clean(n.cited_ementa)])
        total_nodes += len(items)

    by_rel: dict[str, list[Edge]] = {}
    for edge in edges:
        by_rel.setdefault(edge.relation, []).append(edge)

    total_rels = 0
    for rel_type, rel_edges in sorted(by_rel.items()):
        with open(_rpath(rel_type), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["start_id", "end_id", "weight"])
            for edge in rel_edges:
                start = id_map.get(edge.source, _sanitize_id(edge.source))
                end   = id_map.get(edge.target, _sanitize_id(edge.target))
                w.writerow([start, end, round(edge.weight, 4)])
        total_rels += len(rel_edges)
        print(f"  rel_{rel_type}.csv  → {len(rel_edges):>3} rows")

    print(f"\n  [Data Importer] {output_dir}/")
    print(f"    Node files : {len(by_type)} labels  ({total_nodes} rows)")
    print(f"    Rel files  : {len(by_rel)} types  ({total_rels} rows)")
