# ============================================================
# Corpus927 KG Pilot — Art. 18 CDC
# Pipeline: Extract → Transform → Load → NLP → Graph
# ============================================================

# Standard library
import re
import json
import math
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Any, Callable
from collections import Counter

# Third-party
import requests
from bs4 import BeautifulSoup
import networkx as nx

# ============================================================
# Section 1: Configuration
# ============================================================

BASE_URL   = "https://corpus927.enfam.jus.br"
NORMA_ID   = 1        # CDC = nrm:1
ARTIGO_ID  = 18       # Art. 18
RATE_LIMIT = 1.0      # seconds between requests (be polite)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (KG-Pilot-Research/1.0)",
    "Accept": "application/json, text/html",
}

# ── Type code mappings ───────────────────────────────────────
JURS_TYPES = {
    90:  "ConstitutionalControl",
    70:  "RG_STF",
    110: "JurisprudenceInTheses",
    100: "OtherType",
}
TEMAS_TYPES = {
    60: "RepetitiveTopic",
    80: "OtherTopic",
}

# ── Authority weights by node type ───────────────────────────
AUTHORITY_WEIGHTS: dict[str, float] = {
    "ConstitutionalControl": 1.00,  # ADI/ADC/ADPF — validity of the norm
    "RG_STF":                0.95,  # STF binding constitutional precedent
    "RepetitiveTopic":       0.90,  # STJ binding thesis (Tema Repetitivo)
    "STJThesis":             0.80,  # STJ Jurisprudência em Teses (Edições)
    # CaseNode: log-normalized (grouped) or 0.30 (isolated) — computed at runtime
}

# ============================================================
# Section 2: Data Classes (KG nodes)
# ============================================================

@dataclass
class NormaNode:
    """Node: Legal provision (article)"""
    node_id: str               # "CDC_art18"
    node_type: str = "LegalProvision"
    law: str = "CDC"
    article: int = 0
    text: str = ""             # article text (fill separately)

@dataclass
class CaseNode:
    """Node: Judicial decision"""
    node_id: str               # "REsp_1556132"
    node_type: str = "Case"
    title: str = ""
    full_text_hash: str = ""   # full-text document identifier
    publication_date: str = ""
    rapporteur: str = ""
    adjudicating_body: str = ""
    case_class: str = ""
    summary: str = ""          # first 500 chars
    full_text_url: str = ""
    authority_weight: float = 0.0
    similar_count: int = 0
    temporal_status: str = "active"
    has_rg: bool = False

@dataclass
class TopicNode:
    """Node: Repetitive appeal topic (canonical thesis)"""
    node_id: str               # "Topic_449"
    node_type: str = "RepetitiveTopic"
    title: str = ""
    thesis: str = ""           # canonical thesis text — GOLD STANDARD
    status: str = ""           # "Transitado em Julgado" → maximum authority
    publication_date: str = ""
    source_url: str = ""
    temporal_status: str = "active"
    has_rg: bool = False

@dataclass
class STJThesisNode:
    """Node: STJ Jurisprudence in Theses (Editions)"""
    node_id: str               # "STJThesis_Edition83_t6"
    node_type: str = "STJThesis"
    edition: str = ""
    thesis_text: str = ""
    source_url: str = ""
    temporal_status: str = "active"

@dataclass
class ConstitutionalControlNode:
    """Node: Constitutional Control decision (ADI, ADC, ADPF)"""
    node_id: str               # "CC_ADI_5158"
    node_type: str = "ConstitutionalControl"
    title: str = ""
    summary: str = ""
    publication_date: str = ""
    temporal_status: str = "active"

@dataclass
class Edge:
    """KG directed edge"""
    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)

@dataclass
class NormaSubNode:
    """Node: Sub-provision of a legal article (paragraph, incise, item)"""
    node_id: str               # "CDC_art18_par1", "CDC_art18_par1_incI"
    node_type: str = "LegalSubProvision"
    law: str = "CDC"
    article: int = 0
    sub_ref: str = ""          # "§ 1°", "I", "II", "a"
    sub_type: str = ""         # "paragraph" | "incise"
    text: str = ""
    parent_id: str = ""

@dataclass
class RG_STFNode:
    """Node: STF Repercussão Geral decision (binding constitutional precedent)"""
    node_id: str               # "RG_STF_Tema_1234"
    node_type: str = "RG_STF"
    title: str = ""
    thesis: str = ""
    status: str = ""           # procedural status from Corpus927
    has_rg_recognized: bool = True  # False when tagged as 'não há repercussão geral'
    publication_date: str = ""
    source_url: str = ""
    temporal_status: str = "active"

