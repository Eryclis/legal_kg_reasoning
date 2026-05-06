import re

BASE_URL   = "https://corpus927.enfam.jus.br"
NORMA_ID   = 1        # CDC = nrm:1
ARTIGO_ID  = 18       # Art. 18
RATE_LIMIT = 1.0      # seconds between requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (KG-Pilot-Research/1.0)",
    "Accept": "application/json, text/html",
}

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

AUTHORITY_WEIGHTS: dict[str, float] = {
    "ConstitutionalControl": 1.00,
    "RG_STF":                0.95,
    "RepetitiveTopic":       0.90,
    "STJThesis":             0.80,
}

# Matches "art. 26 do CDC", "artigo 18, §1°, do CDC", etc.
# Does NOT match "art. 7º da Lei 8.137/1990" (no CDC anchor)
CDC_ART_RE = re.compile(
    r"art(?:igo)?\.?\s*(\d+)(?:[°º])?"
    r"(?:[,\s]+(?:§\s*\d+[°º]?|inciso\s+[IVX]+|[IVX]+[,\s]|caput))*"
    r"[,\s]*(?:do\s+)?(?:CDC|Código\s+de\s+Defesa(?:\s+do\s+Consumidor)?)",
    re.IGNORECASE,
)

# Canonical Brazilian judicial citation:
#   (CASE_CLASS n. NUMBER/STATE, TURMA, Rel. Min. NAME, DJe de DATE)
CANONICAL_CITATION_RE = re.compile(
    r"\("
    r"(?P<case_class>[A-Za-z]+(?:\s+(?:no|nos|na|nas)\s+[A-Za-z]+)?)"
    r"\s+(?:n[oº°]?\.\s*)?"
    r"(?P<case_number>[\d.,]+)"
    r"(?:/(?P<origin_state>[A-Z]{2,3}))?"
    r",\s*"
    r"(?P<adjudicating_body>[^,]+?)"
    r",\s*[Rr]el(?:ator)?\.?\s*(?:[Mm]in\.\s*)?"
    r"(?P<rapporteur>[^,]+?)"
    r",\s*DJe\s+(?:de\s+)?"
    r"(?P<decision_date>[^)]+?)"
    r"\)",
    re.IGNORECASE | re.UNICODE,
)
