"""Pages images des PDF à couche texte : lesquelles sont océrisées, lesquelles gardées."""
import unittest
from unittest import mock

from tests import outils  # noqa: F401  (ajoute scripts/ au chemin)
import extraire_pages as E


class SurPlace:
    """Remplace le ProcessPoolExecutor : exécution dans le processus courant."""
    @staticmethod
    def map(f, xs):
        return [f(x) for x in xs]


class PagesImages(unittest.TestCase):
    connus = {"gouvernement", "les", "travailleurs", "retraite"}
    ocr = {2: "Le gouvernement et les travailleurs : retraite. " * 20,   # texte reproduit en image
           3: "Le gouvernement Wxqz Kjhq Zrpt. " * 20,                    # photo : mots inconnus
           4: "Les travailleurs.",                                        # légende : trop court
           5: "Le gouvernement et les travailleurs. " * 20,               # page à couche texte
           6: "Tract des travailleurs. " + "Le gouvernement et les travailleurs. " * 20,
           7: "Les travailleurs et le gouvernement. " * 12}

    def oceriser(self, pages, images, couvertes=()):
        with mock.patch.object(E, "grande_image", lambda pdf, k: k in images), \
                mock.patch.object(E, "part_image", lambda pdf, k: 0.9 if k in couvertes else 0.1), \
                mock.patch.object(E, "ocr_page", lambda args: self.ocr[args[1]]):
            return E.ocr_pages_images("n.pdf", pages, SurPlace(), None, self.connus)

    def test_seules_les_pages_images_lisibles_sont_gardees(self):
        pages = ["Texte natif. " * 30, "", "page 3", "  ", "Texte natif. " * 30]
        self.assertEqual(self.oceriser(pages, {2, 3, 4, 5}), [2])
        self.assertTrue(pages[1].startswith("Le gouvernement"))
        self.assertEqual(pages[2:], ["page 3", "  ", "Texte natif. " * 30])

    def test_ligne_de_texte_au_dessus_d_une_image(self):
        # en-tête dans la couche texte, le tract en image dessous ; une page de texte ordinaire
        # avec une grande photo garde sa couche texte (l'OCR n'y apporte pas assez)
        pages = ["Texte natif. " * 30] * 5 + ["Tract des travailleurs.", "Les travailleurs, le gouvernement. " * 15]
        self.assertEqual(self.oceriser(pages, set(), couvertes={6, 7}), [6])
        self.assertTrue(pages[5].startswith("Tract des travailleurs. Le gouvernement"))

    def test_page_vide_sans_image(self):
        pages = ["Texte natif. " * 30, ""]
        self.assertEqual(self.oceriser(pages, set()), [])


if __name__ == "__main__":
    unittest.main()
