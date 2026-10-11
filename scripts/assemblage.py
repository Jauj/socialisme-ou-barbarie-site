"""Découpage des articles dans le Markdown des pages d'une publication.

Chaque page Markdown est une suite de blocs (paragraphes, intertitres « ## » /
« ### », éléments de liste). Pour chaque article du sommaire, on cherche son
titre parmi les intertitres (seuls ou groupés par deux ou trois : surtitre, titre,
sous-titre), en respectant l'ordre du sommaire et en se méfiant des pages qui
citent plusieurs titres (une, sommaire). Les pages indiquées par le site, puis celles
du sommaire imprimé en une, guident la recherche. Le texte d'un article va de son
titre (surtitre compris) jusqu'au titre de l'article suivant localisé dans le même PDF.
"""
import re

from localiser import jetons, jetons_titre
from pdf_markdown import fusionner_paragraphes

RUBRIQUE = re.compile(r"^\W*([ÉE]ditorial|EDITORIAL|Notes? [ée]ditoriales?)\s*[:\-–—]\s*", re.I)


def blocs_document(pages):
    """[(page, rang, texte)] pour toutes les pages (page à partir de 1)."""
    blocs = []
    for p, page in enumerate(pages, 1):
        for b in page.split("\n\n"):
            if b.strip():
                blocs.append((p, len(blocs), b.strip()))
    return blocs


def _est_titre(b):
    return b.startswith("#")


def _score(tt, texte):
    if not tt:
        return 0.0
    tj = set(j for j in jetons(texte) if len(j) > 1)
    return len(set(tt) & tj) / len(set(tt))


def rubrique(titre):
    """Partie d'un titre avant « : » ou « ( » (« Les militants interviennent : RATP… »)."""
    return tuple(jetons(re.split(r"\s*[:(\[]", titre, maxsplit=1)[0]))


def _candidats(titre, blocs, rubriques=frozenset()):
    """Positions (rang de bloc) dont le groupe d'intertitres correspond au titre, avec score.
    rubriques : débuts de titres récurrents (« les militants interviennent ») ; pour ces titres,
    l'intertitre imprimé peut n'être que la rubrique."""
    variantes = [titre]
    sans_rubrique = RUBRIQUE.sub("", titre)
    if sans_rubrique != titre and len(jetons_titre(sans_rubrique)) >= 3:
        variantes.append(sans_rubrique)
    norm_titre = " ".join(jetons(titre))
    # « Les militants interviennent : RATP ; Université… » : l'intertitre imprimé est la rubrique
    j_rub = list(rubrique(titre)) if rubrique(titre) in rubriques else []
    res = {}
    for k, (p, rang, texte) in enumerate(blocs):
        if _ressemble_sommaire(texte):
            continue
        if not _est_titre(texte):
            # titre fondu au début d'un paragraphe (intertitre non reconnu par l'OCR)
            debut = jetons(texte)
            meilleur = 0.0
            for v in variantes:
                tt = jetons_titre(v, n=10)
                if len(tt) >= 4:
                    # « Intervention d'un délégué de la métallurgie au congrès confédéral de la CGT
                    # Force ouvrière » pour « Intervention au congrès confédéral de la CGT-FO » :
                    # fenêtre plus large quand le paragraphe commence par le premier mot du titre
                    n = len(jetons(v)) + 4
                    if debut[:1] == tt[:1]:
                        n = max(n, 20)
                    tete = set(debut[:n])
                    meilleur = max(meilleur, len(set(tt) & tete) / len(set(tt)))
            if meilleur >= 0.85:
                res[k] = meilleur - 0.05  # un peu moins sûr qu'un intertitre
            continue
        groupe = [texte]
        for j in range(k + 1, min(k + 3, len(blocs))):
            if _est_titre(blocs[j][2]) and blocs[j][0] == p:
                groupe.append(blocs[j][2])
            else:
                break
        meilleur = 0.0
        for v in variantes:
            tt = jetons_titre(v, n=10)
            if len(tt) < 3:
                continue
            for n in range(1, len(groupe) + 1):
                texte_groupe = " ".join(groupe[:n])
                # un intertitre bien plus long que le titre cherché est une accroche ou un sommaire
                if len(jetons(texte_groupe)) > max(3 * len(jetons(v)), len(jetons(v)) + 15):
                    break
                meilleur = max(meilleur, _score(tt, texte_groupe))
        # titres courts (« Éditorial », « Brésil ») : égalité exacte avec l'intertitre
        j_texte = jetons(texte.lstrip("# "))
        n_titre = len(norm_titre.split())
        if " ".join(j_texte) == norm_titre and norm_titre:
            meilleur = max(meilleur, 1.0)
        elif n_titre >= 3 and " ".join(j_texte[-n_titre:]) == norm_titre and len(j_texte) <= n_titre + 8:
            meilleur = max(meilleur, 0.8)  # « … (POUR LA RECONSTRUCTION DE LA UN PREMIER BILAN »
        elif j_rub and j_texte[:len(j_rub)] == j_rub and len(j_texte) <= len(j_rub) + 6:
            meilleur = max(meilleur, 0.8)
        if meilleur >= 0.75:
            res[k] = meilleur
    return res


