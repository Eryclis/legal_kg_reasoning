import re
import time

import requests
from bs4 import BeautifulSoup

from config import BASE_URL, RATE_LIMIT, HEADERS


class Corpus927Extractor:
    def __init__(self, base_url: str = BASE_URL, rate_limit: float = RATE_LIMIT):
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._init_session()

    def _init_session(self):
        resp = self.session.get(f"{self.base_url}/legislacao/cdc-90", timeout=30)
        resp.raise_for_status()
        self._legislacao_html = resp.text
        xsrf = self.session.cookies.get("XSRF-TOKEN", "")
        if xsrf:
            self.session.headers.update({
                "x-xsrf-token": requests.utils.unquote(xsrf),
                "x-requested-with": "XMLHttpRequest",
            })
        time.sleep(self.rate_limit)

    def fetch_article_text(self, norma_id: int, artigo_id: int) -> dict:
        soup = BeautifulSoup(self._legislacao_html, "html.parser")
        ng_val = f"buscarJurisprudencia($event,'nrm:{norma_id}|art:{artigo_id}')"
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
            if el.find("a", attrs={"ng-click": True}):
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
                inc_key = raw_key.upper() if re.fullmatch(r"[IVX]+", raw_key) else raw_key
                result["incises"][current_par][inc_key] = text

        return result

    def fetch_jurisprudencia(self, norma_id: int, artigo_id: int) -> dict:
        url = f"{self.base_url}/jurisprudencia/nrm:{norma_id}%7Cart:{artigo_id}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        time.sleep(self.rate_limit)
        return resp.json()

    def fetch_full_text(self, hash_it: str) -> str:
        url = f"{self.base_url}/inteiro-teor/{hash_it}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(self.rate_limit)
        soup = BeautifulSoup(resp.text, "html.parser")
        el = soup.find(id="conteudoInteiroTeor")
        return el.get_text(separator="\n", strip=True) if el else ""
