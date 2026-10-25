"""Césures et recollage des paragraphes."""
import unittest

from tests.outils import petit_vocabulaire
import pdf_markdown as P


class Cesures(unittest.TestCase):
    def test_recoller(self):
        v = P.Vocabulaire(["les élections marquées par la grève\n", "Jospin-Gayssot\n"])
        self.assertEqual(v.recoller("mar-", "quées par"), "")
        self.assertEqual(v.recoller("Jospin-", "Gayssot"), "-")
        self.assertEqual(v.recoller("anti-", "impérialiste"), "-")


class Paragraphes(unittest.TestCase):
    def test_paragraphe_coupe_recousu(self):
        self.assertEqual(P.fusionner_paragraphes("le gouvernement a décidé de\n\npoursuivre son offensive."),
                         "le gouvernement a décidé de poursuivre son offensive.")

    def test_phrases_finies_et_separateurs(self):
        self.assertEqual(P.fusionner_paragraphes("Fin de phrase.\n\nNouvelle phrase."), "Fin de phrase.\n\nNouvelle phrase.")
        self.assertEqual(P.fusionner_paragraphes("Avant\n\n-----\n\nAprès"), "Avant\n\n-----\n\nAprès")

    def test_vocabulaire_debuts_de_phrase(self):
        v = petit_vocabulaire()
        self.assertGreater(v.debuts["Les"], v.debuts["Près"])
        self.assertGreater(v.debuts2[("Après", "la")], 0)


if __name__ == "__main__":
    unittest.main()