@dataclass
class ExternalCitationNode:
    """Node: Citation target not found in the KG (stub for external references)"""
    node_id: str               # "EXT_RESP_200000"
    node_type: str = "ExternalCitation"
    citation_raw: str = ""     # original citation text extracted from VOTO
    inferred_type: str = ""    # "Case" | "STJThesis" | "ConstitutionalControl" | "Unknown"
    court: str = ""            # inferred from citation class prefix
    authority_weight: float = 0.0  # inferred from type via AUTHORITY_WEIGHTS

# ============================================================
# Section 3: Corpus927Extractor — API access layer
# ============================================================

class Corpus927Extractor:
    def __init__(self, base_url: str = BASE_URL, rate_limit: float = RATE_LIMIT):
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._init_session()

    def _init_session(self):
        """
        Visits the legislation page to obtain Laravel session cookies (XSRF-TOKEN,
        laravel_session) required by all subsequent API calls.
        The HTML response is cached for later article-text extraction.
        """
        resp = self.session.get(
            f"{self.base_url}/legislacao/cdc-90", timeout=30
        )
        resp.raise_for_status()
        self._legislacao_html = resp.text   # cached for fetch_article_text
        # Extract XSRF token from cookie and add as request header
        xsrf = self.session.cookies.get("XSRF-TOKEN", "")
        if xsrf:
            self.session.headers.update({
                "x-xsrf-token": requests.utils.unquote(xsrf),
                "x-requested-with": "XMLHttpRequest",
            })
        time.sleep(self.rate_limit)

    def fetch_article_text(self, norma_id: int, artigo_id: int) -> dict:
        """
        Parses the cached legislation HTML to extract the structured text of an article.
        Uses the ng-click attribute to locate the article element, then walks siblings
        to collect paragraphs and incises until the next article begins.

        Returns:
            {
              "caput": str,
              "paragraphs": {"§ 1°": str, "§ 2°": str, ...},
              "incises": {"§ 1°": {"I": str, "II": str, ...}, ...},
            }
            Empty dict if the article is not found in the cached HTML.
        """
        soup = BeautifulSoup(self._legislacao_html, "html.parser")
        ng_val = f"buscarJurisprudencia($event,'nrm:{norma_id}|art:{artigo_id}')"
        # The ng-click lives on an <a> inside <font> inside <p>; walk up to <p>
        anchor = soup.find("a", attrs={"ng-click": ng_val})
        if anchor is None:
            return {}
        target = anchor.find_parent("p")
        if target is None:
            return {}

        result: dict = {
            "caput": target.get_text(separator=" ", strip=True),
            "paragraphs": {},
            "incises": {},
        }
        current_par: str | None = None

        for el in target.find_next_siblings():
            if el.name != "p":
                continue
            if el.find("a", attrs={"ng-click": True}):   # next article starts here
                break
            text = el.get_text(strip=True)
            if not text:
                continue

            par_m = re.match(r"^(§\s*\d+[°º]?)", text)
            inc_m = re.match(r"^([IVX]+|[a-z])\s*[-–)]", text)

            if par_m:
                par_key = re.sub(r"\s+", " ", par_m.group(1)).strip()
                current_par = par_key
                result["paragraphs"][par_key] = text
                result["incises"][par_key] = {}
            elif inc_m and current_par:
                raw_key = inc_m.group(1)
                # Normalize: roman numerals → uppercase, letters → lowercase
                inc_key = raw_key.upper() if re.fullmatch(r"[IVX]+", raw_key) else raw_key
                result["incises"][current_par][inc_key] = text

        return result

    def fetch_jurisprudencia(self, norma_id: int, artigo_id: int) -> dict:
        """
        Calls the main API: /jurisprudencia/nrm:{N}|art:{M}
        Returns the full JSON with all authority layers.
        """
        url = f"{self.base_url}/jurisprudencia/nrm:{norma_id}%7Cart:{artigo_id}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        time.sleep(self.rate_limit)
        return resp.json()

    def fetch_full_text(self, hash_it: str) -> str:
        """
        Fetches the full text of a decision by hash.
        Returns plain text extracted from #conteudoInteiroTeor.
        """
        url = f"{self.base_url}/inteiro-teor/{hash_it}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(self.rate_limit)
        soup = BeautifulSoup(resp.text, "html.parser")
        el = soup.find(id="conteudoInteiroTeor")
        if el:
            return el.get_text(separator="\n", strip=True)
        return ""

# ============================================================
# Section 4: KGTransformer — converts JSON → nodes and edges
# ============================================================

