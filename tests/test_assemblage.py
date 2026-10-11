"""Découpage des articles : sommaires imprimés, recherche des titres, retouches des débuts."""
import unittest

from tests import outils  # noqa: F401  (ajoute scripts/ au chemin)
import assemblage as A


class SommaireImprime(unittest.TestCase):
    def test_lignes_a_points_de_conduite(self):
        page = ("Sommaire :\n ÉDITORIAL ........................................... P.1\n"
                " NOTES SUR LA SITUATION INTERNATIONALE ..................... P.11\n"
                "* ENSEIGNEMENT PUBLIC... . snsesesssnsnee …P.18\n"
                "* LA POLITIQUE DE NOTRE CERCLE: COMBATTRE POUR LE SOCIALISME issues P.13\n")
        self.assertEqual(A.sommaire_imprime([page, ""]),
                         [("ÉDITORIAL", 1), ("NOTES SUR LA SITUATION INTERNATIONALE", 11),
                          ("ENSEIGNEMENT PUBLIC", 18), ("LA POLITIQUE DE NOTRE CERCLE: COMBATTRE POUR LE SOCIALISME", 13)])

    def test_renvoi_illisible_ignore(self):
        page = ("* EDITORIAL ........ P.1\n* AUTRE ARTICLE ........ P.4\n"
                "* UNE ANNEE DECISIVE POUR L'ENSEIGNEMENT PUBLIC.................... 1.42\n")
        entrees = A.sommaire_imprime([page])
        self.assertIn(("UNE ANNEE DECISIVE POUR L'ENSEIGNEMENT PUBLIC", 42), entrees)
        self.assertEqual(A.indices_sommaire(entrees, ["Une année décisive pour l'enseignement public"], 36), {})

    def test_appariement_aux_titres_du_site(self):
        entrees = [("ÉDITORIAL", 1), ("IRAN", 25), ("LES MILITANTS INTERVIENNENT ET INFORMENT CPS", 23)]
        titres = ["Editorial : pour arracher les revendications", "Les militants interviennent et informent CPS (RATP)",
                  "Iran : soulèvement héroïque des masses", "Pour arrêter le bras des bourreaux d'Iran"]
        self.assertEqual(A.indices_sommaire(entrees, titres, 36), {0: 1, 1: 23, 2: 25})


def pages_md(*pages):
    return A.blocs_document(list(pages))


class Localisation(unittest.TestCase):
    def test_titre_parmi_les_intertitres_et_surtitre(self):
        blocs = pages_md(
            "## Éditorial\n\n" + "Texte de l'éditorial. " * 20,
            "### Brésil :\n\n### Le gouvernement Bolsonaro face aux masses\n\n" + "Texte sur le Brésil. " * 20)
        titres = ["Éditorial", "Brésil : le gouvernement Bolsonaro face aux masses"]
        debuts, sources = A.localiser_blocs(titres, blocs)
        debuts = A.ajuster_debuts(debuts, blocs, sources)
        self.assertEqual(blocs[debuts[1]][2], "### Brésil :")  # surtitre inclus
        self.assertEqual(blocs[debuts[0]][0], 1)

    def test_rubrique_recurrente(self):
        blocs = pages_md("## Éditorial\n\n" + "Texte. " * 50,
                         "### LES MILITANTS INTERVIENNENT ET INFORMENT C.P.S.\n\n" + "Motion de la section. " * 20)
        titres = ["Éditorial", "Les militants interviennent : SNES ; PTT"]
        debuts, _ = A.localiser_blocs(titres, blocs, rubriques=frozenset({A.rubrique(titres[1])}))
        self.assertEqual(blocs[debuts[1]][0], 2)
        debuts, _ = A.localiser_blocs(titres, blocs)  # rubrique non récurrente : pas d'appariement
        self.assertIsNone(debuts[1])

    def test_sommaire_de_derniere_page_ecarte(self):
        texte = "Texte de l'article qui suit son titre et occupe la page entière. " * 5
        blocs = pages_md(
            "### PREMIER ARTICLE IMPORTANT\n\n" + texte,
            "### SECOND ARTICLE IMPORTANT\n\n" + texte,
            "### PREMIER ARTICLE IMPORTANT\n\n### SECOND ARTICLE IMPORTANT\n\n" + texte)
        debuts, _ = A.localiser_blocs(["Premier article important", "Second article important"], blocs)
        self.assertEqual([blocs[d][0] for d in debuts], [1, 2])

    def test_page_du_sommaire_imprime_a_une_page_pres(self):
        texte = "Texte de l'article. " * 20
        blocs = pages_md("## Éditorial\n\n" + texte, texte, "### Iran : la république islamique en crise\n\n" + texte,
                         texte)
        debuts, sources = A.localiser_blocs(["Éditorial", "Iran : la république islamique en crise"], blocs,
                                            pages_indiquees={1: 4})
        self.assertEqual((blocs[debuts[1]][0], sources[1]), (3, "sommaire"))

    def test_fin_d_article_precedent_en_haut_de_page(self):
        blocs = pages_md("## Titre A\n\n" + "Texte A. " * 30,
                         "suite de l'article A en minuscule.\n\nDébut de l'article B. " + "Texte B. " * 20)
        debuts = A.ajuster_debuts([0, 2], blocs, ["titre", "sommaire"])
        self.assertEqual(debuts[1], 3)


if __name__ == "__main__":
    unittest.main()
