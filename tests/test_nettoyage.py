"""Nettoyage du Markdown : cas réels relevés dans le corpus (bruit éditorial, intertitres)."""
import unittest

from tests.outils import petit_vocabulaire  # noqa: F401  (ajoute scripts/ au chemin)
import nettoyage as N


def net(md, **kw):
    return N.nettoyer(md, None, **kw)


class Bruit(unittest.TestCase):
    def test_mentions_legales(self):
        self.assertEqual(net("Directeur de la Publication : Stéphane JUST Commission Paritaire n° 67187 "
                             "n° L.S.S.N. : 0763790 X Imprimerie Spéciale"), "")
        self.assertEqual(net("***Prenez contact !*** *e-mail : socialisme@free.fr Site web : http://socialisme.free.fr* "
                             "Directeur de la publication : Yves Ankaoua – Commission paritaire n°67187 – N° ISSN : "
                             "0763790 X – Imprimerie spéciale"), "")

    def test_mentions_collees_au_texte(self):
        self.assertEqual(net("Directeur de la publication: Olivier LESTANG Commission paritaire n°67187 - n°ISSN: "
                             "0763790X - Imprimerie spéciale Editorial inconditionnellement contre la guerre."),
                         "Editorial inconditionnellement contre la guerre.\n")

    def test_pied_de_page_et_navigation(self):
        self.assertEqual(net("### [ http://socialisme.free.fr - © A.E.P.S., 1 Bis Rue GUTENBERG, 93100 MONTREUIL ]"), "")
        self.assertEqual(net("[Prenez contact !](mailto:socialisme@free.fr)"), "")
        self.assertEqual(net("[Retour à la section: partis](http://socialisme.free.fr/franceorganisations.htm)"), "")
        self.assertEqual(net("Texte final.\n\nHaut"), "Texte final.\n")

    def test_bulletin_d_abonnement(self):
        md = ("Texte.\n\n### BULLETIN D'ABONNEMENT A \"COMBATTRE POUR LE SOCIALISME\" {10 NUMEROS: 100 FRANCS)\n\n"
              "NOM :......PRÉNOM :.......\n\n### CODE POSTAL : -\n\n### LOCALITÉ :\n\n"
              "(Écrire en caractère d'imprimerie. Merci) Chèque à établir à l'ordre de : Stéphane JUST "
              "Envoyer à : Stéphane JUST - B.P. 154 - 92804 PUTEAUX CEDEX\n\nAbonnement de soutien : 200 F\n\n"
              "Suite du texte normal qui reprend ici.")
        self.assertEqual(net(md), "Texte.\n\nSuite du texte normal qui reprend ici.\n")

    def test_champs_du_bulletin_defigures_par_l_ocr(self):
        md = ("Pour cela, que les dirigeants de l'UNEF organisent une conférence nationale des étudiants.\n\n"
              "NOM: persesensseN rer enn tent eune an renane SPA UT On San PRENOM:....…....…... suénesnauessen tes "
              "eUAN TS CSPem area Ven NEC Ne ADI 2ESSE: (OPUS Eten Des ED N MO DGSE DOFUS AC ND VASE S NAT")
        self.assertEqual(net(md), "Pour cela, que les dirigeants de l'UNEF organisent une conférence nationale "
                                  "des étudiants.\n")
        texte = "Il donna ses nom et prénom au policier, puis se tut."
        self.assertEqual(net(texte), texte + "\n")

    def test_en_tete_de_page(self):
        self.assertEqual(net("Supplément à C.P.S. nouvelle série n°73 (155) – 7 juillet 2019 – page 15"), "")
        self.assertEqual(net("une 3 CPS N°21 - 20 mars 1988 réalité : le capitalisme"), "une réalité : le capitalisme\n")
        self.assertEqual(net("les guerres n'ouvrent de débouchés\n\n### Supplément Enseignement public à CPS n° 98 "
                             "(5 octobre 2026)\n\nqu'aux marchands d'armes."),
                         "les guerres n'ouvrent de débouchés qu'aux marchands d'armes.\n")

    def test_citation_de_cps_conservee(self):
        t = "décembre 1997, CPS n°70, éditorial (p.6): \"L'expression\""
        self.assertEqual(net(t), t + "\n")

    def test_suite_page(self):
        self.assertEqual(net("le cours de la lutte (suite page 12)"), "le cours de la lutte\n")

    def test_sommaires(self):
        self.assertEqual(net("### SOMMAIRE"), "")
        self.assertEqual(net("La Russie à la dérive... Lnrensss cesse esse 35 Le clivage à l'ouest... sesesesseeesnsens 28"), "")
        self.assertEqual(net("TRACT ENSEIGNEMENT PUBLIC.....ersirssrieesseeen sonne eneeeeenecesnenanneneeenee 13"), "")

    def test_ps_mal_lu_n_est_pas_un_sommaire(self):
        # « P.S. » lu « P.5 » / « P.6 » par l'OCR : un paragraphe de texte, pas des renvois de page
        t = ("AU moment actuel un tel gouvernement serait forcément un gouvernement du P.5, et du P.C.F.. Qu'il y "
             "ait une majorité de députés du P.5, et du P.C.F, facilite ce combat. Aller exiger des députés du P.6. "
             "et du P.C.F. qu'ils décident que les revendications mises en avant soient satisfaites, s'intègre à "
             "l'action politique pour que la majorité P.6.-P.C.F. à l'Assemblée Nationale décide que celle-ci est "
             "souveraine. Aller exiger des députés du P.6, et du P.C.F, qu'ils décident.")
        self.assertIn("un tel gouvernement serait", net(t))

    def test_bandeau_de_une(self):
        doc = ("## SUPPLÉMENT À C.P.S. N° 52\n\non ne peut aller. de l'avant si l’on craint d'aller au sralismes "
               "(Lénine)\n\n- COMITE POUR\n\n### LA CONSTRUCTION DU PARTI OUVRIER REVOLUTIONNAIRE £ LA CONSTRUCTION "
               "DE L'INTERNATIONALE OUVRIERE REVOLUTIONNAIRE\n\n### DÉCLARATION DU COMITÉ POUR LA CONSTRUCTION DU "
               "PARTI RÉVOLUTIONNAIRE\n\n### VOTER POUR LA RUPTURE AVEC LA BOURGEOISIE")
        self.assertEqual(net(doc, debut_document=True),
                         "### DÉCLARATION DU COMITÉ POUR LA CONSTRUCTION DU PARTI RÉVOLUTIONNAIRE\n\n"
                         "### VOTER POUR LA RUPTURE AVEC LA BOURGEOISIE\n")
        self.assertEqual(net("### IE POUR LA CONSTRUCTION\n\n### DU PART\n\n### UN PREMIER BILAN\n\nTexte.",
                             debut_document=True), "### UN PREMIER BILAN\n\nTexte.\n")

    def test_debris_et_separateurs(self):
        self.assertEqual(net("Texte un.\n\nhe\n\nTexte deux."), "Texte un.\n\nTexte deux.\n")
        self.assertEqual(net("Pour la jeunesse : la lutte.\n\n(…)\n\nSuite."), "Pour la jeunesse : la lutte.\n\n(…)\n\nSuite.\n")
        self.assertIn("-----", net("Avant.\n\n-----\n\nAprès."))

    def test_revisions_word_et_traits_conditionnels(self):
        self.assertEqual(net("en cette rentrée 2015. ~~C~~’~~est en particulier l~~Le second degré", recoudre=False),
                         "en cette rentrée 2015. Le second degré\n")
        self.assertEqual(net("Les rou­lements des or­ganisations."), "Les roulements des organisations.\n")


