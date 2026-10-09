#!/usr/bin/env python3
"""Texte intégral des articles qui ont leur propre page HTML ou leur propre PDF.

Pour chaque article de data/cps.sqlite :
  - url_html : la page est téléchargée et convertie en texte ;
  - sinon url_pdf, s'il s'agit d'un PDF propre à l'article (pas du PDF du
    numéro entier, pas d'une page de PDF) : pdftotext.
Les textes des numéros complets et des suppléments (un PDF = une publication)
sont traités par extraire_pages.py.

Sortie : data/textes/<id_article>.txt et data/textes/index.json.
Usage : python3 scripts/fetch_textes.py [--refresh]
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "articles"
OUT = ROOT / "data" / "textes"
USER_AGENT = "cps-database/1.0 (archivage)"
BLOCS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "td", "tr", "table", "blockquote", "ul", "ol", "pre"]


def telecharger(url):
    nom = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1].split("#")[0])
    dest = CACHE / nom
    if dest.exists():
        return dest.read_bytes()
    for essai in range(4):
        try:
            req = urllib.request.Request(url.split("#")[0], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            time.sleep(0.3)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None
            time.sleep(2 ** (essai + 1))
        except Exception:
            time.sleep(2 ** (essai + 1))
    return None


def decoder(data):
    m = re.search(rb"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", data[:4000])
    enc = m.group(1).decode() if m else None
    for e in [enc, "utf-8", "cp1252"]:
        if not e:
            continue
        try:
            return data.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("cp1252", "replace")


def html_vers_texte(data):
    soup = BeautifulSoup(decoder(data), "html.parser")
    for t in soup(["script", "style", "head", "title", "meta", "link", "xml", "noscript"]):
        t.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    # le HTML exporté par Word coupe les lignes au milieu des phrases : on
    # aplatit d'abord les espaces, puis on marque les fins de blocs
    for s in list(soup.find_all(string=True)):
        s.replace_with(NavigableString(re.sub(r"\s+", " ", str(s))))
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for b in soup.find_all(BLOCS):
        b.insert_before("\n\n")
        b.insert_after("\n\n")
    texte = soup.get_text("")
    texte = texte.replace(" ", " ")
    lignes = [l.strip() for l in texte.split("\n")]
    texte = "\n".join(lignes)
    return re.sub(r"\n{3,}", "\n\n", texte).strip()


def pdf_vers_texte(data):
    res = subprocess.run(["pdftotext", "-enc", "UTF-8", "-", "-"], input=data, capture_output=True)
    t = res.stdout.decode("utf-8", "replace").replace("\f", "\n\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    db = sqlite3.connect(ROOT / "data" / "cps.sqlite")
    rows = db.execute("""
        SELECT a.id, a.url_html, a.url_pdf, a.pdf_page, p.url_pdf
        FROM articles a JOIN publications p ON p.id = a.publication_id
        ORDER BY a.date, a.id""").fetchall()
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "index.json"
    index = {} if args.refresh or not index_path.exists() else json.loads(index_path.read_text(encoding="utf-8"))
    par_source = {v["source"]: k for k, v in index.items() if v.get("statut") == "ok" and "identique_a" not in v}

    for n, (aid, url_html, url_pdf, page, pdf_pub) in enumerate(rows, 1):
        if url_html:
            src, typ = url_html.split("#")[0], "html"
        elif url_pdf and not page and url_pdf != pdf_pub:
            src, typ = url_pdf, "pdf"
        else:
            # plus rien à récupérer pour cet article (lien corrigé…) : on oublie l'ancienne entrée
            if index.pop(aid, None) is not None:
                (OUT / f"{aid}.txt").unlink(missing_ok=True)
            continue
        if aid in index and index[aid]["source"] == src and not args.refresh:
            continue
        if src in par_source:
            index[aid] = {**index[par_source[src]], "identique_a": par_source[src]}
            continue
        data = telecharger(src)
        if data is None:
            index[aid] = {"source": src, "type": typ, "statut": "introuvable"}
        else:
            if typ == "html" and data[:5] == b"%PDF-":
                typ = "pdf"
            texte = html_vers_texte(data) if typ == "html" else pdf_vers_texte(data)
            if len(texte) < 200:
                index[aid] = {"source": src, "type": typ, "statut": "vide_ou_scan", "caracteres": len(texte)}
            else:
                (OUT / f"{aid}.txt").write_text(texte + "\n", encoding="utf-8")
                index[aid] = {"source": src, "type": typ, "statut": "ok", "caracteres": len(texte)}
                par_source[src] = aid
        print(f"[{n}/{len(rows)}] {aid} {index[aid]['statut']} {src}", flush=True)
        if n % 20 == 0:
            index_path.write_text(json.dumps(dict(sorted(index.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    index_path.write_text(json.dumps(dict(sorted(index.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for v in index.values() if v.get("statut") == "ok")
    print(f"{ok} textes, {sum(1 for v in index.values() if v.get('statut') == 'introuvable')} introuvables", file=sys.stderr)


if __name__ == "__main__":
    main()
