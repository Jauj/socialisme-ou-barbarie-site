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

OCR : chaque page est rendue à la résolution native du scan (pdfimages -list ; les scans
de CPS sont en noir et blanc à 400 ppp), bornée entre 300 et 600 dpi. Avec --tessdata, un
autre modèle Tesseract peut être utilisé ; le modèle « best » (tessdata_best, ou sa version
entière du paquet npm @tesseract.js-data/fra : 4.0.0_best_int) supprime les confusions
systématiques du modèle standard (« Île » pour « le », « 11 » pour « Il », « Ja » pour « la »).
--refaire-ocr refait l'OCR des publications scannées déjà traitées et garde, page par page,
la meilleure des deux versions (part de mots inconnus d'un vocabulaire tiré des textes non
océrisés, et nombre de ces confusions).

Pages images : dans un PDF à couche texte, une page presque sans texte qui porte une grande
image, ou dont l'essentiel est une image sous une ligne de texte (tract, supplément ou article
reproduits en image), est océrisée ; le texte obtenu est gardé s'il est lisible (part de mots
inconnus du corpus) et s'il apporte bien plus que la couche texte. Leurs numéros sont notés
dans index.json (« pages_ocr »). --ocr-pages-images le fait pour les publications déjà traitées.

Dépendances : poppler-utils (pdftotext, pdftoppm, pdfinfo, pdfimages), tesseract-ocr + tesseract-ocr-fra.
Usage : python3 scripts/extraire_pages.py [--ids NS-097 AS-001 …] [--workers 4] [--garder-pdf]
                                          [--tessdata DOSSIER] [--refaire-ocr] [--ocr-pages-images]
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
# pages images d'un PDF à couche texte : moins de SEUIL_PAGE_IMAGE caractères et une image dont
# le petit côté fait au moins COTE_IMAGE pixels, ou moins de SEUIL_PAGE_PARTIELLE caractères
# (en-tête, légende) et une image qui couvre au moins PART_IMAGE de la page ; OCR gardé s'il
# donne au moins MIN_MOTS_OCR mots de plus que le double de ceux de la couche texte, dont au plus
# MAX_INCONNUS_OCR d'inconnus du corpus (pas une photo, un dessin)
SEUIL_PAGE_IMAGE = 80
COTE_IMAGE = 500
SEUIL_PAGE_PARTIELLE = 700
PART_IMAGE = 0.5
MIN_MOTS_OCR = 50
MAX_INCONNUS_OCR = 0.25
VERSION_PAGES_IMAGES = 2  # critères ci-dessus : une publication traitée avec d'autres critères est revue


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


def resolution_native(pdf, page):
    """Résolution (ppp) de la plus grande image de la page, bornée entre 300 et 600."""
    out = subprocess.run(["pdfimages", "-f", str(page), "-l", str(page), "-list", str(pdf)],
                         capture_output=True, text=True, errors="replace").stdout
    meilleure, ppp = 0, RESOLUTION_OCR
    for ligne in out.splitlines()[2:]:
        c = ligne.split()
        if len(c) >= 14 and c[2] == "image" and c[3].isdigit() and c[12].isdigit():
            if int(c[3]) * int(c[4]) > meilleure:
                meilleure, ppp = int(c[3]) * int(c[4]), int(c[12])
    return min(600, max(300, ppp))


def grande_image(pdf, page):
    """La page porte-t-elle une image assez grande pour contenir du texte lisible ?"""
    out = subprocess.run(["pdfimages", "-f", str(page), "-l", str(page), "-list", str(pdf)],
                         capture_output=True, text=True, errors="replace").stdout
    for ligne in out.splitlines()[2:]:
        c = ligne.split()
        if len(c) >= 5 and c[2] == "image" and c[3].isdigit() and c[4].isdigit() \
                and min(int(c[3]), int(c[4])) >= COTE_IMAGE:
            return True
    return False


