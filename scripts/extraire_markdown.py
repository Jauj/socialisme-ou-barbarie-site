#!/usr/bin/env python3
"""Versions Markdown des pages et des textes d'articles.

Produit, à côté des textes bruts :
  - data/pages/<publication>.md : Markdown de chaque page du PDF de la publication
    (pages séparées par un saut de page \\f, mêmes numéros que data/pages/<id>.txt) ;
      * PDF à couche texte : structure tirée des polices (pdftohtml -xml) ;
      * PDF océrisés : structure déduite du texte de Tesseract ;
  - data/textes/<article>.md : Markdown des articles qui ont leur propre page HTML
    ou leur propre PDF sur le site ; le .txt correspondant est régénéré à partir du
    Markdown (texte débarrassé des menus du site, paragraphes recousus).

Contrôle : pour chaque page, la part des mots du texte brut retrouvés dans le
Markdown ; une page PDF mal reconstruite (< 90 %) est refaite à partir du texte brut.
Le Markdown passe ensuite par nettoyage.py (bruit éditorial : bulletins d'abonnement,
mentions légales, bandeau de une, sommaires… ; intertitres coupés ou vides).

Usage : python3 scripts/extraire_markdown.py [--ids NS-097 …] [--garder-pdf]
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrections_ocr  # noqa: E402
import extraire_pages  # noqa: E402
import fetch_textes  # noqa: E402
import html_markdown  # noqa: E402
import nettoyage  # noqa: E402
import pdf_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "pages"
TEXTES = ROOT / "data" / "textes"
SEUIL_COUVERTURE = 0.90


def mots_norm(t):
    return [m.lower() for m in re.findall(r"\w+", t)]


def couverture(brut, md):
    """Part des mots du texte brut présents dans le Markdown (multiensemble)."""
    a = mots_norm(brut)
    if not a:
        return 1.0
    from collections import Counter
    cb, cm = Counter(a), Counter(mots_norm(html_markdown.markdown_vers_texte(md)))
    commun = sum(min(n, cm[w]) for w, n in cb.items())
    return commun / len(a)


def ordre(brut, md):
    """Similarité d'ordre des mots (détecte une colonne lue dans le mauvais sens)."""
    a, b = mots_norm(brut), mots_norm(html_markdown.markdown_vers_texte(md))
    if not a or not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", help="limiter à ces publications / articles")
    ap.add_argument("--garder-pdf", action="store_true")
    args = ap.parse_args()
    ids = set(args.ids or [])

    print("vocabulaire du corpus…", flush=True)
    vocab = pdf_markdown.vocabulaire_du_corpus(PAGES, TEXTES)

    rapport = {"pages_refaites": [], "articles": {}}

    # ---- pages des publications
    index = json.loads((PAGES / "index.json").read_text(encoding="utf-8"))
    for pid, m in sorted(index.items()):
        if m.get("statut") != "ok" or "identique_a" in m or (ids and pid not in ids):
            continue
        bruts = (PAGES / f"{pid}.txt").read_text(encoding="utf-8").rstrip("\n").split("\f")
        if m["methode"] == "ocr_tesseract":
            bruts = corrections_ocr.appliquer(pid, bruts)  # pages relues (data/corrections_ocr/)
            pages_md = [pdf_markdown.page_markdown_ocr(t, vocab) for t in bruts]
        else:
            pdf = extraire_pages.CACHE / m["source"].rsplit("/", 1)[-1].replace("%20", " ")
            if not extraire_pages.telecharger(m["source"], pdf):
                print(f"{pid} : PDF introuvable", flush=True)
                continue
            pages_md = pdf_markdown.pages_markdown_pdf(pdf, vocab)
            if len(pages_md) != len(bruts):
                print(f"{pid} : {len(pages_md)} pages Markdown pour {len(bruts)} pages texte, repli sur le texte brut")
                pages_md = [pdf_markdown.page_markdown_ocr(t, vocab) for t in bruts]
            else:
                for k, (brut, md) in enumerate(zip(bruts, pages_md)):
                    if len(brut.strip()) > 200 and (couverture(brut, md) < SEUIL_COUVERTURE or ordre(brut, md) < 0.6):
                        pages_md[k] = pdf_markdown.page_markdown_ocr(brut, vocab)
                        rapport["pages_refaites"].append(f"{pid} p.{k + 1}")
            if not args.garder_pdf:
                pdf.unlink(missing_ok=True)
        pages_md = [nettoyage.nettoyer(md, vocab, debut_document=(k == 0)).rstrip("\n") for k, md in enumerate(pages_md)]
        (PAGES / f"{pid}.md").write_text("\f".join(pages_md) + "\n", encoding="utf-8")
        print(f"{pid} : {m['methode']}, {len(pages_md)} pages", flush=True)

    # ---- textes propres aux articles (page HTML ou PDF de l'article)
    tindex = json.loads((TEXTES / "index.json").read_text(encoding="utf-8"))
    for aid, m in sorted(tindex.items()):
        if m.get("statut") != "ok" or "identique_a" in m or (ids and aid not in ids):
            continue
        data = fetch_textes.telecharger(m["source"])
        if data is None:
            print(f"{aid} : source introuvable", flush=True)
            continue
        if m["type"] == "html" and data[:5] != b"%PDF-":
            md = html_markdown.html_vers_markdown(data, m["source"])
        else:
            tmp = fetch_textes.CACHE / ("_md_" + aid + ".pdf")
            tmp.write_bytes(data)
            pages_md = pdf_markdown.pages_markdown_pdf(tmp, vocab)
            tmp.unlink(missing_ok=True)
            md = pdf_markdown.fusionner_paragraphes("\n\n".join(p for p in pages_md if p.strip()), vocab)
            md = html_markdown.nettoyer_markdown(md)
        md = nettoyage.nettoyer(md, vocab, debut_document=True, recoudre=(m["type"] != "html" or data[:5] == b"%PDF-"))
        ancien = (TEXTES / f"{aid}.txt").read_text(encoding="utf-8")
        cov = couverture(ancien, md)
        rapport["articles"][aid] = round(cov, 3)
        (TEXTES / f"{aid}.md").write_text(md, encoding="utf-8")
        (TEXTES / f"{aid}.txt").write_text(html_markdown.markdown_vers_texte(md) + "\n", encoding="utf-8")
    (ROOT / "cache").mkdir(exist_ok=True)
    (ROOT / "cache" / "rapport_markdown.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pages refaites à partir du texte brut : {len(rapport['pages_refaites'])}")
    faibles = {k: v for k, v in rapport["articles"].items() if v < 0.9}
    print(f"articles dont le Markdown couvre < 90 % de l'ancien texte : {len(faibles)} {faibles}")


if __name__ == "__main__":
    main()
