import re
import math
from typing import Any

from config import AUTHORITY_WEIGHTS, BASE_URL, CDC_ART_RE
from models import (
    NormaNode, NormaSubNode, CaseNode, TopicNode, STJThesisNode,
    ConstitutionalControlNode, RG_STFNode, Edge,
)


class KGTransformer:
    def __init__(self, norma_node: NormaNode):
        self.norma = norma_node
        self.nodes: dict[str, Any] = {norma_node.node_id: norma_node}
        self.edges: list[Edge] = []

    def _clean_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text or "").strip()

    def _make_case_id(self, title: str) -> str:
        cleaned = title.strip().replace("/", "_").replace(".", "").replace(",", "")
        return re.sub(r"\s+", "_", cleaned)

    def _sanitize_node_id(self, raw: str) -> str:
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", raw)
        ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
        return re.sub(r"[^A-Za-z0-9_\-]", "_", ascii_str)

    # ── RG_STF ──────────────────────────────────────────────────────────────
    def process_rg_stf(self, items: list):
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
                source=self.norma.node_id, target=node_id,
                relation=relation, weight=weight,
                metadata={"has_rg": has_rg, "situacao": situacao},
            ))

    # ── Constitutional Control ───────────────────────────────────────────────
    def process_constitutional_control(self, items: list):
        for item in items:
            raw_title = item.get("titulo", "")
            node_id = "CC_" + re.sub(r"[\s/]+", "_", raw_title.strip())
            ativo = item.get("ativo", True)
            node = ConstitutionalControlNode(
                node_id=node_id,
                title=raw_title,
                process_number=str(item.get("numero_processo", "")),
                summary=self._clean_html(item.get("conteudo", "")),
                publication_date=item.get("data_publicacao", ""),
                source_url=item.get("url_origem", ""),
                temporal_status="active" if ativo else "inactive",
            )
            self.nodes[node_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id, target=node_id,
                relation="CONTROLLED_BY", weight=1.0,
                metadata={"type": "constitutional_control"},
            ))

    # ── Repetitive Topics ────────────────────────────────────────────────────
    def process_topics(self, temas_dict: dict):
        items = temas_dict.get("60", [])
        for item in items:
            raw_title = item.get("titulo", "")
            num_match = re.search(r"(\d+)\s*$", raw_title)
            num = num_match.group(1) if num_match else re.sub(r"\s+", "_", raw_title.strip())
            node_id = f"Topic_{num}"
            status = item.get("situacao", "")
            authority_weight = 1.0 if "Julgado" in status else 0.8
            node = TopicNode(
                node_id=node_id,
                title=raw_title,
                thesis=self._clean_html(item.get("tese", "")),
                ementa=self._clean_html(item.get("conteudo", "")),
                question=self._clean_html(item.get("tema", "")),
                status=status,
                status_confirmed=bool(item.get("situacao_confirmada", False)),
                publication_date=item.get("data_publicacao", ""),
                source_url=item.get("url_origem", ""),
            )
            self.nodes[node_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id, target=node_id,
                relation="INTERPRETED_BY_BINDING_THESIS", weight=authority_weight,
                metadata={"status": status},
            ))
            self._extract_thesis_article_citations(node_id, node.thesis + " " + node.question)

    # ── STJ Theses ───────────────────────────────────────────────────────────
    def process_stj_theses(self, items: list):
        for item in items:
            header = item.get("cabecalho", {})
            edition_title = header.get("titulo", "")
            edition_slug = self._sanitize_node_id(re.sub(r"[\s/]+", "_", edition_title.strip()))
            theses = item.get("teses", [])
            source_url = header.get("url_origem", "")
            seen_thesis_ids: set[str] = set()
            for idx, thesis_text in enumerate(theses, start=1):
                num_match = re.match(r"^(\d+)\)", thesis_text.strip())
                num = num_match.group(1) if num_match else str(idx)
                node_id = f"STJThesis_{edition_slug}_t{num}"
                if node_id in seen_thesis_ids:
                    continue
                seen_thesis_ids.add(node_id)
                cleaned_text = self._clean_html(thesis_text)
                node = STJThesisNode(
                    node_id=node_id, edition=edition_title,
                    thesis_text=cleaned_text, source_url=source_url,
                )
                self.nodes[node_id] = node
                self.edges.append(Edge(
                    source=self.norma.node_id, target=node_id,
                    relation="SUMMARIZED_BY_STJ_THESIS", weight=0.9,
                    metadata={"edition": edition_title},
                ))
                self._extract_thesis_article_citations(node_id, cleaned_text)

    # ── Grouped Positions (Leading Cases) ────────────────────────────────────
    def process_grouped_positions(self, items: list):
        if not items:
            return
        max_similar = max(item.get("semelhantes", 0) for item in items)
        for item in items:
            similar_count = item.get("semelhantes", 0)
            weight = (
                math.log(1 + similar_count) / math.log(1 + max_similar)
                if max_similar > 0 else 0.0
            )
            raw_title = item.get("titulo", "")
            case_id = self._make_case_id(raw_title)
            hash_it = item.get("hash_it", "")
            class_match = re.match(r"^([A-Za-z]+)", raw_title.strip())
            inferred_class = class_match.group(1) if class_match else ""
            node = CaseNode(
                node_id=case_id, title=raw_title, full_text_hash=hash_it,
                publication_date=item.get("data_publicacao", ""),
                rapporteur=item.get("relator", ""), adjudicating_body="",
                case_class=inferred_class,
                summary=self._clean_html(item.get("conteudo", "")),
                full_text_url=f"{BASE_URL}/inteiro-teor/{hash_it}" if hash_it else "",
                authority_weight=round(weight, 4), similar_count=similar_count,
                court="STJ", corpus_id=item.get("jurisprudencia_id", 0),
            )
            self.nodes[case_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id, target=case_id,
                relation="INTERPRETED_BY_LEADING_CASE", weight=round(weight, 4),
                metadata={
                    "semelhantes": similar_count, "is_leading_case": True,
                    "dispositivo_legal_id": item.get("dispositivo_legal_id", ""),
                    "nome_corpus": item.get("nome_corpus", ""),
                },
            ))

    # ── Isolated Positions ───────────────────────────────────────────────────
    def process_isolated_positions(self, items: list):
        for item in items:
            raw_title = item.get("titulo", "")
            case_id = self._make_case_id(raw_title)
            if case_id in self.nodes:
                continue
            hash_it = item.get("hash_it", "")
            node = CaseNode(
                node_id=case_id, title=raw_title, full_text_hash=hash_it,
                publication_date=item.get("data_publicacao", ""),
                rapporteur=item.get("relator", ""),
                adjudicating_body=item.get("orgao_julgador", ""),
                case_class=item.get("sigla_classe", ""),
                summary=self._clean_html(item.get("conteudo", "")),
                full_text_url=f"{BASE_URL}/inteiro-teor/{hash_it}" if hash_it else "",
                authority_weight=0.3, similar_count=0,
                origin_state=item.get("uf", ""),
                court=item.get("origem", "STJ"),
                corpus_id=item.get("documento_id", 0),
            )
            self.nodes[case_id] = node
            self.edges.append(Edge(
                source=self.norma.node_id, target=case_id,
                relation="INTERPRETED_BY_ISOLATED_CASE", weight=0.3,
                metadata={"is_leading_case": False},
            ))

    # ── Sub-article decomposition ────────────────────────────────────────────
    def populate_norma_sub_nodes(self, article_data: dict):
        if not article_data:
            return
        law, art = self.norma.law, self.norma.article
        prefix = f"{law}_art{art}"
        self.norma.text = article_data.get("caput", "")

        for par_ref, par_text in article_data.get("paragraphs", {}).items():
            par_num_m = re.search(r"(\d+)", par_ref)
            par_num = par_num_m.group(1) if par_num_m else re.sub(r"\W", "", par_ref)
            par_id = f"{prefix}_par{par_num}"
            par_node = NormaSubNode(
                node_id=par_id, law=law, article=art,
                sub_ref=par_ref, sub_type="paragraph",
                text=par_text, parent_id=self.norma.node_id,
            )
            self.nodes[par_id] = par_node
            self.edges.append(Edge(
                source=self.norma.node_id, target=par_id,
                relation="HAS_SUB_PROVISION", weight=1.0,
                metadata={"sub_type": "paragraph", "sub_ref": par_ref},
            ))
            for inc_ref, inc_text in article_data.get("incises", {}).get(par_ref, {}).items():
                inc_id = f"{par_id}_inc{inc_ref}"
                self.nodes[inc_id] = NormaSubNode(
                    node_id=inc_id, law=law, article=art,
                    sub_ref=inc_ref, sub_type="incise",
                    text=inc_text, parent_id=par_id,
                )
                self.edges.append(Edge(
                    source=par_id, target=inc_id,
                    relation="HAS_INCISE", weight=1.0,
                    metadata={"sub_type": "incise", "sub_ref": inc_ref},
                ))

    # ── Thesis article citation extraction ───────────────────────────────────
    def _extract_thesis_article_citations(self, source_id: str, text: str):
        matches = CDC_ART_RE.findall(text)
        seen: set[str] = set()
        for art_num in matches:
            if art_num in seen:
                continue
            seen.add(art_num)
            target_id = f"CDC_art{art_num}"
            if target_id not in self.nodes:
                self.nodes[target_id] = NormaNode(
                    node_id=target_id, law="CDC", article=int(art_num), is_stub=True,
                )
            self.edges.append(Edge(
                source=source_id, target=target_id,
                relation="CITES_ARTICLE", weight=1.0,
                metadata={"cited_article": int(art_num), "law": "CDC",
                          "is_stub_target": target_id not in self.nodes},
            ))

    def build(self, api_response: dict) -> tuple[dict, list[Edge]]:
        jurs  = api_response.get("jurisprudencias", {})
        temas = api_response.get("temas", {})
        self.process_constitutional_control(jurs.get("90", []))
        self.process_rg_stf(jurs.get("70", []))
        self.process_stj_theses(jurs.get("110", []))
        self.process_topics(temas)
        self.process_grouped_positions(api_response.get("posicionamentos_agrupados_stj", []))
        self.process_isolated_positions(api_response.get("posicionamentos_isolados_stj", []))
        return self.nodes, self.edges