def part_image(pdf, page):
    """Part de la surface de la page couverte par sa plus grande image."""
    info = subprocess.run(["pdfinfo", "-f", str(page), "-l", str(page), str(pdf)],
                          capture_output=True, text=True, errors="replace").stdout
    m = re.search(r"^Page\s+\d+\s+size:\s+([\d.]+)\s+x\s+([\d.]+)", info, re.M)
    if not m:
        return 0.0
    surface = float(m.group(1)) * float(m.group(2))
    out = subprocess.run(["pdfimages", "-f", str(page), "-l", str(page), "-list", str(pdf)],
                         capture_output=True, text=True, errors="replace").stdout
    part = 0.0
    for ligne in out.splitlines()[2:]:
        c = ligne.split()
        if len(c) >= 14 and c[2] == "image" and all(x.isdigit() and int(x) for x in (c[3], c[4], c[12], c[13])):
            part = max(part, int(c[3]) / int(c[12]) * 72 * int(c[4]) / int(c[13]) * 72 / surface)
    return part


def _mots(texte):
    return re.findall(r"[^\W\d_]{3,}", texte)


def ocr_pages_images(pdf, pages, pool, tessdata, connus):
    """Pages images d'un PDF à couche texte (voir en tête) : remplace dans `pages` le texte des
    pages dont l'OCR est lisible ; renvoie leurs numéros (1 = première)."""
    candidates = [k for k, p in enumerate(pages, 1)
                  if (len(p.strip()) < SEUIL_PAGE_IMAGE and grande_image(pdf, k))
                  or (len(p.strip()) < SEUIL_PAGE_PARTIELLE and part_image(pdf, k) >= PART_IMAGE)]
    gardees = []
    for k, texte in zip(candidates, pool.map(ocr_page, [(pdf, k, tessdata) for k in candidates])):
        texte = nettoyer(texte)
        if len(_mots(texte)) >= MIN_MOTS_OCR + 2 * len(_mots(pages[k - 1])) \
                and qualite(texte, connus)[0] <= MAX_INCONNUS_OCR:
            pages[k - 1] = texte
            gardees.append(k)
    return gardees


def ocr_page(args):
    pdf, page, tessdata = args
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "p"
        subprocess.run(["pdftoppm", "-r", str(resolution_native(pdf, page)), "-gray", "-tiff", "-f", str(page),
                        "-l", str(page), "-singlefile", str(pdf), str(base)], check=True, capture_output=True)
        cmd = ["tesseract", str(base) + ".tif", "stdout", "-l", "fra", "--psm", "1"]
        if tessdata:
            cmd[3:3] = ["--tessdata-dir", str(tessdata)]
        res = subprocess.run(cmd, capture_output=True, env=env)
        return res.stdout.decode("utf-8", "replace")


CONFUSIONS = re.compile(r"(?<=[a-zé,] )Îles? |(?:^|[.!?] )11s? [a-zé]|(?<= )[Jj]a (?=[a-zé])|(?<= )ia (?=[a-zé])", re.M)


def vocabulaire_propre():
    """Mots (3 lettres et plus) des textes non océrisés : pages à couche texte, textes HTML."""
    from collections import Counter
    freq = Counter()
    index = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    textes = []
    for pid, m in index.items():
        if m.get("statut") == "ok" and m.get("methode") == "pdf_texte" and "identique_a" not in m:
            pages = (OUT / f"{pid}.txt").read_text(encoding="utf-8").split("\f")
            ocr = set(m.get("pages_ocr", {}).get("pages", []))  # pages images océrisées : exclues
            textes += [p for k, p in enumerate(pages, 1) if k not in ocr]
    textes += [f.read_text(encoding="utf-8") for f in sorted((ROOT / "data" / "textes").glob("*.txt"))]
    for t in textes:
        freq.update(w.lower() for w in re.findall(r"[^\W\d_]{3,}", t))
    return {w for w, n in freq.items() if n >= 2}


