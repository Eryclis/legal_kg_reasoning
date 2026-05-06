import re
from typing import Any

from config import CANONICAL_CITATION_RE, AUTHORITY_WEIGHTS
from models import Edge, ExternalCitationNode


CITATION_PATTERNS = [
    r"\b(REsp|AREsp|AgRg|AgInt|EDcl)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)(?:\s*/\s*\w{2,3})?",
    r"\b(HC|MS|RMS|RO|CC|AR)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)(?:\s*/\s*\w{2,3})?",
    r"\bTemas?\s+(?:n[oº°]?\s*)?(\d+)",
    r"\b(ADI|ADC|ADPF|MI|ADIN)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)",
    (
        r"\bart(?:igo)?\.?\s*(\d+)"
        r"(?:[,\s]+(?:§|parágrafo|inciso|caput))?"
        r"\s+(?:do\s+)?(?:CDC|Código\s+de\s+Defesa\s+do\s+Consumidor|Lei\s+8\.078)"
    ),
]


def _extract_preceding_quote(look_back: str) -> str:
    for open_char, close_char in [('"', '"'), ('"', '"')]:
        last_close = look_back.rfind(close_char)
        if last_close < 0:
            continue
        open_pos = look_back.rfind(open_char, 0, last_close)
        if open_pos < 0:
            continue
        quoted = look_back[open_pos + 1 : last_close].strip()
        if len(quoted) >= 20:
            return quoted
    return ""


def extract_citations(text: str, source_id: str) -> list[Edge]:
    edges: list[Edge] = []
    seen: set[tuple[str, str]] = set()

    def _norm_key(cls: str, num: str) -> tuple[str, str]:
        return (
            re.sub(r"[\s\-]", "", cls).upper(),
            re.sub(r"[.,\s]", "", num),
        )

    for m in CANONICAL_CITATION_RE.finditer(text):
        case_class  = m.group("case_class").strip()
        case_number = m.group("case_number").strip()
        key = _norm_key(case_class, case_number)
        if key in seen:
            continue
        seen.add(key)

        origin_state  = (m.group("origin_state")      or "").strip()
        adj_body      = (m.group("adjudicating_body") or "").strip()
        rapporteur    = (m.group("rapporteur")        or "").strip()
        decision_date = (m.group("decision_date")     or "").strip()

        look_back    = text[max(0, m.start() - 3000) : m.start()]
        cited_ementa = _extract_preceding_quote(look_back)

        norm_cls  = re.sub(r"[\s\-]", "", case_class).upper()
        norm_num  = re.sub(r"[.,\s]", "", case_number)
        target_id = f"CITE_{norm_cls}_{norm_num}"
        if origin_state:
            target_id += f"_{origin_state}"

        edges.append(Edge(
            source=source_id,
            target=target_id,
            relation="CITES",
            weight=0.5,
            metadata={
                "citation_raw":      m.group(0),
                "case_class":        case_class,
                "case_number":       case_number,
                "origin_state":      origin_state,
                "adjudicating_body": adj_body,
                "rapporteur":        rapporteur,
                "decision_date":     decision_date,
                "cited_ementa":      cited_ementa,
                "extraction_method": "canonical",
                "needs_llm_classification": True,
            },
        ))

    for pattern in CITATION_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            citation_raw = m.group(0)
            groups = m.groups()
            if len(groups) >= 2 and groups[0] and groups[1]:
                key = _norm_key(groups[0], groups[1])
            else:
                key = _norm_key(citation_raw, "")
            if key in seen:
                continue
            seen.add(key)

            citation_norm = re.sub(r"\s+", "_", citation_raw.strip().upper())
            start   = max(0, m.start() - 80)
            end     = min(len(text), m.end() + 80)
            context = text[start:end].replace("\n", " ")
            edges.append(Edge(
                source=source_id,
                target=f"CITE_{citation_norm}",
                relation="CITES",
                weight=0.5,
                metadata={
                    "citation_raw":      citation_raw,
                    "context":           context,
                    "extraction_method": "bare_mention",
                    "needs_llm_classification": True,
                },
            ))

    return edges