def _ressemble_sommaire(texte):
    puces = len(re.findall(r"(\\\*|•|●)", texte))
    return puces >= 2 or bool(re.search(r"(\.\s?){3,}\s*\d|…\s*\d|\.{2,}\s*\d+\s*\.{2,}", texte))


def _meilleur_bloc(titre, blocs, page):
    """(rang, score) du bloc de la page dont le début ressemble le plus au titre."""
    tt = jetons_titre(RUBRIQUE.sub("", titre), n=8) or jetons_titre(titre, n=8)
    if len(tt) < 2:
        return None, 0.0
    meilleur, score = None, 0.0
    for k, (p, rang, texte) in enumerate(blocs):
        if p == page:
            s = len(set(tt) & set(jetons(texte)[:40])) / len(set(tt))
            if s > score:
                meilleur, score = k, s
    return meilleur, score


def meilleur_bloc_page(titre, blocs, page, seuil=0.5):
    """Sur une page donnée : le bloc dont le début ressemble le plus au titre (ou None)."""
    tt = jetons_titre(RUBRIQUE.sub("", titre), n=8) or jetons_titre(titre, n=8)
    if len(tt) < 2:
        return None  # « Éditorial » : le mot se retrouve dans le texte, pas un repère
    meilleur, score = None, 0.0
    for k, (p, rang, texte) in enumerate(blocs):
        if p != page:
            continue
        s = len(set(tt) & set(jetons(texte)[:40])) / len(set(tt))
        if s > score:
            meilleur, score = k, s
    return meilleur if score >= seuil else None