class KGTransformer:
    def __init__(self, norma_node: NormaNode):
        self.norma = norma_node
        self.nodes: dict[str, Any] = {norma_node.node_id: norma_node}
        self.edges: list[Edge] = []

    def _clean_html(self, text: str) -> str:
        """Strips HTML tags from content using regex."""
        return re.sub(r"<[^>]+>", " ", text or "").strip()

    def _make_case_id(self, title: str) -> str:
        """Converts 'REsp 1.556.132' → 'REsp_1556132'."""
        cleaned = title.strip().replace("/", "_").replace(".", "").replace(",", "")
        return re.sub(r"\s+", "_", cleaned)

    # ── 4a. RG_STF (Repercussão Geral) ──────────────────────
    def process_rg_stf(self, items: list):
        """
        Type 70: STF Repercussão Geral decisions (binding constitutional precedents).
        Items tagged as 'não há repercussão geral' are recorded with relation
        REVIEWED_STF_NO_RG and weight 0.0 (informational only, not authority).
        Edge: norm --[INTERPRETED_BY_RG_STF]--> rg_node (weight=0.95)
        """
        for item in items:
            raw_title = item.get("titulo", "")
            situacao = item.get("situacao", "")
            situacao_confirmada = item.get("situacao_confirmada", "")

            no_rg_phrases = ["não há repercussão", "nao ha repercussao", "sem repercussão"]
            combined = (situacao + " " + situacao_confirmada).lower()
            has_rg = not any(p in combined for p in no_rg_phrases)

            node_id = "RG_STF_" + re.sub(r"[\s/]+", "_", raw_title.strip())
            node = RG_STFNode(
                node_id=node_id,
                title=raw_title,
                thesis=self._clean_html(item.get("tese", "")),
                status=situacao,
                has_rg_recognized=has_rg,
                publication_date=item.get("data_publicacao", ""),
                source_url=item.get("url", ""),
            )
            self.nodes[node_id] = node
            relation = "INTERPRETED_BY_RG_STF" if has_rg else "REVIEWED_STF_NO_RG"
            weight = AUTHORITY_WEIGHTS["RG_STF"] if has_rg else 0.0
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=node_id,
                relation=relation,
                weight=weight,
                metadata={"has_rg": has_rg, "situacao": situacao},
            ))

    # ── 4c. Constitutional Control ───────────────────────────
    def process_constitutional_control(self, items: list):
        """
        Type 90: ADI, ADC, ADPF decisions linked to the article.
        Edge: norm --[CONTROLLED_BY]--> constitutional_control (weight=1.0)
        Logic: constitutional control defines the validity of the norm.
        """
        for item in items:
            raw_title = item.get("titulo", "")
            node_id = "CC_" + re.sub(r"[\s/]+", "_", raw_title.strip())
            node = ConstitutionalControlNode(
                node_id=node_id,
                title=raw_title,
                summary=self._clean_html(item.get("conteudo", ""))[:600],
                publication_date=item.get("data_publicacao", ""),
            )
            self.nodes[node_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=node_id,
                relation="CONTROLLED_BY",
                weight=1.0,
                metadata={"type": "constitutional_control"},
            ))

    # ── 4b. Repetitive Topics ────────────────────────────────
    def process_topics(self, temas_dict: dict):
        """
        Key "60": Repetitive Appeal Topics (binding theses).
        Edge: norm --[INTERPRETED_BY_BINDING_THESIS]--> topic
        Weight: 1.0 if "Julgado" in status, else 0.8.
        """
        items = temas_dict.get("60", [])
        for item in items:
            raw_title = item.get("titulo", "")
            # Extract trailing number: "Tema 449" → "449"
            num_match = re.search(r"(\d+)\s*$", raw_title)
            num = num_match.group(1) if num_match else re.sub(r"\s+", "_", raw_title.strip())
            node_id = f"Topic_{num}"
            status = item.get("situacao", "")
            authority_weight = 1.0 if "Julgado" in status else 0.8
            node = TopicNode(
                node_id=node_id,
                title=raw_title,
                thesis=self._clean_html(item.get("tese", "")),
                status=status,
                publication_date=item.get("data_publicacao", ""),
                source_url=item.get("url", ""),
            )
            self.nodes[node_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=node_id,
                relation="INTERPRETED_BY_BINDING_THESIS",
                weight=authority_weight,
                metadata={"status": status},
            ))

    # ── 4c. STJ Jurisprudence in Theses ─────────────────────
    def process_stj_theses(self, items: list):
        """
        Type 110: STJ Jurisprudence in Theses (Editions).
        Each edition contains a list of thesis strings.
        Edge: norm --[SUMMARIZED_BY_STJ_THESIS]--> stj_thesis (weight=0.9)
        """
        for item in items:
            header = item.get("cabecalho", {})
            edition_title = header.get("titulo", "")
            edition_slug = re.sub(r"[\s/]+", "_", edition_title.strip())
            theses = item.get("teses", [])
            source_url = item.get("url", "")
            for idx, thesis_text in enumerate(theses, start=1):
                # Extract leading number: "6) Texto..." → "6"
                num_match = re.match(r"^(\d+)\)", thesis_text.strip())
                num = num_match.group(1) if num_match else str(idx)
                node_id = f"STJThesis_{edition_slug}_t{num}"
                node = STJThesisNode(
                    node_id=node_id,
                    edition=edition_title,
                    thesis_text=self._clean_html(thesis_text),
                    source_url=source_url,
                )
                self.nodes[node_id] = node
                self.edges.append(Edge(
                    source=self.norma.node_id,
                    target=node_id,
                    relation="SUMMARIZED_BY_STJ_THESIS",
                    weight=0.9,
                    metadata={"edition": edition_title},
                ))

    # ── 4d. Grouped Positions (Leading Cases) ────────────────
    def process_grouped_positions(self, items: list):
        """
        Grouped positions: leading cases with clusters of similar decisions.
        Weight: logarithmic normalization over similar-case counts.
        Edge: norm --[INTERPRETED_BY_LEADING_CASE]--> case
        """
        if not items:
            return
        max_similar = max(item.get("semelhantes", 0) for item in items)
        for item in items:
            similar_count = item.get("semelhantes", 0)
            if max_similar > 0:
                weight = math.log(1 + similar_count) / math.log(1 + max_similar)
            else:
                weight = 0.0
            raw_title = item.get("titulo", "")
            case_id = self._make_case_id(raw_title)
            node = CaseNode(
                node_id=case_id,
                title=raw_title,
                full_text_hash=item.get("hash_it", ""),
                publication_date=item.get("data_publicacao", ""),
                rapporteur=item.get("relator", ""),
                adjudicating_body=item.get("orgao_julgador", ""),
                case_class=item.get("sigla_classe", ""),
                summary=self._clean_html(item.get("conteudo_resumo", ""))[:500],
                full_text_url=item.get("inteiro_teor_url", ""),
                authority_weight=round(weight, 4),
                similar_count=similar_count,
            )
            self.nodes[case_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=case_id,
                relation="INTERPRETED_BY_LEADING_CASE",
                weight=round(weight, 4),
                metadata={
                    "semelhantes": similar_count,
                    "is_leading_case": True,
                    "dispositivo_legal_id": item.get("dispositivo_legal_id", ""),
                    "nome_corpus": item.get("nome_corpus", ""),
                },
            ))

    # ── 4e. Isolated Positions ───────────────────────────────
    def process_isolated_positions(self, items: list):
        """
        Isolated positions: individual cases not in any leading-case cluster.
        Cases already registered as leading cases are skipped (no overwrite).
        Edge: norm --[INTERPRETED_BY_CASE]--> case (weight=0.3)
        """
        for item in items:
            raw_title = item.get("titulo", "")
            case_id = self._make_case_id(raw_title)
            if case_id in self.nodes:
                continue  # preserve leading-case node
            node = CaseNode(
                node_id=case_id,
                title=raw_title,
                full_text_hash=item.get("hash_it", ""),
                publication_date=item.get("data_publicacao", ""),
                rapporteur=item.get("relator", ""),
                adjudicating_body=item.get("orgao_julgador", ""),
                case_class=item.get("sigla_classe", ""),
                summary=self._clean_html(item.get("conteudo_resumo", ""))[:500],
                full_text_url=item.get("inteiro_teor_url", ""),
                authority_weight=0.3,
                similar_count=0,
            )
            self.nodes[case_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=case_id,
                relation="INTERPRETED_BY_CASE",
                weight=0.3,
                metadata={"is_leading_case": False},
            ))

    # ── Sub-article decomposition ────────────────────────────
    def populate_norma_sub_nodes(self, article_data: dict):
        """
        Creates NormaSubNode instances from structured article text returned by
        Corpus927Extractor.fetch_article_text().

        Sets self.norma.text to the caput.
        Edges:
          norma --[HAS_SUB_PROVISION]--> paragraph_node  (weight=1.0)
          paragraph_node --[HAS_INCISE]--> incise_node   (weight=1.0)
        """
        if not article_data:
            return
        law = self.norma.law
        art = self.norma.article
        prefix = f"{law}_art{art}"

        self.norma.text = article_data.get("caput", "")

        for par_ref, par_text in article_data.get("paragraphs", {}).items():
            par_num_m = re.search(r"(\d+)", par_ref)
            par_num = par_num_m.group(1) if par_num_m else re.sub(r"\W", "", par_ref)
            par_id = f"{prefix}_par{par_num}"

            par_node = NormaSubNode(
                node_id=par_id,
                law=law,
                article=art,
                sub_ref=par_ref,
                sub_type="paragraph",
                text=par_text,
                parent_id=self.norma.node_id,
            )
            self.nodes[par_id] = par_node
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=par_id,
                relation="HAS_SUB_PROVISION",
                weight=1.0,
                metadata={"sub_type": "paragraph", "sub_ref": par_ref},
            ))

            for inc_ref, inc_text in article_data.get("incises", {}).get(par_ref, {}).items():
                inc_id = f"{par_id}_inc{inc_ref}"
                inc_node = NormaSubNode(
                    node_id=inc_id,
                    law=law,
                    article=art,
                    sub_ref=inc_ref,
                    sub_type="incise",
                    text=inc_text,
                    parent_id=par_id,
                )
                self.nodes[inc_id] = inc_node
                self.edges.append(Edge(
                    source=par_id,
                    target=inc_id,
                    relation="HAS_INCISE",
                    weight=1.0,
                    metadata={"sub_type": "incise", "sub_ref": inc_ref},
                ))

    def build(self, api_response: dict) -> tuple[dict, list[Edge]]:
        """
        Orchestrates all processing steps in authority order.
        Returns (nodes, edges).
        """
        jurs  = api_response.get("jurisprudencias", {})
        temas = api_response.get("temas", {})

        # Authority order: highest first
        self.process_constitutional_control(jurs.get("90", []))
        self.process_rg_stf(jurs.get("70", []))
        self.process_stj_theses(jurs.get("110", []))
        self.process_topics(temas)
        self.process_grouped_positions(
            api_response.get("posicionamentos_agrupados_stj", [])
        )
        self.process_isolated_positions(
            api_response.get("posicionamentos_isolados", [])
        )
        return self.nodes, self.edges