def resolve_citations(
    citation_edges: list[Edge],
    nodes: dict,
) -> tuple[list[Edge], dict[str, ExternalCitationNode]]:
    def _infer_type(citation_text: str) -> tuple[str, str]:
        c = citation_text.upper()
        if re.search(r"\b(ADI|ADC|ADPF|ADIN|MI)\b", c):
            return "ConstitutionalControl", "STF"
        if re.search(r"\bTEMA\b", c):
            return "RepetitiveTopic", "STJ"
        if re.search(r"\b(SÚMULA|SUMULA|TESE)\b", c):
            return "STJThesis", "STJ"
        if re.search(r"\b(RESP|ARESP|HC|MS|RMS|CC|AGRG|AGINT|EDCL|RHC)\b", c):
            return "Case", "STJ"
        return "Unknown", ""

    node_lookup: dict[str, str] = {}
    for nid in nodes:
        key = re.sub(r"[.,\s]", "", nid).upper()
        node_lookup[key] = nid

    resolved_edges: list[Edge] = []
    new_stubs: dict[str, ExternalCitationNode] = {}

    for edge in citation_edges:
        if edge.relation != "CITES":
            resolved_edges.append(edge)
            continue

        citation_norm = edge.target.replace("CITE_", "", 1)
        citation_text = edge.metadata.get("citation_raw", citation_norm)

        lookup_key = re.sub(r"[.,\s_]", "", citation_norm).upper()
        matched_id  = node_lookup.get(lookup_key)

        source_node   = nodes.get(edge.source)
        source_weight = getattr(source_node, "authority_weight", 0.3) if source_node else 0.3

        if matched_id:
            matched_node = nodes[matched_id]
            kg_weight = getattr(
                matched_node, "authority_weight",
                AUTHORITY_WEIGHTS.get(getattr(matched_node, "node_type", ""), 0.5),
            )
            resolved_edges.append(Edge(
                source=edge.source,
                target=matched_id,
                relation="CITES_KG_NODE",
                weight=kg_weight,
                metadata={**edge.metadata, "resolved": True},
            ))
        else:
            # Sanitize so stub_id matches the CSV nodeId (dots/slashes → underscores)
            citation_norm_safe = re.sub(r"[^A-Za-z0-9_\-]", "_", citation_norm)
            stub_id = f"EXT_{citation_norm_safe}"
            inferred_type, court = _infer_type(citation_text)
            meta = edge.metadata

            if stub_id not in new_stubs:
                new_stubs[stub_id] = ExternalCitationNode(
                    node_id=stub_id,
                    citation_raw=citation_text,
                    inferred_type=inferred_type,
                    court=court,
                    authority_weight=source_weight,
                    case_number=meta.get("case_number", ""),
                    origin_state=meta.get("origin_state", ""),
                    adjudicating_body=meta.get("adjudicating_body", ""),
                    rapporteur=meta.get("rapporteur", ""),
                    decision_date=meta.get("decision_date", ""),
                    cited_ementa=meta.get("cited_ementa", ""),
                )
            else:
                existing = new_stubs[stub_id]
                existing.authority_weight = max(existing.authority_weight, source_weight)
                if meta.get("extraction_method") == "canonical":
                    if not existing.case_number:       existing.case_number       = meta.get("case_number", "")
                    if not existing.origin_state:      existing.origin_state      = meta.get("origin_state", "")
                    if not existing.adjudicating_body: existing.adjudicating_body = meta.get("adjudicating_body", "")
                    if not existing.rapporteur:        existing.rapporteur        = meta.get("rapporteur", "")
                    if not existing.decision_date:     existing.decision_date     = meta.get("decision_date", "")
                    if not existing.cited_ementa:      existing.cited_ementa      = meta.get("cited_ementa", "")

            resolved_edges.append(Edge(
                source=edge.source,
                target=stub_id,
                relation="CITES_EXTERNAL",
                weight=source_weight,
                metadata={**edge.metadata, "resolved": False},
            ))

    return resolved_edges, new_stubs


def segment_full_text(text: str) -> dict[str, str]:
    sections: dict[str, str] = {"header": "", "abstract": "", "report": "", "vote": ""}

    relatorio_m = re.search(r"\bRELATÓRIO\b", text, re.IGNORECASE)
    search_from = relatorio_m.end() if relatorio_m else 0
    tail        = text[search_from:]

    voto_local = (
        re.search(r"(?:^|\n)\s*VOTO\s*(?:\n|$)", tail, re.IGNORECASE)
        or re.search(r"\bVOTO\s+DO\s+RELATOR\b",  tail, re.IGNORECASE)
        or re.search(r"\bVOTO\b",                  tail, re.IGNORECASE)
    )

    if voto_local:
        voto_abs_start = search_from + voto_local.start()
        voto_abs_end   = search_from + voto_local.end()
    else:
        voto_abs_start = voto_abs_end = None

    if relatorio_m:
        sections["header"] = text[: relatorio_m.start()].strip()
        if voto_abs_start is not None and voto_abs_start > relatorio_m.end():
            sections["report"] = text[relatorio_m.end() : voto_abs_start].strip()
            sections["vote"]   = text[voto_abs_end:].strip()
        else:
            sections["report"] = text[relatorio_m.end():].strip()
    else:
        if voto_abs_start is not None:
            sections["header"] = text[:voto_abs_start].strip()
            sections["vote"]   = text[voto_abs_end:].strip()
        else:
            sections["header"] = text

    ementa_m = re.search(r"\bEMENTA\b", text, re.IGNORECASE)
    if ementa_m:
        start = ementa_m.end()
        end_m = re.search(r"\n\s*\d+\.|Sustenta|Trata-se", text[start:], re.IGNORECASE)
        if end_m:
            sections["abstract"] = text[start : start + end_m.start()].strip()
        else:
            sections["abstract"] = text[start : start + 1000].strip()

    return sections
