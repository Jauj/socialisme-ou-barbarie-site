#!/usr/bin/env python3
"""Texte intégral, page par page, des PDF de chaque publication (numéro, supplément…).

Pour chaque publication ayant un PDF :
  - téléchargement dans cache/pdf/ (non versionné) ;
  - si le PDF contient une couche texte : extraction avec pdftotext ;
  - sinon (scans de l'ancienne série et des premières années de la nouvelle) :
    OCR page par page avec Tesseract (langue fra), en parallèle.

Sortie : data/pages/<id_publication>.txt, pages séparées par un saut de page (\\f),
et data/pages/index.json (méthode, nombre de pages, URL source, statut).
Le script reprend là où il s'était arrêté (publications déjà traitées ignorées).

Dépendances : poppler-utils (pdftotext, pdftoppm, pdfinfo), tesseract-ocr + tesseract-ocr-fra.
Usage : python3 scripts/extraire_pages.py [--ids NS-097 AS-001 …] [--workers 4] [--garder-pdf]
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "pdf"
OUT = ROOT / "data" / "pages"
USER_AGENT = "cps-database/1.0 (archivage)"
SEUIL_TEXTE = 200  # caractères/page en moyenne en dessous desquels on considère le PDF comme un scan
RESOLUTION_OCR = 300


def telecharger(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for essai in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as r, open(str(dest) + ".part", "wb") as f:
                while True:
                    bloc = r.read(1 << 20)
                    if not bloc:
                        break
                    f.write(bloc)
            os.replace(str(dest) + ".part", dest)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            time.sleep(2 ** (essai + 1))
        except Exception:
            time.sleep(2 ** (essai + 1))
    return False


def nb_pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, errors="replace").stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def texte_natif(pdf):
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True)
    return out.stdout.decode("utf-8", "replace").split("\f")


def ocr_page(args):
    pdf, page = args
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "p"
        subprocess.run(["pdftoppm", "-r", str(RESOLUTION_OCR), "-gray", "-tiff", "-f", str(page), "-l", str(page),
                        "-singlefile", str(pdf), str(base)], check=True, capture_output=True)
        res = subprocess.run(["tesseract", str(base) + ".tif", "stdout", "-l", "fra", "--psm", "1"],
                             capture_output=True, env=env)
        return res.stdout.decode("utf-8", "replace")


def nettoyer(t):
    t = t.replace("\r", "").replace("\f", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", help="limiter à ces publications")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--garder-pdf", action="store_true", help="ne pas supprimer les PDF du cache après traitement")
    ap.add_argument("--sans-ocr", action="store_true", help="ne traiter que les PDF à couche texte")
    args = ap.parse_args()

    db = sqlite3.connect(ROOT / "data" / "cps.sqlite")
    pubs = db.execute("SELECT id, url_pdf FROM publications WHERE url_pdf IS NOT NULL AND pdf_disponible = 1 "
                      "ORDER BY date DESC").fetchall()
    if args.ids:
        pubs = [p for p in pubs if p[0] in set(args.ids)]
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    def sauver_index():
        index_path.write_text(json.dumps(dict(sorted(index.items())), ensure_ascii=False, indent=1), encoding="utf-8")

    # un même PDF peut servir à plusieurs publications : on le traite une fois
    deja_fait = {v["source"]: k for k, v in index.items() if v.get("statut") == "ok"}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (pid, url) in enumerate(pubs, 1):
            if pid in index and index[pid].get("statut") in ("ok", "introuvable") and index[pid]["source"] == url:
                continue
            if url in deja_fait:
                index[pid] = {**index[deja_fait[url]], "identique_a": deja_fait[url]}
                sauver_index()
                continue
            pdf = CACHE / url.rsplit("/", 1)[-1].replace("%20", " ")
            t0 = time.time()
            if not telecharger(url, pdf):
                index[pid] = {"source": url, "statut": "introuvable"}
                sauver_index()
                print(f"[{i}/{len(pubs)}] {pid} : PDF introuvable ({url})", flush=True)
                continue
            n = nb_pages(pdf)
            pages = texte_natif(pdf)
            if pages and pages[-1].strip() == "":
                pages = pages[:-1]
            total = sum(len(p.strip()) for p in pages)
            if n and total / n >= SEUIL_TEXTE:
                methode = "pdf_texte"
            elif args.sans_ocr:
                print(f"[{i}/{len(pubs)}] {pid} : scan, OCR ignoré (--sans-ocr)", flush=True)
                continue
            else:
                methode = "ocr_tesseract"
                pages = list(pool.map(ocr_page, [(pdf, k) for k in range(1, n + 1)]))
            pages = [nettoyer(p) for p in pages]
            (OUT / f"{pid}.txt").write_text("\f".join(pages) + "\n", encoding="utf-8")
            index[pid] = {"source": url, "statut": "ok", "methode": methode, "pages": len(pages),
                          "caracteres": sum(len(p) for p in pages)}
            deja_fait[url] = pid
            sauver_index()
            if not args.garder_pdf:
                pdf.unlink(missing_ok=True)
            print(f"[{i}/{len(pubs)}] {pid} : {methode}, {len(pages)} pages, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