# ============================================================
# Section 5: NLP Functions
# ============================================================

# Regex patterns for Brazilian legal citation extraction
CITATION_PATTERNS = [
    # STJ case classes
    r"\b(REsp|AREsp|AgRg|AgInt|EDcl)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)(?:\s*/\s*\w{2,3})?",
    # HC/MS and similar writ classes
    r"\b(HC|MS|RMS|RO|CC|AR)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)(?:\s*/\s*\w{2,3})?",
    # Repetitive topics
    r"\bTemas?\s+(?:n[oº°]?\s*)?(\d+)",
    # STF constitutional cases
    r"\b(ADI|ADC|ADPF|MI|ADIN)\s+(?:n[oº°]?\s*)?(\d[\d.,]*)",
    # CDC article references
    (
        r"\bart(?:igo)?\.?\s*(\d+)"
        r"(?:[,\s]+(?:§|parágrafo|inciso|caput))?"
        r"\s+(?:do\s+)?(?:CDC|Código\s+de\s+Defesa\s+do\s+Consumidor|Lei\s+8\.078)"
    ),
]


def extract_citations(text: str, source_id: str) -> list[Edge]:
    """
    Extracts legal citations from text and returns them as KG edges.
    Uses ±80 character context windows around each match.
    Deduplicates by normalized citation string.
    """
    edges: list[Edge] = []
    seen: set[str] = set()

    for pattern in CITATION_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            citation_raw = m.group(0)
            citation_norm = re.sub(r"\s+", "_", citation_raw.strip().upper())
            if citation_norm in seen:
                continue
            seen.add(citation_norm)
            start = max(0, m.start() - 80)
            end   = min(len(text), m.end() + 80)
            context = text[start:end].replace("\n", " ")
            edges.append(Edge(
                source=source_id,
                target=f"CITE_{citation_norm}",
                relation="CITES",
                weight=0.5,
                metadata={
                    "citation_text": citation_raw,
                    "context": context,
                    "needs_llm_classification": True,
                },
            ))

    return edges