def qualite(texte, connus):
    """(part de mots inconnus, nombre de confusions typiques) d'une page océrisée."""
    ms = [w.lower() for w in re.findall(r"[^\W\d_]{3,}", texte)]
    return (sum(1 for w in ms if w not in connus) / len(ms) if ms else 0.0), len(CONFUSIONS.findall(texte))


def meilleure_une(ancienne, nouvelle, titres, nb_pages):
    """Page de une (1-2) : la version dont le sommaire imprimé apparie le plus d'articles du site.
    Le modèle « best » lit mieux le texte courant mais parfois moins bien les encadrés de sommaire
    (points de conduite pris pour des mots, renvoi « P.1 » lu « P. 4 »), qui guident le découpage."""
    import assemblage

    def apparies(texte):
        return len(assemblage.indices_sommaire(assemblage.sommaire_imprime([texte]), titres, nb_pages))
    return ancienne if titres and apparies(ancienne) > apparies(nouvelle) else nouvelle


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
    ap.add_argument("--tessdata", help="dossier du modèle Tesseract (fra.traineddata) à utiliser")
    ap.add_argument("--refaire-ocr", action="store_true",
                    help="refaire l'OCR des publications scannées et garder la meilleure version de chaque page")
    ap.add_argument("--ocr-pages-images", action="store_true",
                    help="océriser les pages images des PDF à couche texte déjà traités")
    args = ap.parse_args()
    modele = "fra " + (Path(args.tessdata).name if args.tessdata else "standard")

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
    connus = vocabulaire_propre() if args.refaire_ocr or args.ocr_pages_images else None
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (pid, url) in enumerate(pubs, 1):
            m = index.get(pid, {})
            if args.refaire_ocr and m.get("statut") == "ok" and m.get("methode") == "ocr_tesseract" \
                    and "identique_a" not in m and m.get("ocr", {}).get("modele") != modele:
                titres = [t for t, in db.execute("SELECT titre FROM articles WHERE publication_id = ? ORDER BY ordre", (pid,))]
                refaire_ocr(pid, url, m, pool, args, modele, connus, i, len(pubs), titres)
                sauver_index()
                continue
            if args.ocr_pages_images and m.get("statut") == "ok" and m.get("methode") == "pdf_texte" \
                    and "identique_a" not in m and m.get("source") == url \
                    and m.get("pages_ocr", {}).get("version", 1) < VERSION_PAGES_IMAGES:
                completer_pages_images(pid, url, m, pool, args, modele, connus, i, len(pubs))
                sauver_index()
                continue
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
            pages_ocr = None
            if n and total / n >= SEUIL_TEXTE:
                methode = "pdf_texte"
                if not args.sans_ocr:
                    connus = connus or vocabulaire_propre()
                    pages_ocr = ocr_pages_images(pdf, pages, pool, args.tessdata, connus)
            elif args.sans_ocr:
                print(f"[{i}/{len(pubs)}] {pid} : scan, OCR ignoré (--sans-ocr)", flush=True)
                continue
            else:
                methode = "ocr_tesseract"
                pages = list(pool.map(ocr_page, [(pdf, k, args.tessdata) for k in range(1, n + 1)]))
            pages = [nettoyer(p) for p in pages]
            (OUT / f"{pid}.txt").write_text("\f".join(pages) + "\n", encoding="utf-8")
            index[pid] = {"source": url, "statut": "ok", "methode": methode, "pages": len(pages),
                          "caracteres": sum(len(p) for p in pages)}
            if methode == "ocr_tesseract":
                index[pid]["ocr"] = {"modele": modele}
            if pages_ocr is not None:
                index[pid]["pages_ocr"] = {"pages": pages_ocr, "modele": modele, "version": VERSION_PAGES_IMAGES}
            deja_fait[url] = pid
            sauver_index()
            if not args.garder_pdf:
                pdf.unlink(missing_ok=True)
            print(f"[{i}/{len(pubs)}] {pid} : {methode}, {len(pages)} pages, {time.time() - t0:.0f}s", flush=True)


