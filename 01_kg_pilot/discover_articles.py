"""
Discovery script: scan artigo_id 1..50 in Corpus927 and report
which IDs exist, what article number they map to, and what data layers
are available (constitutional control, repetitive topics, cases, etc.).

Run: python discover_articles.py
Output: discover_articles.json
"""

import json
import re
import time

from extractor import Corpus927Extractor

NORMA_ID    = 1      # CDC
SCAN_RANGE  = range(1, 51)
OUTPUT_FILE = "output/discover_articles.json"


def scan_article(extractor: Corpus927Extractor, norma_id: int, artigo_id: int) -> dict:
    result = {
        "artigo_id":    artigo_id,
        "article_num":  None,   # parsed from caput text
        "has_text":     False,
        "has_cc":       False,  # constitutional control (type 90)
        "has_rg_stf":   False,  # RG STF (type 70)
        "has_theses":   False,  # STJ theses (type 110)
        "has_topics":   False,  # repetitive topics (key 60)
        "n_grouped":    0,
        "n_isolated":   0,
        "n_total_cases": 0,
        "error":        None,
    }

    # ── Article text (uses cached HTML — no extra request) ────────
    try:
        art_data = extractor.fetch_article_text(norma_id, artigo_id)
        if art_data:
            result["has_text"] = True
            caput = art_data.get("caput", "")
            # Parse "Art. 18 ." or "Art. 18." from caput
            m = re.search(r"Art\.\s*(\d+)", caput)
            if m:
                result["article_num"] = int(m.group(1))
    except Exception as e:
        result["error"] = f"text: {e}"

    # ── Jurisprudência API ────────────────────────────────────────
    try:
        data = extractor.fetch_jurisprudencia(norma_id, artigo_id)
        jurs     = data.get("jurisprudencias", {})
        temas    = data.get("temas", {})
        grouped  = data.get("posicionamentos_agrupados_stj", [])
        isolated = data.get("posicionamentos_isolados_stj", [])

        result["has_cc"]      = len(jurs.get("90", [])) > 0
        result["has_rg_stf"]  = len(jurs.get("70", [])) > 0
        result["has_theses"]  = len(jurs.get("110", [])) > 0
        result["has_topics"]  = len(temas.get("60", [])) > 0
        result["n_grouped"]   = len(grouped)
        result["n_isolated"]  = len(isolated)
        result["n_total_cases"] = len(grouped) + len(isolated)
    except Exception as e:
        if result["error"]:
            result["error"] += f" | jurs: {e}"
        else:
            result["error"] = f"jurs: {e}"

    return result


def main():
    import os
    os.makedirs("output", exist_ok=True)

    print("Initializing session...")
    extractor = Corpus927Extractor()
    print("Session ready. Starting scan...\n")

    header = f"{'artigo_id':>10} {'art_num':>8} {'text':>5} {'CC':>4} {'RG':>4} {'Teses':>6} {'Topic':>6} {'Group':>6} {'Isol':>5} {'Cases':>6}"
    print(header)
    print("-" * len(header))

    results = []
    for artigo_id in SCAN_RANGE:
        r = scan_article(extractor, NORMA_ID, artigo_id)
        results.append(r)

        art_num = str(r["article_num"]) if r["article_num"] else "?"
        print(
            f"{artigo_id:>10} {art_num:>8}"
            f"  {'✓' if r['has_text']   else '·':>4}"
            f"  {'✓' if r['has_cc']     else '·':>3}"
            f"  {'✓' if r['has_rg_stf'] else '·':>3}"
            f"  {'✓' if r['has_theses'] else '·':>5}"
            f"  {'✓' if r['has_topics'] else '·':>5}"
            f"  {r['n_grouped']:>5}"
            f"  {r['n_isolated']:>4}"
            f"  {r['n_total_cases']:>5}"
            + (f"  ⚠ {r['error']}" if r["error"] else "")
        )

    # ── Summary ───────────────────────────────────────────────────
    with_data = [r for r in results if r["n_total_cases"] > 0 or r["has_topics"] or r["has_cc"]]
    print(f"\n{'='*60}")
    print(f"  Scan complete: artigo_id 1–50")
    print(f"  Articles with any jurisprudência data : {len(with_data)}")
    print(f"  Articles with repetitive topics       : {sum(1 for r in results if r['has_topics'])}")
    print(f"  Articles with constitutional control  : {sum(1 for r in results if r['has_cc'])}")
    print(f"  Total cases across all articles       : {sum(r['n_total_cases'] for r in results)}")
    print(f"{'='*60}")

    # ── artigo_id → article_num mapping check ─────────────────────
    mismatches = [r for r in results if r["article_num"] and r["article_num"] != r["artigo_id"]]
    if mismatches:
        print("\n⚠  artigo_id ≠ article_num for:")
        for r in mismatches:
            print(f"    artigo_id={r['artigo_id']} → Art. {r['article_num']}")
    else:
        matched = [r for r in results if r["article_num"]]
        if matched:
            print(f"\n✓  artigo_id == article_num for all {len(matched)} articles found")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