def resolve_citations(
    citation_edges: list[Edge],
    nodes: dict,
) -> tuple[list[Edge], dict[str, "ExternalCitationNode"]]:
    """
    Resolves raw CITES edges (produced by extract_citations) against the KG node set.

    For each CITES edge:
      - Match found  → CITES_KG_NODE edge pointing to the existing node
      - No match     → CITES_EXTERNAL edge + new ExternalCitationNode stub

    Args:
        citation_edges: Output of extract_citations (relation == "CITES").
        nodes: Current KG node dict (used for matching).

    Returns:
        (resolved_edges, new_stubs) — updated edges and new stub nodes to merge.
    """
    INFERRED_WEIGHTS: dict[str, float] = {
        "ConstitutionalControl": AUTHORITY_WEIGHTS["ConstitutionalControl"],
        "RG_STF":                AUTHORITY_WEIGHTS["RG_STF"],
        "RepetitiveTopic":       AUTHORITY_WEIGHTS["RepetitiveTopic"],
        "STJThesis":             AUTHORITY_WEIGHTS["STJThesis"],
        "Case":                  0.50,   # mid-range; no cluster info available
        "Unknown":               0.30,
    }

    def _infer_type(citation_text: str) -> tuple[str, str]:
        """Returns (inferred_node_type, court)."""
        c = citation_text.upper()
        if any(x in c for x in ["ADI", "ADC", "ADPF", "MI", "ADIN"]):
            return "ConstitutionalControl", "STF"
        if re.search(r"\bTEMA\b", c):
            return "RepetitiveTopic", "STJ"
        if re.search(r"\b(SÚMULA|SUMULA|TESE)\b", c):
            return "STJThesis", "STJ"
        if re.search(r"\b(RESP|ARESP|HC|MS|RMS|CC|AGRG|AGINT|EDCL)\b", c):
            return "Case", "STJ"
        return "Unknown", ""

    # Build a normalized lookup: strip dots/commas/spaces → original node_id
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

        # edge.target == "CITE_{citation_norm}"; strip prefix for matching
        citation_norm = edge.target.replace("CITE_", "", 1)   # e.g. "RESP_1556132"
        citation_text = edge.metadata.get("citation_text", citation_norm)

        # Try normalized match against existing nodes
        lookup_key = re.sub(r"[.,\s_]", "", citation_norm).upper()
        matched_id = node_lookup.get(lookup_key)

        if matched_id:
            matched_node = nodes[matched_id]
            kg_weight = getattr(matched_node, "authority_weight",
                                AUTHORITY_WEIGHTS.get(
                                    getattr(matched_node, "node_type", ""), 0.5))
            resolved_edges.append(Edge(
                source=edge.source,
                target=matched_id,
                relation="CITES_KG_NODE",
                weight=kg_weight,
                metadata={**edge.metadata, "resolved": True},
            ))
        else:
            stub_id = f"EXT_{citation_norm}"
            if stub_id not in new_stubs:
                inferred_type, court = _infer_type(citation_text)
                new_stubs[stub_id] = ExternalCitationNode(
                    node_id=stub_id,
                    citation_raw=citation_text,
                    inferred_type=inferred_type,
                    court=court,
                    authority_weight=INFERRED_WEIGHTS.get(inferred_type, 0.3),
                )
            resolved_edges.append(Edge(
                source=edge.source,
                target=stub_id,
                relation="CITES_EXTERNAL",
                weight=new_stubs[stub_id].authority_weight,
                metadata={**edge.metadata, "resolved": False},
            ))

    return resolved_edges, new_stubs