class Confusions(unittest.TestCase):
    def test_confusions_ocr(self):
        c = N.corriger_confusions_ocr
        self.assertEqual(c("préparé par Île gouvernement et Îles dirigeants"), "préparé par le gouvernement et les dirigeants")
        self.assertEqual(c("la petite Île de Guam"), "la petite Île de Guam")
        self.assertEqual(c("Le 11 juin. 11 faut dire. 11s ont voté. « 11 n'y a pas"),
                         "Le 11 juin. Il faut dire. Ils ont voté. « Il n'y a pas")
        self.assertEqual(c("Elle est sortie. 11 heures plus tard"), "Elle est sortie. 11 heures plus tard")
        self.assertEqual(c("dans Ja politique de ia bourgeoisie"), "dans la politique de la bourgeoisie")


class Intertitres(unittest.TestCase):
    def test_lettrines(self):
        self.assertEqual(net("***G****uerre inter-impérialistes en Ukraine*"), "*Guerre inter-impérialistes en Ukraine*\n")
        self.assertEqual(net("**J**e m’exprime au nom des militants"), "Je m’exprime au nom des militants\n")

    def test_lettrines_perdues(self):
        v = petit_vocabulaire()
        def l(t):
            return N.nettoyer("### TITRE\n\n" + t, v).split("\n\n")[1].strip()
        self.assertEqual(l("e gouvernement le plus réactionnaire"), "Le gouvernement le plus réactionnaire")
        self.assertEqual(l("es projets de loi sont dans la continuité"), "Les projets de loi sont dans la continuité")
        self.assertEqual(l("endant ce temps du 9 au 30 octobre"), "Pendant ce temps du 9 au 30 octobre")
        self.assertEqual(l("ace à l'offensive économique"), "Face à l'offensive économique")
        self.assertEqual(l("et que la direction confédérale"), "et que la direction confédérale")
        self.assertEqual(l("e Une intervention militaire"), "e Une intervention militaire")  # puce « e », pas une lettrine

    def test_titres_vides_dates_sources(self):
        self.assertEqual(net("## •\n\nTexte"), "Texte\n")
        self.assertEqual(net("### Le 6 septembre 2013"), "Le 6 septembre 2013\n")
        self.assertEqual(net("### article paru dans Cps n°31 de janvier 2008"), "Article paru dans Cps n°31 de janvier 2008\n")

    def test_titres_recolles(self):
        self.assertEqual(net("## Pour mettre le gouvernement Chirac-Raffarin\n\n## hors d'état de nuire\n\nTexte."),
                         "## Pour mettre le gouvernement Chirac-Raffarin hors d'état de nuire\n\nTexte.\n")
        # surtitre terminé par une virgule + titre : deux intertitres
        md = "### Appuyé sur la défaite,\n\n### Le gouvernement Macron-Philippe\n\nTexte."
        self.assertEqual(net(md), md + "\n")

    def test_puces_en_liste(self):
        self.assertEqual(net("## · Assez de journées d'action !\n\n## · Appelez à la grève !\n\nTexte."),
                         "- Assez de journées d'action !\n\n- Appelez à la grève !\n\nTexte.\n")

    def test_hierarchie_dans_un_article(self):
        art = ("## Titre de l'article\n\n### Un chapeau très long qui fait bien plus de trente mots pour être sûr "
               "qu'il sera rendu au texte courant parce que ce n'est pas un intertitre du tout mais bien un paragraphe "
               "de présentation de l'article qui suit.\n\nTexte.\n\n## Intertitre en h2\n\nTexte.\n\n### Sous-intertitre\n\nTexte.")
        r = N.nettoyer(art, None, article=True, titre="Titre de l'article")
        self.assertTrue(r.startswith("## Titre de l'article\n\nUn chapeau très long"))
        self.assertIn("### Intertitre en h2", r)
        self.assertIn("#### Sous-intertitre", r)

    def test_sommaire_html_retire(self):
        md = ("## Titre\n\n- Après le décès de Stéphane Just, une crise\n\n- Les tâches politiques du Comité\n\n"
              "Introduction assez longue pour être un vrai paragraphe de texte.\n\n"
              "### Après le décès de Stéphane Just, une crise\n\nTexte.\n\n### Les tâches politiques du Comité\n\nTexte.")
        r = N.nettoyer(md, None, article=True, titre="Titre", recoudre=False)
        self.assertNotIn("- Après", r)
        self.assertIn("### Les tâches politiques du Comité", r)

    def test_emphases_conservees(self):
        t = "Il est **important** de *voir* cela, voir le site http://socialisme.free.fr pour la suite."
        self.assertEqual(net(t), t + "\n")
        self.assertEqual(net("avec le titre *: « L’UGT et les CCOO apprécient »*. Puis", recoudre=False),
                         "avec le titre *: « L’UGT et les CCOO apprécient »*. Puis\n")


if __name__ == "__main__":
    unittest.main()