def localiser_blocs(titres, blocs, pages_imposees=None, seuil=0.75, pages_indiquees=None, rubriques=frozenset()):
    """Pour chaque titre : (rang du bloc de début ou None, source).

    pages_imposees  : {indice de titre: page} indiquées par le site ; on y cherche le titre
                      (page voisine comprise), à défaut on commence au premier bloc de la page ;
    pages_indiquees : {indice de titre: page} du sommaire imprimé ; même recherche, sans
                      repli sur le haut de page (voir placer_selon_sommaire).
    source : « site », « sommaire » ou « titre »."""
    pages_imposees = pages_imposees or {}
    pages_indiquees = {i: p for i, p in (pages_indiquees or {}).items() if i not in pages_imposees}
    cands = [_candidats(t, blocs, rubriques) for t in titres]
    # pages « denses » : plusieurs titres différents y sont reconnus (une, sommaire)
    par_page = {}
    for i, c in enumerate(cands):
        for k in c:
            par_page.setdefault(blocs[k][0], set()).add(i)
    denses = {p for p, s in par_page.items() if len(s) >= 2}

    def suivi_de_texte(k):
        """Un vrai début d'article est suivi d'un paragraphe de texte, pas d'autres titres."""
        for j in range(k + 1, min(k + 5, len(blocs))):
            if not _est_titre(blocs[j][2]) and not blocs[j][2].startswith("- ") and len(blocs[j][2]) >= 200:
                return True
        return False

    # sur ces pages, des titres groupés sans texte entre eux forment un sommaire (même sans
    # points de conduite ni numéros de page, comme en dernière page de l'ancienne série)
    positions = sorted({(k, i) for i, c in enumerate(cands) for k in c if blocs[k][0] in denses})
    groupes = set()
    for (k1, i1), (k2, i2) in zip(positions, positions[1:]):
        if i1 != i2 and k1 != k2 and blocs[k1][0] == blocs[k2][0] \
                and all(len(blocs[j][2]) < 200 for j in range(k1 + 1, k2)):
            groupes.update({k1, k2})
    for i, c in enumerate(cands):
        for k in list(c):
            if blocs[k][0] in denses and (k in groupes or not suivi_de_texte(k)):
                del c[k]  # entrée de sommaire ou titre de une

    res = [None] * len(titres)
    sources = [None] * len(titres)
    pris = set()
    haut = {}
    for k, b in enumerate(blocs):
        haut.setdefault(b[0], k)
    # 1. pages indiquées par le site, puis par le sommaire imprimé
    for i, page in list(pages_imposees.items()) + list(pages_indiquees.items()):
        sur_page = [k for k in cands[i] if blocs[k][0] == page and k not in pris]
        # le site et le sommaire se trompent parfois d'une page : on regarde aussi les voisines
        voisines = [k for k in cands[i] if abs(blocs[k][0] - page) == 1 and k not in pris]
        if sur_page:
            res[i] = max(sur_page, key=lambda k: cands[i][k])
        elif voisines:
            res[i] = max(voisines, key=lambda k: cands[i][k])
        elif i in pages_imposees:
            res[i] = meilleur_bloc_page(titres[i], blocs, page)
            if res[i] is None:
                res[i] = haut.get(page)
        if res[i] is not None:
            pris.add(res[i])
            sources[i] = "site" if i in pages_imposees else "sommaire"
    # 2. les autres, dans l'ordre du sommaire ; un article dont le sommaire imprimé donne la
    #    page sans qu'on y ait trouvé son titre borne quand même la recherche des suivants
    courant = -1
    for i in range(len(titres)):
        if res[i] is not None:
            courant = max(courant, res[i])
            continue
        if i in pages_indiquees and pages_indiquees[i] - 1 in haut:
            courant = max(courant, haut[pages_indiquees[i] - 1] - 1)
        c = {k: s for k, s in cands[i].items() if k not in pris}
        apres = sorted(k for k in c if k > courant)
        hors_denses = [k for k in apres if blocs[k][0] not in denses]
        choix = (hors_denses or apres or [None])[0]
        if choix is None:  # hors de l'ordre du sommaire : seulement une correspondance très sûre
            sures = sorted(k for k, s in c.items() if s >= 0.9 and blocs[k][0] not in denses)
            choix = sures[0] if sures else None
        if choix is not None:
            res[i] = choix
            sources[i] = "titre"
            pris.add(choix)
            courant = max(courant, choix)
    return res, sources


def placer_selon_sommaire(debuts, sources, blocs, pages_indiquees, titres, premier_en_une=True):
    """Derniers recours, après la recherche du titre : article du sommaire imprimé dont le
    titre reste introuvable → bloc de la page indiquée qui ressemble le plus au titre, à
    défaut haut de cette page, si aucun autre article n'y commence ; premier article du
    sommaire du site → haut de la première page, s'il y est libre (premier_en_une : numéros,
    dont le premier article est en une ; pas les suppléments, recueils de textes divers)."""
    haut = {}
    for k, b in enumerate(blocs):
        haut.setdefault(b[0], k)
    occupees = {blocs[k][0] for k in debuts if k is not None}
    for i, page in sorted(pages_indiquees.items()):
        if debuts[i] is not None:
            continue
        choix = None
        for p in (page, page + 1, page - 1):  # le sommaire imprimé se trompe parfois d'une page
            if p in haut and p not in occupees:
                k, s = _meilleur_bloc(titres[i], blocs, p)
                if k is not None and s >= 0.5 and (choix is None or s > choix[1]):
                    choix = (k, s)
        if choix is None and page in haut and page not in occupees:
            choix = (haut[page], 0)
        if choix is not None:
            debuts[i], sources[i] = choix[0], "sommaire"
            occupees.add(blocs[choix[0]][0])
    if premier_en_une and debuts and debuts[0] is None and blocs and blocs[0][0] not in occupees:
        debuts[0], sources[0] = 0, "ordre"