def segment_full_text(text: str) -> dict[str, str]:
    """
    Segments a full judicial decision into structural parts.
    Returns: {"header": ..., "abstract": ..., "report": ..., "vote": ...}
    """
    sections: dict[str, str] = {
        "header":   "",
        "abstract": "",
        "report":   "",
        "vote":     "",
    }

    relatorio_m = re.search(r"\bRELATÓRIO\b", text, re.IGNORECASE)
    voto_m      = re.search(r"\bVOTO\b",      text, re.IGNORECASE)

    if relatorio_m:
        sections["header"] = text[:relatorio_m.start()].strip()
        if voto_m and voto_m.start() > relatorio_m.end():
            sections["report"] = text[relatorio_m.end():voto_m.start()].strip()
            sections["vote"]   = text[voto_m.end():].strip()
        else:
            sections["report"] = text[relatorio_m.end():].strip()
    else:
        sections["header"] = text

    # Extract abstract (ementa) block
    ementa_m = re.search(r"\bEMENTA\b", text, re.IGNORECASE)
    if ementa_m:
        start = ementa_m.end()
        end_m = re.search(
            r"\n\s*\d+\.|Sustenta|Trata-se",
            text[start:],
            re.IGNORECASE,
        )
        if end_m:
            sections["abstract"] = text[start : start + end_m.start()].strip()
        else:
            sections["abstract"] = text[start : start + 1000].strip()

    return sections

# ============================================================
# Section 6: Graph Functions
# ============================================================

def build_networkx_graph(nodes: dict, edges: list[Edge]) -> nx.DiGraph:
    """
    Builds a NetworkX DiGraph from KG nodes and edges.
    Unresolved citation targets are added as placeholder nodes.
    Edge metadata is filtered to primitive types for GraphML compatibility.
    """
    G = nx.DiGraph()

    for node_id, node in nodes.items():
        d = asdict(node)
        label = (
            d.get("title")
            or d.get("thesis_text")
            or d.get("sub_ref")        # NormaSubNode
            or d.get("citation_raw")   # ExternalCitationNode
            or node_id
        )
        G.add_node(
            node_id,
            type=d.get("node_type", ""),
            label=label[:80],
            weight=d.get("authority_weight", 1.0),
        )

    for edge in edges:
        if edge.target not in G:
            G.add_node(
                edge.target,
                type="UnresolvedCitation",
                label=edge.target,
                weight=0.0,
            )
        # GraphML does not support nested dicts — keep only primitives
        safe_meta = {
            k: v for k, v in edge.metadata.items()
            if isinstance(v, (str, int, float, bool))
        }
        G.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation,
            weight=edge.weight,
            **safe_meta,
        )

    return G


