"""Découpage des articles dans le Markdown des pages d'une publication.

Chaque page Markdown est une suite de blocs (paragraphes, intertitres « ## » /
« ### », éléments de liste). Pour chaque article du sommaire, on cherche son
titre parmi les intertitres (seuls ou groupés par deux ou trois : surtitre, titre,
sous-titre), en respectant l'ordre du sommaire et en se méfiant des pages qui
citent plusieurs titres (une, sommaire). Le texte d'un article va de son titre
jusqu'au titre de l'article suivant localisé dans le même PDF.
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


def _candidats(titre, blocs):
    """Positions (rang de bloc) dont le groupe d'intertitres correspond au titre, avec score."""
    variantes = [titre]
    sans_rubrique = RUBRIQUE.sub("", titre)
    if sans_rubrique != titre and len(jetons_titre(sans_rubrique)) >= 3:
        variantes.append(sans_rubrique)
    norm_titre = " ".join(jetons(titre))
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
                    tete = set(debut[:len(jetons(v)) + 4])
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
        if " ".join(jetons(texte.lstrip("# "))) == norm_titre and norm_titre:
            meilleur = max(meilleur, 1.0)
        if meilleur >= 0.75:
            res[k] = meilleur
    return res


def _ressemble_sommaire(texte):
    puces = len(re.findall(r"(\\\*|•|●)", texte))
    return puces >= 2 or bool(re.search(r"(\.\s?){3,}\s*\d|…\s*\d|\.{2,}\s*\d+\s*\.{2,}", texte))


def meilleur_bloc_page(titre, blocs, page, seuil=0.5):
    """Sur une page donnée : le bloc dont le début ressemble le plus au titre (ou None)."""
    tt = jetons_titre(RUBRIQUE.sub("", titre), n=8) or jetons_titre(titre, n=8)
    if not tt:
        return None
    meilleur, score = None, 0.0
    for k, (p, rang, texte) in enumerate(blocs):
        if p != page:
            continue
        s = len(set(tt) & set(jetons(texte)[:40])) / len(set(tt))
        if s > score:
            meilleur, score = k, s
    return meilleur if score >= seuil else None


def localiser_blocs(titres, blocs, pages_imposees=None, seuil=0.75):
    """Pour chaque titre : rang du bloc de début (ou None).

    pages_imposees : {indice de titre: page} pour les pages indiquées par le site ; on y
    cherche le titre, à défaut on commence au premier bloc de la page."""
    pages_imposees = pages_imposees or {}
    cands = [_candidats(t, blocs) for t in titres]
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

    for i, c in enumerate(cands):
        for k in list(c):
            if blocs[k][0] in denses and not suivi_de_texte(k):
                del c[k]  # entrée de sommaire ou titre de une

    res = [None] * len(titres)
    pris = set()
    # 1. pages indiquées par le site
    for i, page in pages_imposees.items():
        sur_page = [k for k in cands[i] if blocs[k][0] == page and k not in pris]
        # le site se trompe parfois d'une page : on regarde aussi les pages voisines
        voisines = [k for k in cands[i] if abs(blocs[k][0] - page) == 1 and k not in pris]
        if sur_page:
            res[i] = max(sur_page, key=lambda k: cands[i][k])
        elif voisines:
            res[i] = max(voisines, key=lambda k: cands[i][k])
        else:
            res[i] = meilleur_bloc_page(titres[i], blocs, page)
            if res[i] is None:
                res[i] = next((k for k, b in enumerate(blocs) if b[0] == page), None)
        if res[i] is not None:
            pris.add(res[i])
    # 2. les autres, dans l'ordre du sommaire
    courant = -1
    for i in range(len(titres)):
        if res[i] is not None:
            courant = max(courant, res[i])
            continue
        c = {k: s for k, s in cands[i].items() if k not in pris}
        apres = sorted(k for k in c if k > courant)
        hors_denses = [k for k in apres if blocs[k][0] not in denses]
        choix = (hors_denses or apres or [None])[0]
        if choix is None:  # hors de l'ordre du sommaire : seulement une correspondance très sûre
            sures = sorted(k for k, s in c.items() if s >= 0.9 and blocs[k][0] not in denses)
            choix = sures[0] if sures else None
        if choix is not None:
            res[i] = choix
            pris.add(choix)
            courant = max(courant, choix)
    return res


def extraire(blocs, debut, fin, vocab=None):
    """Markdown des blocs [debut, fin) ; le premier intertitre devient le titre affiché (##).
    Les paragraphes coupés par un changement de page ou de colonne sont recousus."""
    morceaux = [texte for _, _, texte in blocs[debut:fin]]
    if morceaux and _est_titre(morceaux[0]):
        morceaux[0] = "## " + morceaux[0].lstrip("#").strip()
    return fusionner_paragraphes("\n\n".join(morceaux), vocab)
