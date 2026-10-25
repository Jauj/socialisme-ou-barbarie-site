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

    def test_points_de_conduite_lus_comme_des_mots(self):
        page = ("Sommaire:\n* EDITORIAL. Lee ae a as aa a a een ee ee es ae ea eee .P.1\n"
                "* ENSEIGNEMENT PUBLIC: POUR LE BOYCOTT. Lasers era see des sa a ea eee .P. 10\n"
                "* ON NOUS COMMUNIQUE (ENSEIGNEMENT PUBLIC)... csrera car ana man er cas P.14\n")
        self.assertEqual(A.sommaire_imprime([page]),
                         [("EDITORIAL", 1), ("ENSEIGNEMENT PUBLIC: POUR LE BOYCOTT", 10),
                          ("ON NOUS COMMUNIQUE (ENSEIGNEMENT PUBLIC)", 14)])

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

    def test_titre_court_reste_paragraphe_page_voisine(self):
        texte = "Texte de l'article. " * 20
        blocs = pages_md("## Premier\n\n" + texte, "On nous communique\n\n" + texte, "## La grève de 1968\n\n" + texte)
        debuts, _ = A.localiser_blocs(["Premier", "On nous communique", "La grève de 1968"], blocs, {1: 3, 2: 4})
        self.assertEqual([blocs[d][0] for d in debuts], [1, 2, 3])

    def test_fin_d_article_precedent_en_haut_de_page(self):
        blocs = pages_md("## Titre A\n\n" + "Texte A. " * 30,
                         "suite de l'article A en minuscule.\n\nDébut de l'article B. " + "Texte B. " * 20)
        debuts = A.ajuster_debuts([0, 2], blocs, ["titre", "sommaire"])
        self.assertEqual(debuts[1], 3)

    def test_surtitre_de_rubrique_au_dessus_du_chapo(self):
        blocs = pages_md("## Titre A\n\n" + "Texte A. " * 30,
                         "Fin de l'article précédent.\n\n### Algérie\n\n*Après l'« élection » du 12 décembre, chapô.*\n\n"
                         "*Qui est Tebboune ? Second paragraphe du chapô.*\n\n### Un an après le déclenchement du Hirak\n\n"
                         + "Texte B. " * 20)
        titres = ["Titre A", "Algérie : Un an après le déclenchement du « Hirak »"]
        debuts = A.ajuster_debuts([0, 6], blocs, ["titre", "sommaire"], titres=titres)
        self.assertEqual(blocs[debuts[1]][2], "### Algérie")
        # sans rubrique commune, le chapô reste à sa place
        debuts = A.ajuster_debuts([0, 6], blocs, ["titre", "sommaire"], titres=["Titre A", "Un an après le Hirak"])
        self.assertEqual(debuts[1], 6)

    def test_bandeau_du_supplement_rattache_au_texte_qui_suit(self):
        blocs = pages_md("## Titre A\n\n" + "Texte A. " * 30,
                         "### GROUPE POUR LA CONSTRUCTION DU PARTI OUVRIER RÉVOLUTIONNAIRE, LA CONSTRUCTION DE "
                         "L'INTERNATIONALE OUVRIÈRE RÉVOLUTIONNAIRE\n\n(31 octobre 2022\n\nCommuniqué : Iran. " + "Texte B. " * 20)
        debuts = A.ajuster_debuts([0, 3], blocs, ["titre", "sommaire"])
        self.assertEqual(debuts[1], 2)


class DebutParLeTexte(unittest.TestCase):
    pages = [
        "## Premier article\n\nTexte du premier article sur la grève des cheminots et la direction de la CGT.",
        "C.P,S, nouvelle série n°34 (113) - 12 janvier 2008 - page 21\n\n"
        "### MOYEN-ORIENT\n\n"
        "Une questlon taraude la bourgeoisle américaine, au point d’occuper une bonne place dans la "
        "précampagne pour la Maison Blanche : comment gérer l'encombrant héritage de la guerre en Irak "
        "et sortir du bourbier sans perdre la face devant ses alliés et ses rivaux de la région.",
    ]
    texte = ("*Article paru dans CPS nouvelle série n°31*\n\n## Moyen-Orient\n\n"
             "Une question taraude la bourgeoisie américaine, au point d’occuper une bonne place dans la "
             "précampagne pour la Maison Blanche : comment gérer l'encombrant héritage de la guerre en Irak "
             "et sortir du bourbier sans perdre la face devant ses alliés et ses rivaux de la région.")

    def test_debut_retrouve_malgre_l_ocr_avec_son_titre(self):
        blocs = A.blocs_document(self.pages)
        k, score = A.debut_par_le_texte(self.texte, blocs)
        self.assertEqual(blocs[k][2], "### MOYEN-ORIENT")
        self.assertGreater(score, 0.5)   # en-tête courant sauté, intertitre inclus

    def test_texte_absent(self):
        blocs = A.blocs_document(self.pages[:1])
        self.assertIsNone(A.debut_par_le_texte(self.texte, blocs))

    def test_fin_de_l_article_precedent_collee_au_debut(self):
        md = ("Les militants continueront à avancer cette exigence. Nous reproduisons ci-dessous un article "
              "publié dans le numéro 31 de notre bulletin :\n\n### LA LAÏCITÉ\n\nTexte.")
        note = "*Article paru dans CPS n°56*\n\nNous reproduisons ci-dessous un article publié dans le numéro 31 :"
        self.assertTrue(A.depuis_le_debut_du_texte(md, note).startswith("Nous reproduisons ci-dessous"))
        self.assertEqual(A.depuis_le_debut_du_texte("## Titre\n\n" + md, note), "## Titre\n\n" + md)

    def test_titre_en_gras_et_bandeau_du_supplement_inclus(self):
        corps = ("Le gouvernement prépare une nouvelle offensive contre les étudiants et les lycéens : "
                 "sélection à l'entrée de l'université, hausse des frais d'inscription, liquidation des "
                 "diplômes nationaux au profit de certificats locaux sans valeur sur le marché du travail.")
        page = ("La grève des cheminots a montré la voie, encore fallait-il que les dirigeants la suivent.\n\n"
                "*GROUPE pour la construction du Parti ouvrier révolutionnaire et de l'Internationale ouvrière "
                "révolutionnaire* Supplément Jeunes à CPS n°74 – 15 novembre 2019\n\n"
                "**Le gouvernement Macron est en guerre contre la jeunesse**\n\n"
                "## Une seule voie : s'organiser\n\n" + corps)
        blocs = A.blocs_document([page])
        k, _ = A.debut_par_le_texte("## Le gouvernement Macron est en guerre contre la jeunesse\n\n" + corps, blocs)
        self.assertTrue(blocs[k][2].startswith("*GROUPE"), blocs[k][2])


if __name__ == "__main__":
    unittest.main()