def print_graph_summary(G: nx.DiGraph, norma_id: str) -> None:
    """Prints a structured summary of the KG graph statistics."""
    print(f"\n{'='*62}")
    print(f"  Graph Summary — {norma_id}")
    print(f"{'='*62}")
    print(f"  Nodes : {G.number_of_nodes()}")
    print(f"  Edges : {G.number_of_edges()}")

    node_types = Counter(d.get("type", "Unknown") for _, d in G.nodes(data=True))
    print("\n  Node type distribution:")
    for ntype, count in node_types.most_common():
        print(f"    {ntype:<38} {count:>4d}")

    edge_types = Counter(
        d.get("relation", "Unknown") for _, _, d in G.edges(data=True)
    )
    print("\n  Edge type distribution:")
    for etype, count in edge_types.most_common():
        print(f"    {etype:<38} {count:>4d}")

    print("\n  Top-5 nodes by in-degree:")
    top5 = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:5]
    for node_id, deg in top5:
        label = G.nodes[node_id].get("label", node_id)
        print(f"    [{deg:>3d}]  {label}")

    print(f"{'='*62}\n")

# ============================================================
# Section 7: run_pilot
# ============================================================

def run_pilot(fetch_full_text: bool = False) -> tuple[dict, list[Edge], nx.DiGraph]:
    """
    Full pipeline: Extract → Transform → NLP → Validate → Export.

    Args:
        fetch_full_text: If True, fetches full text for the top-5 leading
                         cases and runs citation extraction.

    Returns:
        (nodes, edges, G) — the KG node dict, edge list, and NetworkX graph.
    """
    extractor  = Corpus927Extractor()
    nlp_edges: list[Edge] = []

    # ── Step 1: Fetch API data ────────────────────────────────
    print(f"[Step 1] Fetching jurisprudencia for nrm:{NORMA_ID}|art:{ARTIGO_ID}...")
    api_data = extractor.fetch_jurisprudencia(NORMA_ID, ARTIGO_ID)

    jurs     = api_data.get("jurisprudencias", {})
    temas    = api_data.get("temas", {})
    grouped  = api_data.get("posicionamentos_agrupados_stj", [])
    isolated = api_data.get("posicionamentos_isolados", [])

    print(f"  Constitutional Control (type 90)  : {len(jurs.get('90', []))}")
    print(f"  RG_STF (type 70)                  : {len(jurs.get('70', []))}")
    print(f"  STJ Theses (type 110)             : {len(jurs.get('110', []))}")
    print(f"  Repetitive Topics (key '60')      : {len(temas.get('60', []))}")
    print(f"  Grouped positions                 : {len(grouped)}")
    print(f"  Isolated positions                : {len(isolated)}")

    # ── Step 1b: Fetch article text ───────────────────────────
    print(f"\n[Step 1b] Parsing article text from legislation page...")
    article_data = extractor.fetch_article_text(NORMA_ID, ARTIGO_ID)
    if article_data:
        total_incises = sum(len(v) for v in article_data["incises"].values())
        print(f"  Caput     : {article_data['caput'][:70]}...")
        print(f"  Paragraphs: {len(article_data['paragraphs'])}")
        print(f"  Incises   : {total_incises}")
    else:
        print("  WARNING: Could not extract article text from legislation page")

    # ── Step 2: Transform → KG ───────────────────────────────
    print("\n[Step 2] Building Knowledge Graph...")
    norma_node  = NormaNode(node_id="CDC_art18", law="CDC", article=18)
    transformer = KGTransformer(norma_node)
    nodes, edges = transformer.build(api_data)
    print(f"  Nodes : {len(nodes)}")
    print(f"  Edges : {len(edges)}")

    # ── Step 2b: Populate sub-article nodes ──────────────────
    print("\n[Step 2b] Expanding NormaNode into sub-article nodes...")
    transformer.populate_norma_sub_nodes(article_data)
    nodes = transformer.nodes
    edges = transformer.edges
    sub_nodes = [n for n in nodes.values() if isinstance(n, NormaSubNode)]
    print(f"  Sub-nodes added : {len(sub_nodes)}"
          f"  ({sum(1 for n in sub_nodes if n.sub_type == 'paragraph')} paragraphs, "
          f"{sum(1 for n in sub_nodes if n.sub_type == 'incise')} incises)")
    print(f"  Total nodes now : {len(nodes)}")

    # ── Step 3: NLP enrichment (optional) ────────────────────
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

        # Resolve to CITES_KG_NODE / CITES_EXTERNAL
        resolved_edges, stub_nodes = resolve_citations(raw_cit_edges, nodes)
        nodes.update(stub_nodes)
        nlp_edges.extend(resolved_edges)
        kg_nodes_hits  = sum(1 for e in resolved_edges if e.relation == "CITES_KG_NODE")
        ext_stubs_hits = sum(1 for e in resolved_edges if e.relation == "CITES_EXTERNAL")
        print(f"  Citation resolution: {kg_nodes_hits} KG matches, "
              f"{ext_stubs_hits} external stubs ({len(stub_nodes)} unique)")

        edges = edges + nlp_edges
        print(f"  Total edges after NLP: {len(edges)}")
    else:
        print("\n[Step 3] Skipped (fetch_full_text=False)")

    # ── Step 4: Symbolic validation ──────────────────────────
    print("\n[Step 4] Running symbolic validations...")
    validations: dict[str, bool] = {}

    # V1: at least one INTERPRETED_BY_BINDING_THESIS edge exists
    v1 = any(e.relation == "INTERPRETED_BY_BINDING_THESIS" for e in edges)
    validations["V1_binding_thesis_exists"] = v1
    print(f"  V1 – Binding thesis edge exists          : {'PASS' if v1 else 'FAIL'}")

    # V2: all edge weights in [0.0, 1.0]
    v2 = all(0.0 <= e.weight <= 1.0 for e in edges)
    validations["V2_weights_in_range"] = v2
    print(f"  V2 – All weights in [0.0, 1.0]           : {'PASS' if v2 else 'FAIL'}")

    # V3: all nodes have a non-empty node_type
    v3 = all(getattr(n, "node_type", "") != "" for n in nodes.values())
    validations["V3_all_nodes_typed"] = v3
    print(f"  V3 – All nodes have non-empty node_type  : {'PASS' if v3 else 'FAIL'}")

    # V4: all CONTROLLED_BY edges originate from a LegalProvision node
    v4 = all(
        getattr(nodes.get(e.source), "node_type", "") == "LegalProvision"
        for e in edges if e.relation == "CONTROLLED_BY"
    )
    validations["V4_controlled_by_source"] = v4
    print(f"  V4 – CONTROLLED_BY from LegalProvision   : {'PASS' if v4 else 'FAIL'}")

    # ── Step 5: Build graph and export ───────────────────────
    print("\n[Step 5] Building NetworkX graph and exporting...")
    G = build_networkx_graph(nodes, edges)
    print_graph_summary(G, f"CDC Art. {ARTIGO_ID}")

    # Top-5 cases by authority weight
    case_nodes = [
        (nid, n) for nid, n in nodes.items() if isinstance(n, CaseNode)
    ]
    top5_cases = sorted(case_nodes, key=lambda x: x[1].authority_weight, reverse=True)[:5]
    if top5_cases:
        print("  Top-5 cases by authority_weight:")
        for _, n in top5_cases:
            print(f"    [{n.authority_weight:.4f}]  {n.title[:60]}")
        print()

    # Export JSON
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
    json_path = "kg_pilot_art18.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)
    print(f"  Exported: {json_path}")

    # Export GraphML
    graphml_path = "kg_pilot_art18.graphml"
    nx.write_graphml(G, graphml_path)
    print(f"  Exported: {graphml_path}")

    return nodes, edges, G

