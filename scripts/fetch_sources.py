#!/usr/bin/env python3
"""Télécharge les pages sources de socialisme.free.fr dans sources/.

Pages récupérées :
  - sommaire.php            : liste de toutes les publications (numéros, suppléments, articles)
  - recherchethem.php       : index thématique (liste des tags)
  - recherchethem.php?tag=X : une page par tag (articles associés)

Les fichiers déjà présents ne sont pas retéléchargés, sauf avec --refresh.
Usage : python3 scripts/fetch_sources.py [--refresh]
"""
import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://socialisme.free.fr/"
ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"
USER_AGENT = "cps-database/1.0 (archivage; contact via depot GitHub)"
DELAY = 1.0  # secondes entre deux requêtes, pour ménager l'hébergement free.fr


def fetch(url, dest, refresh=False, retries=4):
    if dest.exists() and not refresh:
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
            time.sleep(DELAY)
            return data
        except Exception as exc:  # réseau capricieux : on réessaie
            wait = 2 ** (attempt + 1)
            print(f"  erreur {exc!r} sur {url}, nouvel essai dans {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"échec du téléchargement : {url}")


def tag_filename(slug):
    return "tag_" + urllib.parse.quote(slug, safe="") + ".html"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="retélécharger même si déjà en cache")
    args = ap.parse_args()

    print("sommaire.php")
    fetch(BASE + "sommaire.php", SOURCES / "sommaire.html", args.refresh)
    print("recherchethem.php (liste des tags)")
    index = fetch(BASE + "recherchethem.php?tag=null", SOURCES / "index_thematique.html", args.refresh)

    slugs = sorted(set(re.findall(r'recherchethem\.php\?tag=([^"&\']+)', index.decode("utf-8", "replace"))))
    slugs = [s for s in slugs if s != "null"]
    print(f"{len(slugs)} tags")
    for slug in slugs:
        url = BASE + "recherchethem.php?tag=" + urllib.parse.quote(slug)
        fetch(url, SOURCES / "tags" / tag_filename(slug), args.refresh)
    print("terminé")


if __name__ == "__main__":
    main()