def ajuster_debuts(debuts, blocs, sources, premier_en_une=True):
    """Retouches des débuts : surtitre et intertitres placés juste au-dessus du titre retrouvé
    (même page) ; premier article commencé en haut de sa page ; début en haut de page qui
    tombe sur la fin de l'article précédent (paragraphes en minuscule) : on saute cette fin."""
    debuts = list(debuts)
    occupes = {k for k in debuts if k is not None}
    for i, k in enumerate(debuts):
        if k is None:
            continue
        page = blocs[k][0]
        if _est_titre(blocs[k][2]):
            n = 0
            while n < 2 and k - 1 >= 0 and blocs[k - 1][0] == page and _est_titre(blocs[k - 1][2]) \
                    and (k - 1) not in occupes and not _ressemble_sommaire(blocs[k - 1][2]):
                k -= 1
                n += 1
        elif k - 1 >= 0 and blocs[k - 1][0] == page and (k - 1) not in occupes and blocs[k - 1][2].rstrip("*_ ").endswith(":") \
                and (len(blocs[k - 1][2]) < 60 or (len(blocs[k - 1][2]) < 100 and re.match(r"[a-zéèàçâêîôûœ]", blocs[k][2]))):
            k -= 1  # surtitre « Enseignement public : » au-dessus de « Après le vote… »
        elif k == 0 or blocs[k - 1][0] != page:
            # haut de page : la fin de l'article précédent peut s'y trouver
            n = 0
            while n < 3 and k + 1 < len(blocs) and blocs[k + 1][0] == page and (k + 1) not in occupes \
                    and re.match(r"[a-zéèàçâêîôûœ…]", blocs[k][2].lstrip("*_\\")):
                k += 1
                n += 1
        occupes.discard(debuts[i])
        occupes.add(k)
        debuts[i] = k
    # premier article du sommaire, avant tous les autres : depuis le haut de sa page s'il
    # commence en une (bandeau déjà retiré) ; depuis la première page s'il n'a été retrouvé
    # que plus loin par son titre (souvent repris en intertitre de conclusion)
    if debuts and debuts[0] is not None and debuts[0] == min(k for k in debuts if k is not None):
        page = blocs[debuts[0]][0]
        if page <= 2:
            debuts[0] = next(k for k, b in enumerate(blocs) if b[0] == page)
        elif sources[0] == "titre" and premier_en_une:
            debuts[0], sources[0] = 0, "ordre"
    elif premier_en_une and debuts and debuts[0] is not None and sources[0] == "titre" \
            and not any(k is not None and blocs[k][0] == 1 for k in debuts):
        # premier article retrouvé « par son titre » après d'autres (sommaire de dernière
        # page) : il commence en fait en une
        debuts[0], sources[0] = 0, "ordre"
    return debuts


def extraire(blocs, debut, fin, vocab=None):
    """Markdown des blocs [debut, fin) ; le premier intertitre devient le titre affiché (##).
    Les paragraphes coupés par un changement de page ou de colonne sont recousus."""
    morceaux = [texte for _, _, texte in blocs[debut:fin]]
    if morceaux and _est_titre(morceaux[0]):
        morceaux[0] = "## " + morceaux[0].lstrip("#").strip()
    return fusionner_paragraphes("\n\n".join(morceaux), vocab)


# ------------------------------------------------------------ sommaires imprimés

R_ENTREE = re.compile(r"(?P<lead>(?:\.\s?){2,}|…+)(?P<bruit>[^\n]{0,90}?)"
                      r"(?P<ref>(?:\bP\s*[.,]?\s*|\bp\s*[.,\-]?\s*)?(?P<page>\d{1,2}))\s*[^\w\n]{0,2}$")
# entrée sans points de conduite (OCR) : « LA POLITIQUE DE NOTRE CERCLE … issues P.13 »
# (points de conduite lus comme des mots, « EDITORIAL. Lee ae a as aa een .P.1 » : les mots parasites
# contiennent des minuscules, le titre n'en contient pas)
R_ENTREE_NUE = re.compile(r"^(?P<titre>.*?[A-ZÉ]{2}[^a-z\n]*?)(?:\s+(?=\S*[a-zéèàç0-9])\S+)*"
                          r"\s*[.,…]*\s*\bP\s*[.,]\s*(?P<page>\d{1,2})\s*\W{0,2}$")
