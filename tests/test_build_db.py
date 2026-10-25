"""Fonctions de construction de la base : articles ajoutés d'après le sommaire imprimé, dates."""
import tempfile
import unittest
from pathlib import Path

from tests import outils  # noqa: F401  (ajoute scripts/ au chemin)
import build_db


def article(titre, page=None, origine="sommaire", page_sommaire=None):
    return {"titre": titre, "origine": origine, "pdf_page": page, "url_pdf": "n.pdf" if page else None,
            "page_sommaire": page_sommaire}


class RangerArticlesPdf(unittest.TestCase):
    def test_insertion_avant_le_premier_article_qui_commence_plus_loin(self):
        propres = [article("A", 1), article("B", 10), article("C"),
                   article("P", origine="pdf", page_sommaire=5), article("Q", origine="pdf", page_sommaire=30)]
        res = build_db.ranger_articles_pdf(propres, [], "n.pdf", 36)
        self.assertEqual([a["titre"] for a in res], ["A", "P", "B", "C", "Q"])

    def test_page_du_sommaire_imprime(self):
        propres = [article("Éditorial"), article("Grève à la RATP"), article("P", origine="pdf", page_sommaire=8)]
        sommaire = [("EDITORIAL", 1), ("GREVE A LA RATP", 12)]
        res = build_db.ranger_articles_pdf(propres, sommaire, "n.pdf", 36)
        self.assertEqual([a["titre"] for a in res], ["Éditorial", "P", "Grève à la RATP"])


class DecouperIndex(unittest.TestCase):
    def test_morceaux_entiers_et_anciens_retires(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "r.sqlite").write_bytes(bytes(range(256)) * 10)          # 2 560 octets
            (tmp / "m").mkdir()
            (tmp / "m" / "r.sqlite.009").write_bytes(b"ancien")
            infos = build_db.decouper_index(tmp / "r.sqlite", tmp / "m", taille=1024)
            self.assertEqual(infos, {"prefixe": "r.sqlite.", "chiffres": 3, "morceau": 1024, "taille": 2560,
                                     "morceaux": 3})
            noms = sorted(f.name for f in (tmp / "m").iterdir())
            self.assertEqual(noms, ["r.sqlite.000", "r.sqlite.001", "r.sqlite.002"])
            self.assertEqual(b"".join((tmp / "m" / n).read_bytes() for n in noms), (tmp / "r.sqlite").read_bytes())


class Dates(unittest.TestCase):
    def test_ecart_signe(self):
        self.assertEqual(build_db.ecart_signe("2008-04-07", "2008-04-17"), -10)
        self.assertEqual(build_db.ecart_signe("1985-09-10", "1985-09-00"), 9)


if __name__ == "__main__":
    unittest.main()
