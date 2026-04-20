# ============================================================
# Corpus927 KG Pilot — Art. 18 CDC
# Pipeline: Extract → Transform → Load → NLP → Graph
# ============================================================
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
import networkx as nx
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
import time

# ── Config ───────────────────────────────────────────────────
BASE_URL    = "https://corpus927.enfam.jus.br"
NORMA_ID    = 1          # CDC = nrm:1
ARTIGO_ID   = 18         # Art. 18
RATE_LIMIT  = 1.0        # seconds between requests (be polite)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (KG-Pilot-Research/1.0)",
    "Accept": "application/json, text/html",
}

# ── Type code mappings ───────────────────────────────────────
JURS_TYPES = {
    90:  "ConstitutionalControl",
    70:  "RepetitiveAppeal",
    110: "JurisprudenceInTheses",
    100: "OtherType",
}
TEMAS_TYPES = {
    60: "RepetitiveTopic",
    80: "OtherTopic",
}

# ============================================================
# 1. DATA CLASSES (KG nodes)
# ============================================================
@dataclass
class NormaNode:
    """Node: Legal provision (article)"""
    node_id: str          # "CDC_art18"
    node_type: str = "LegalProvision"
    law: str = "CDC"
    article: int = 0
    text: str = ""        # article text (fill separately)

@dataclass
class CaseNode:
    """Node: Judicial decision"""
    node_id: str          # "REsp_1556132"
    node_type: str = "Case"
    title: str = ""
    full_text_hash: str = ""     # full-text document identifier
    publication_date: str = ""
    rapporteur: str = ""
    adjudicating_body: str = ""
    case_class: str = ""
    summary: str = ""            # first 500 chars
    full_text_url: str = ""
    # KG spec fields
    authority_weight: float = 0.0
    similar_count: int = 0

@dataclass
class TopicNode:
    """Node: Repetitive appeal topic (canonical thesis)"""
    node_id: str          # "Topic_449"
    node_type: str = "RepetitiveTopic"
    title: str = ""
    thesis: str = ""      # canonical thesis text — GOLD STANDARD
    status: str = ""      # "Transitado em Julgado" → maximum authority
    publication_date: str = ""
    source_url: str = ""

@dataclass
class STJThesisNode:
    """Node: STJ Jurisprudence in Theses (Editions)"""
    node_id: str          # "Edition83_thesis6"
    node_type: str = "STJThesis"
    edition: str = ""
    thesis_text: str = ""
    source_url: str = ""

@dataclass
class ConstitutionalControlNode:
    """Node: Constitutional Control decision"""
    node_id: str          # "ADI_5158"
    node_type: str = "ConstitutionalControl"
    title: str = ""
    summary: str = ""
    publication_date: str = ""

@dataclass
class Edge:
    """KG edge"""
    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)

# ============================================================
# 2. EXTRACTOR — API access layer
# ============================================================
class Corpus927Extractor:
    def __init__(self, base_url=BASE_URL, rate_limit=RATE_LIMIT):
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_jurisprudencia(self, norma_id: int, artigo_id: int) -> dict:
        """
        Calls the main API: /jurisprudencia/nrm:{N}|art:{M}
        Returns the full JSON with all layers.
        """
        url = f"{self.base_url}/jurisprudencia/nrm:{norma_id}%7Cart:{artigo_id}"
        resp = self.session.get(url, timeout=10)
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
# 3. TRANSFORMER — converts JSON → nodes and edges
# ============================================================
class KGTransformer:
    def __init__(self, norma_node: NormaNode):
        self.norma = norma_node
        self.nodes: dict[str, Any] = {norma_node.node_id: norma_node}
        self.edges: list[Edge] = []

    def _clean_html(self, text: str) -> str:
        """Strips HTML tags from content."""
        return BeautifulSoup(text or "", "html.parser").get_text(strip=True)

    def _make_case_id(self, title: str) -> str:
        return re.sub(r"\s+", "_", title.strip().replace("/", "_").replace(".", ""))

    # ── 3a. Constitutional Control ───────────────────────────
    def process_constitutional_control(self, items: list):
        """
        Type 90: ADI, ADC, ADPF linked to the article.
        Edge: norm --[CONTROLLED_BY]--> constitutional_control
        Logic: constitutional control defines the validity of the norm.
        """
        for item in items:
            node_id = f"CC_{item['titulo'].replace('/', '_').replace(' ', '_')}"
            node = ConstitutionalControlNode(
                node_id=node_id,
                title=item.get("titulo", ""),
                summary=self._clean_html(item.get("conteudo", ""))[:600],
                publication_date=item.get("data_publicacao", ""),
            )
            self.nodes[node_id] = node
            # Edge: norm is controlled by this constitutional decision
            self.edges.append(Edge(
                source=self.norma.node_id,
                target=node_id,
                relation="CONTROLLED_BY",
                weight=1.0,
                metadata={"type": "constitutional_control"}
            ))

    # ── 3b. Repetitive Topics ────────────────────────────────
    def process_topics(self, _topics: dict):
        """
        Type 60: Repetitive Appeal Topics.
        Edge: norm --[HAS_BINDING_TOPIC]--> topic
        Logic: binding topics represent the canonical legal thesis for the norm.
        """
        pass  # TODO: implement
