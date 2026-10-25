#!/usr/bin/env python3
"""Serveur web local pour l'explorateur ; il accepte aussi les requêtes partielles (HTTP Range).
La recherche plein texte lit l'index par morceaux entiers (data/recherche/, construit par
build_db.py) : `python3 -m http.server` convient aussi.

Usage : python3 scripts/serveur.py [--port 8000]   puis ouvrir http://localhost:8000/explorateur/
"""
import argparse
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


class Gestionnaire(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        plage = self.headers.get("Range")
        chemin = self.translate_path(self.path)
        if not plage or not os.path.isfile(chemin):
            return super().send_head()
        taille = os.path.getsize(chemin)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", plage.strip())
        if not m or not (m.group(1) or m.group(2)):
            return super().send_head()
        if m.group(1):
            debut = int(m.group(1))
            fin = min(int(m.group(2)), taille - 1) if m.group(2) else taille - 1
        else:  # « bytes=-N » : les N derniers octets
            debut, fin = max(0, taille - int(m.group(2))), taille - 1
        if debut >= taille or debut > fin:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{taille}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        f = open(chemin, "rb")
        f.seek(debut)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(chemin))
        self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
        self.send_header("Content-Length", str(fin - debut + 1))
        self.end_headers()
        self._reste = fin - debut + 1
        return f

    def copyfile(self, source, destination):
        reste = getattr(self, "_reste", None)
        if reste is None:
            return super().copyfile(source, destination)
        del self._reste
        while reste > 0:
            bloc = source.read(min(reste, 1 << 16))
            if not bloc:
                break
            destination.write(bloc)
            reste -= len(bloc)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--hote", default="127.0.0.1")
    args = ap.parse_args()
    serveur = ThreadingHTTPServer((args.hote, args.port), partial(Gestionnaire, directory=str(RACINE)))
    print(f"http://{args.hote}:{args.port}/explorateur/  (Ctrl+C pour arrêter)")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