def completer_pages_images(pid, url, m, pool, args, modele, connus, i, total):
    """OCR des pages images d'une publication à couche texte déjà extraite."""
    t0 = time.time()
    pages = (OUT / f"{pid}.txt").read_text(encoding="utf-8").rstrip("\n").split("\f")
    deja = m.get("pages_ocr", {}).get("pages", [])
    if all(len(p.strip()) >= SEUIL_PAGE_PARTIELLE for k, p in enumerate(pages, 1) if k not in deja):
        return
    pdf = CACHE / url.rsplit("/", 1)[-1].replace("%20", " ")
    if not telecharger(url, pdf):
        print(f"[{i}/{total}] {pid} : PDF introuvable, pages inchangées", flush=True)
        return
    nouvelles = ocr_pages_images(pdf, pages, pool, args.tessdata, connus)
    if nouvelles:
        (OUT / f"{pid}.txt").write_text("\f".join(pages) + "\n", encoding="utf-8")
    gardees = sorted(set(deja) | set(nouvelles))
    m.update(caracteres=sum(len(p) for p in pages),
             pages_ocr={"pages": gardees, "modele": modele, "date": time.strftime("%Y-%m-%d"),
                        "version": VERSION_PAGES_IMAGES})
    if not args.garder_pdf:
        pdf.unlink(missing_ok=True)
    print(f"[{i}/{total}] {pid} : {len(nouvelles)} page(s) image océrisée(s) {nouvelles}, {time.time() - t0:.0f}s",
          flush=True)


def refaire_ocr(pid, url, m, pool, args, modele, connus, i, total, titres=()):
    """Nouvel OCR d'une publication scannée ; garde, page par page, la meilleure version
    (et, pour la une, celle dont le sommaire imprimé est le mieux lu)."""
    t0 = time.time()
    pdf = CACHE / url.rsplit("/", 1)[-1].replace("%20", " ")
    if not telecharger(url, pdf):
        print(f"[{i}/{total}] {pid} : PDF introuvable, OCR inchangé", flush=True)
        return
    anciennes = (OUT / f"{pid}.txt").read_text(encoding="utf-8").rstrip("\n").split("\f")
    n = nb_pages(pdf)
    nouvelles = [nettoyer(p) for p in pool.map(ocr_page, [(pdf, k, args.tessdata) for k in range(1, n + 1)])]
    if len(nouvelles) != len(anciennes):
        print(f"[{i}/{total}] {pid} : {len(nouvelles)} pages au lieu de {len(anciennes)}, OCR inchangé", flush=True)
        return
    gardees = []
    for ancienne, nouvelle in zip(anciennes, nouvelles):
        (inc_a, conf_a), (inc_n, conf_n) = qualite(ancienne, connus), qualite(nouvelle, connus)
        # la nouvelle version, sauf si elle est nettement moins lisible sans réduire les confusions
        gardees.append(nouvelle if inc_n <= inc_a + 0.01 or conf_n < conf_a else ancienne)
    for k in range(min(2, n)):
        gardees[k] = meilleure_une(anciennes[k], gardees[k], titres, n)
    remplacees = sum(1 for g, a in zip(gardees, anciennes) if g != a)
    (OUT / f"{pid}.txt").write_text("\f".join(gardees) + "\n", encoding="utf-8")
    m.update(caracteres=sum(len(p) for p in gardees),
             ocr={"modele": modele, "pages_remplacees": remplacees, "date": time.strftime("%Y-%m-%d")})
    avant = sum(len(CONFUSIONS.findall(p)) for p in anciennes)
    apres = sum(len(CONFUSIONS.findall(p)) for p in gardees)
    if not args.garder_pdf:
        pdf.unlink(missing_ok=True)
    print(f"[{i}/{total}] {pid} : nouvel OCR, {remplacees}/{n} pages remplacées, confusions {avant} → {apres}, "
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
