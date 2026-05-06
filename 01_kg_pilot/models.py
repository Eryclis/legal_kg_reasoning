from dataclasses import dataclass, field


@dataclass
class NormaNode:
    node_id: str
    node_type: str = "LegalProvision"
    law: str = "CDC"
    article: int = 0
    text: str = ""
    is_stub: bool = False


@dataclass
class NormaSubNode:
    node_id: str
    node_type: str = "LegalSubProvision"
    law: str = "CDC"
    article: int = 0
    sub_ref: str = ""
    sub_type: str = ""     # "paragraph" | "incise"
    text: str = ""
    parent_id: str = ""


@dataclass
class CaseNode:
    node_id: str
    node_type: str = "Case"
    title: str = ""
    full_text_hash: str = ""
    publication_date: str = ""
    rapporteur: str = ""
    adjudicating_body: str = ""  # populated for isolated cases; empty for grouped
    case_class: str = ""
    summary: str = ""
    full_text_url: str = ""
    authority_weight: float = 0.0
    similar_count: int = 0
    temporal_status: str = "active"
    has_rg: bool = False
    origin_state: str = ""
    court: str = "STJ"
    corpus_id: int = 0


@dataclass
class TopicNode:
    node_id: str
    node_type: str = "RepetitiveTopic"
    title: str = ""
    thesis: str = ""
    ementa: str = ""
    question: str = ""
    status: str = ""
    status_confirmed: bool = False
    publication_date: str = ""
    source_url: str = ""
    temporal_status: str = "active"
    has_rg: bool = False


@dataclass
class STJThesisNode:
    node_id: str
    node_type: str = "STJThesis"
    edition: str = ""
    thesis_text: str = ""
    source_url: str = ""
    temporal_status: str = "active"


@dataclass
class ConstitutionalControlNode:
    node_id: str
    node_type: str = "ConstitutionalControl"
    title: str = ""
    process_number: str = ""
    summary: str = ""
    publication_date: str = ""
    source_url: str = ""
    temporal_status: str = "active"


@dataclass
class RG_STFNode:
    node_id: str
    node_type: str = "RG_STF"
    title: str = ""
    thesis: str = ""
    status: str = ""
    has_rg_recognized: bool = True
    publication_date: str = ""
    source_url: str = ""
    temporal_status: str = "active"


@dataclass
class ExternalCitationNode:
    node_id: str
    node_type: str = "ExternalCitation"
    citation_raw: str = ""
    inferred_type: str = ""
    court: str = ""
    authority_weight: float = 0.0
    case_number: str = ""
    origin_state: str = ""
    adjudicating_body: str = ""
    rapporteur: str = ""
    decision_date: str = ""
    cited_ementa: str = ""


@dataclass
class Edge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)