# ============================================================
# Section 8: LLM Citation Classifier
# ============================================================

def classify_citations_llm(
    edges: list[Edge],
    llm_fn: Callable[[str], str],
    confidence_threshold: float = 0.7,
) -> list[Edge]:
    """
    Classifies CITES edges using an LLM, updating relation type and weight.

    Only processes edges where:
      - relation == "CITES"
      - metadata["needs_llm_classification"] == True

    Args:
        edges: Full list of KG edges.
        llm_fn: Callable that accepts a prompt string and returns a string.
        confidence_threshold: Weight below this value flags for expert review.

    Returns:
        The same edge list with updated relation/weight/metadata.
    """
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

    classified   = 0
    needs_review = 0

    for edge in edges:
        if edge.relation != "CITES":
            continue
        if not edge.metadata.get("needs_llm_classification", False):
            continue

        prompt = PROMPT_TEMPLATE.format(
            citation_text=edge.metadata.get("citation_text", ""),
            context=edge.metadata.get("context", ""),
        )
        try:
            raw_response = llm_fn(prompt)
            label = raw_response.strip().upper()
            valid_label = label in RELATION_WEIGHTS
            if not valid_label:
                label = "SUPPORTS"  # safe fallback
            weight = RELATION_WEIGHTS[label]
            edge.relation = label
            edge.weight   = weight
            edge.metadata["llm_raw_output"]          = raw_response.strip()
            edge.metadata["needs_llm_classification"] = False
            edge.metadata["needs_expert_review"]      = (
                not valid_label or weight < confidence_threshold
            )
            classified += 1
            if edge.metadata["needs_expert_review"]:
                needs_review += 1
        except Exception as exc:
            edge.metadata["llm_error"] = str(exc)

    print(f"[LLM] Classified: {classified} | Needs expert review: {needs_review}")
    return edges

# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    nodes, edges, G = run_pilot(fetch_full_text=True)

    # ── LLM integration (uncomment to activate) ─────────────
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
    #
    # # Re-export GraphML with classified citation edges
    # G_classified = build_networkx_graph(nodes, edges)
    # nx.write_graphml(G_classified, "kg_pilot_art18_classified.graphml")
    # print("Exported: kg_pilot_art18_classified.graphml")
