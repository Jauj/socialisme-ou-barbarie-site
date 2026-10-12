"""Fonctions de construction de la base : articles ajoutés d'après le sommaire imprimé, dates."""
import unittest

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


class Dates(unittest.TestCase):
    def test_ecart_signe(self):
        self.assertEqual(build_db.ecart_signe("2008-04-07", "2008-04-17"), -10)
        self.assertEqual(build_db.ecart_signe("1985-09-10", "1985-09-00"), 9)


if __name__ == "__main__":
    unittest.main()
