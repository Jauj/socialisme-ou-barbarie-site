"""Localisation des articles dans les pages d'un numéro, d'après leur titre.

Le site n'indique la page de début que pour une minorité d'articles. Pour les
autres, on cherche le titre (ses premiers mots significatifs) dans le texte de
chaque page (couche texte ou OCR), en respectant l'ordre du sommaire quand
c'est possible et en écartant les pages de sommaire (qui citent tous les titres).
"""
import re
import unicodedata

MOTS_VIDES = set("""a au aux avec ce ces dans de des du en et il ils la le les leur lui mais ne ni
non nous on ou par pas pour qu que qui sa se ses son sont sur un une vous est d l n s c j m y""".split())


def jetons(texte):
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("œ", "oe")
    return re.findall(r"[a-z0-9]+", t)


def jetons_titre(titre, n=8):
    # « Éditorial : … », « Supplément … » : on garde tout, on enlève seulement les mots vides
    js = [j for j in jetons(titre) if j not in MOTS_VIDES and len(j) > 1]
    return js[:n]


def score_page(tt, tout_titre, page_jetons, index_pos, lignes):
    """Meilleure proportion des jetons du titre retrouvés dans une fenêtre de la page.

    Ne comptent que les fenêtres qui commencent une ligne composée uniquement de mots
    du titre (à un mot près, pour le bruit d'OCR) : un titre occupe sa propre ligne,
    alors qu'une simple mention du titre dans le corps d'un autre article non."""
    if not tt:
        return 0.0
    cible = set(tt)
    largeur = len(tt) + 6
    meilleur = 0
    for j in tt[:3]:  # la fenêtre doit commencer près du début du titre
        for i in index_pos.get(j, []):
            ligne = lignes.get(i)
            if ligne is None:
                continue
            mots = {m for m in page_jetons[ligne[0]:ligne[1]] if m not in MOTS_VIDES and len(m) > 1}
            if len(mots - tout_titre) > 1:
                continue
            fen = set(page_jetons[i:i + largeur])
            n = len(cible & fen)
            if n > meilleur:
                meilleur = n
                if meilleur == len(cible):
                    return 1.0
    return meilleur / len(cible)


def localiser(titres, pages, seuil=0.75):
    """Renvoie pour chaque titre (dans l'ordre) un n° de page (1-based) ou None."""
    # pour chaque page : jetons, et pour chaque position « proche d'un début de ligne »
    # les bornes de cette ligne
    pj, lignes_pages = [], []
    for p in pages:
        js, lignes = [], {}
        for ligne in p.split("\n"):
            lj = jetons(ligne)
            if lj:
                d, f = len(js), len(js) + len(lj)
                for k in range(d, min(d + 3, f)):
                    lignes.setdefault(k, (d, f))
            js.extend(lj)
        pj.append(js)
        lignes_pages.append(lignes)
    idx = []
    for js in pj:
        d = {}
        for i, j in enumerate(js):
            d.setdefault(j, []).append(i)
        idx.append(d)
    tts = [jetons_titre(t) for t in titres]
    touts = [set(jetons_titre(t, n=1000)) for t in titres]
    scores = [[score_page(tt, tout, pj[k], idx[k], lignes_pages[k]) if len(tt) >= 3 else 0.0  # titres trop courts : trop ambigus
               for k in range(len(pages))] for tt, tout in zip(tts, touts)]
    # pages de sommaire ou de couverture : plusieurs titres y sont reconnus
    nb = [sum(1 for s in scores if s[k] >= seuil) for k in range(len(pages))]
    sommaire = {k for k in range(len(pages))
                if nb[k] >= max(3, len(titres) // 2) or (nb[k] >= 2 and "sommaire" in pj[k])}
    denses = {k for k in range(len(pages)) if nb[k] >= 2}
    res, courant = [], 0
    for s in scores:
        cands = [k for k in range(len(pages)) if s[k] >= seuil and k not in sommaire]
        apres = [k for k in cands if k >= courant]
        # une page qui cite plusieurs titres (couverture, chapeau) n'est retenue qu'à défaut d'autre
        apres = [k for k in apres if k not in denses] or apres
        choix = apres[0] if apres else (cands[0] if cands else None)
        if choix is not None:
            courant = choix
        res.append(choix + 1 if choix is not None else None)
    return res
