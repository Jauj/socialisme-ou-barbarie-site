"""Métadonnées tirées des textes : date imprimée en une, date de rédaction, tags du texte."""
import unittest

from tests import outils  # noqa: F401  (ajoute scripts/ au chemin)
import metadonnees as M


class DateImprimee(unittest.TestCase):
    def test_manchette(self):
        une = "C.P.S. Nouvelle série N°80 (N°162) – 2 €\n\n29 SEPTEMBRE 2021\n\nLe gouvernement Macron-Castex…"
        self.assertEqual(M.date_imprimee(une, "2021-09-29"), ("2021-09-29", "29 SEPTEMBRE 2021"))

    def test_supplement_et_premier_du_mois(self):
        self.assertEqual(M.date_imprimee("Supplément à\nCPS n° 88\n(9 octobre 2023)\n", "2023-10-09")[0], "2023-10-09")
        self.assertEqual(M.date_imprimee("CPS n°65\n1er juin 2017\n", "2017-06-01")[0], "2017-06-01")

    def test_date_d_evenement_lointain_ignoree(self):
        une = "Titre\nDepuis le 13 mai 1954, la guerre\n"
        self.assertIsNone(M.date_imprimee(une, "1986-12-31"))

    def test_jour_illisible_mois_retenu(self):
        self.assertEqual(M.date_imprimee("° | : 34 MAI 1999\nOn ne peut", "1999-05-31", ocr=True)[0], "1999-05-00")

    def test_erreur_ocr_d_un_caractere_ignoree(self):
        self.assertIsNone(M.date_imprimee("CPS\n20 Mars 1988\n", "1988-03-26", ocr=True))
        self.assertEqual(M.date_imprimee("CPS\n20 Mars 1988\n", "1988-03-26")[0], "1988-03-20")

    def test_seules_les_premieres_lignes(self):
        une = "\n".join(["ligne"] * 12) + "\n7 SEPTEMBRE 1991\n"
        self.assertIsNone(M.date_imprimee(une, "1991-09-07"))

    def test_comparaison(self):
        self.assertEqual(M.comparer_dates("2001-01-12", "2001-01-12"), "identique")
        self.assertEqual(M.comparer_dates("2000-01-12", "2001-01-12"), "millésime différent en janvier (coquille probable)")
        self.assertEqual(M.comparer_dates("2006-06-03", "2006-06-01"), "jour différent")
        self.assertEqual(M.comparer_dates("1999-05-00", "1999-05-31"), "identique (mois)")


class DateRedaction(unittest.TestCase):
    def test_formes(self):
        self.assertEqual(M.date_redaction("Texte.\n\nLe 7 avril 2008\n"), ("2008-04-07", "Le 7 avril 2008"))
        self.assertEqual(M.date_redaction("Texte.\n\n*Le 30/03/87*\n")[0], "1987-03-30")
        self.assertEqual(M.date_redaction("Texte.\n\nParis, le 1er mai 1990.\n")[0], "1990-05-01")
        self.assertEqual(M.date_redaction("Texte.\n\nLe 2/3/1990\n")[0], "1990-03-02")

    def test_suivie_d_une_note(self):
        md = "Texte.\n\nLe 30 septembre 2000\n\n*Dans la seconde partie, CPS reviendra sur la Russie.*\n"
        self.assertEqual(M.date_redaction(md)[0], "2000-09-30")

    def test_date_dans_une_phrase_ou_invalide(self):
        self.assertIsNone(M.date_redaction("Le 7 avril 2008, la grève a commencé dans toutes les écoles du pays.\n"))
        self.assertIsNone(M.date_redaction("Texte.\n\nLe 15.64.87\n"))
        self.assertIsNone(M.date_redaction("Le 7 avril 2008\n\n" + "Paragraphe.\n\n" * 5))


class TagsDuTexte(unittest.TestCase):
    regles = M.compiler_regles_texte({"min": 3, "densite": 2.0, "regles": [
        {"tag": "italie", "motif": r"\bItali"},
        {"tag": "lo", "motif": r"Lutte [Oo]uvri[èe]re|\bLO\b", "casse": True}]})

    def test_seuils(self):
        texte = "L'Italie. " * 3 + "mot " * 2000
        self.assertEqual(M.tags_du_texte(texte, self.regles), [])          # 3 pour ~2 000 mots : < 2 ‰
        texte = "L'Italie et les Italiens. " * 3 + "mot " * 500
        self.assertEqual(M.tags_du_texte(texte, self.regles), [("italie", 6)])

    def test_mot_entier_et_casse(self):
        texte = "Le capitalisme. " * 20 + "lo lo lo"
        self.assertEqual(M.tags_du_texte(texte, self.regles), [])


if __name__ == "__main__":
    unittest.main()