PUCES_SOMMAIRE = re.compile(r"^[\s*•+#°\-–—-]*(?:e\s+(?=[A-ZÉ]))?")


def sommaire_imprime(pages):
    """Entrées (titre, page) du sommaire imprimé en une (pages 1-2) : lignes
    « TITRE ........ P.12 », points de conduite parfois lus comme des lettres par l'OCR.
    Les sommaires de dernière page de l'ancienne série, sur deux colonnes que l'OCR
    entremêle, ne sont pas retenus. pages : texte brut des pages."""
    entrees = []
    for k in range(min(2, len(pages))):
        lignes = pages[k].split("\n")
        trouvees, precedente = [], ""
        for ligne in lignes:
            debut = 0
            ms = list(R_ENTREE.finditer(ligne))
            nue = R_ENTREE_NUE.match(ligne) if not ms else None
            if nue:
                titre = PUCES_SOMMAIRE.sub("", nue.group("titre")).strip(" .,:;-–")
                lettres = [c for c in titre if c.isalpha()]
                if len(lettres) >= 6 and sum(c.isupper() for c in lettres) >= 0.8 * len(lettres):
                    trouvees.append((titre, int(nue.group("page"))))
                precedente = ""
                continue
            if not ms:
                # début de titre sur la ligne précédente, sauf entrée dont le renvoi est illisible
                precedente = ligne.strip() if re.search(r"[A-ZÉ]{3,}", ligne) and not re.search(
                    r"sommaire|(?:\.\s?){2,}|…", ligne, re.I) else ""
                continue
            for m in ms:
                titre = PUCES_SOMMAIRE.sub("", ligne[debut:m.start()]).strip(" .,:;-–")
                interne = list(re.finditer(r"(?:\.\s?){2,}|…+", titre))
                if interne:
                    # « MICHELIN... 4er ereeuice ss PP EDITORIAL ..... P.3 » : deux entrées fondues,
                    # la page lue est celle de la dernière (mots en capitales à la fin)
                    fin = re.search(r"(?:\b[A-ZÉÈÀÂÊÎÔÛÇ][A-ZÉÈÀÂÊÎÔÛÇ'’\-]{2,}\b[\s:,«»\"()-]*)+$", titre[interne[-1].end():])
                    titre = fin.group(0).strip(" :,-") if fin else ""
                # titre sur deux lignes : début sur la ligne précédente, sans renvoi de page
                if debut == 0 and precedente and (len(titre) < 25 or titre[:1].islower()):
                    titre = PUCES_SOMMAIRE.sub("", precedente).strip() + " " + titre
                if len(re.findall(r"[^\W\d_]", titre)) >= 4:
                    trouvees.append((titre, int(m.group("page"))))
                debut = m.end()
            precedente = ""
        if len(trouvees) >= 3:
            entrees += trouvees
    return entrees


def indices_sommaire(entrees, titres, nb_pages):
    """{indice de titre: page} d'après le sommaire imprimé (appariement des entrées aux titres
    du sommaire du site par les mots du titre ; une entrée sert au plus un article)."""
    paires = []
    for e, (t_e, page) in enumerate(entrees):
        if not 1 <= page <= nb_pages:
            continue
        je = set(jetons_titre(RUBRIQUE.sub("", t_e) or t_e, n=12)) or set(jetons_titre(t_e, n=12))
        if not je:
            continue
        for i, t in enumerate(titres):
            lt = jetons_titre(t, n=20)
            ja = set(lt)
            commun = je & ja
            if not commun or (len(commun) < 2 and len(je) > 1):
                continue
            s = max(len(commun) / len(je), len(commun) / max(1, len(ja)))
            # à score égal : le titre qui commence par les mots de l'entrée (« Iran » → « Iran : … »)
            tete = int(bool(lt) and lt[0] in je)
            if s >= 0.6:
                paires.append((s, tete, -e, -i, page))
    res, pris = {}, {}
    for s, tete, e, i, page in sorted(paires, reverse=True):
        i, e = -i, -e
        if i in res or e in pris.values():
            continue
        res[i], pris[i] = page, e
    return res
