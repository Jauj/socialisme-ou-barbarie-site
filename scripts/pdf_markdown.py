"""Mise en Markdown des pages de PDF.

Deux sources :
  - PDF à couche texte (numéros récents, suppléments) : « pdftohtml -xml » donne
    chaque ligne avec sa position, sa police, sa taille, gras et italique. On en
    déduit paragraphes (interlignes, lignes courtes, retraits), intertitres
    (taille ou gras), listes et emphases ;
  - pages océrisées (scans) : le texte brut de Tesseract (paragraphes séparés par
    des lignes vides) ; intertitres = lignes en capitales, listes = tirets.

Dans les deux cas : en-têtes courants (« C.P.S. … page 12 »), numéros de page et
devise du journal supprimés ; césures de fin de ligne recollées d'après le
vocabulaire du corpus (« mar-/quées » → « marquées », mais « Jospin-/Gayssot »
reste composé).

Conventions communes avec html_markdown.py : « ## » titre affiché, « ### »
intertitre, « - » liste, « *…* » italique, « **…** » gras.
"""
import html
import re
import subprocess
from collections import Counter

DEVISE = re.compile(r"on ne peut aller de l.avant si l.on craint d.aller au socialisme", re.I)
ENTETE = re.compile(r"^\W{0,3}C\s?\.?\s?P\s?\.?\s?S\s?\.?\s*(N\s?°|n\s?°|nouvelle\s+s[ée]rie|Nouvelle\s+s[ée]rie|N\s?o\b)", re.I)
FIN_PHRASE = re.compile(r"[.!?…:;»\"”)\]]\s*$")
PUCES = "•●▪■◆♦·-–—➢►✓"


def est_puce(c):
    return bool(c) and (c in PUCES or "\uf000" <= c <= "\uf0ff")


def retirer_puce(t):
    return re.sub(r"^\s*(?:[" + re.escape(PUCES) + r"]|[\uf000-\uf0ff])+\s*", "", t, count=1)


# ----------------------------------------------------------- vocabulaire

def mots(texte):
    return re.findall(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", texte)


class Vocabulaire:
    """Fréquences des mots du corpus, pour décider des césures."""

    def __init__(self, textes=()):
        self.freq = Counter()
        for t in textes:
            self.ajouter(t)

    def ajouter(self, texte):
        # on ignore les mots coupés en fin de ligne pour ne pas compter les fragments
        texte = re.sub(r"[^\W\d_]+-\s*\n\s*[^\W\d_]+", " ", texte)
        self.freq.update(m.lower() for m in mots(texte))

    def recoller(self, avant, apres):
        """Fin de ligne « avant- » suivie de « apres… » : renvoie le séparateur ('' ou '-')."""
        a = re.search(r"([^\W\d_]+)-$", avant)
        b = re.match(r"([^\W\d_]+)", apres)
        if not a or not b:
            return "-"
        g, d = a.group(1), b.group(1)
        if d[0].isupper():
            return "-"  # « Jospin-Gayssot », « Moyen-Orient »
        soude, compose = self.freq[(g + d).lower()], self.freq[(g + "-" + d).lower()]
        if compose > soude:
            return "-"
        if soude > 0:
            return ""
        # mot inconnu : une coupure en fin de ligne au milieu d'un mot est le cas le plus fréquent,
        # sauf préfixes courants de mots composés
        if g.lower() in {"anti", "contre", "néo", "neo", "ex", "post", "pro", "sous", "non", "semi",
                         "auto", "socio", "politico", "franco", "germano", "arabo", "israélo", "sino",
                         "vice", "demi", "mi", "grand", "petite", "petit", "arrière", "avant", "porte"}:
            return "-"
        return ""


# ------------------------------------------------------------- emphases

def _echapper(t):
    t = t.replace("\\", "\\\\").replace("*", "\\*").replace("`", "\\`")
    t = t.replace("[", "\\[").replace("]", "\\]").replace("<", "\\<")
    return t


def rendre_runs(runs):
    """[(texte, gras, italique)] → Markdown inline aux emphases équilibrées."""
    # fragments sans lettre : prennent le style de leurs voisins s'ils sont identiques
    runs = [list(r) for r in runs if r[0]]
    for i, r in enumerate(runs):
        if not re.search(r"\w", r[0]):
            av = runs[i - 1] if i > 0 else None
            ap = runs[i + 1] if i + 1 < len(runs) else None
            if av and ap and av[1:] == ap[1:]:
                r[1], r[2] = av[1], av[2]
            else:
                r[1] = r[2] = False
    fusion = []
    for r in runs:
        if fusion and fusion[-1][1:] == r[1:]:
            fusion[-1][0] += r[0]
        else:
            fusion.append(r)
    sortie = []
    for i, (t, g, it) in enumerate(fusion):
        if not (g or it) or not re.search(r"\w", t):
            sortie.append(_echapper(t))
            continue
        m = re.match(r"^(\s*)(.*?)(\s*)$", t, re.S)
        deb, coeur, fin = m.groups()
        avant = (fusion[i - 1][0][-1:] if i > 0 else " ") if not deb else " "
        apres = (fusion[i + 1][0][:1] if i + 1 < len(fusion) else " ") if not fin else " "
        # ponctuation de bord collée à une lettre extérieure : hors de l'emphase
        p1 = re.match(r"^([^\w\s]+)", coeur)
        pre = ""
        if p1 and avant.isalnum():
            pre, coeur = p1.group(1), coeur[p1.end():]
        p2 = re.search(r"([^\w\s]+)$", coeur)
        post = ""
        if p2 and apres.isalnum():
            post, coeur = p2.group(1), coeur[:p2.start()]
        if not re.search(r"\w", coeur):
            sortie.append(_echapper(t))
            continue
        # la ponctuation sortie peut laisser un blanc collé au marqueur : on le sort aussi
        m2 = re.match(r"^(\s*)(.*?)(\s*)$", coeur, re.S)
        deb2, coeur, fin2 = m2.groups()
        marque = "***" if g and it else ("**" if g else "*")
        sortie.append(deb + _echapper(pre) + deb2 + marque + _echapper(coeur) + marque + fin2 + _echapper(post) + fin)
    md = "".join(sortie)
    md = re.sub(r"\s+", " ", md).strip()
    if re.match(r"^(#|>|[-+] |\d+[.)] )", md):
        md = "\\" + md
    return md


# ----------------------------------------------------- PDF à couche texte

class Ligne:
    __slots__ = ("top", "left", "right", "h", "taille", "gras", "ital", "runs", "page_h", "tailles")

    def __init__(self):
        self.runs = []
        self.tailles = Counter()

    @property
    def texte(self):
        return "".join(r[0] for r in self.runs)


def normaliser_texte(t, famille=""):
    """Caractères des polices Symbol / Wingdings (zone privée Unicode) et lettres espacées."""
    def pua(m):
        c = ord(m.group(0))
        if re.search(r"wingding|webding", famille, re.I) or c in (0xF0B7, 0xF0A7, 0xF097):
            return "•"
        if 0xF020 <= c <= 0xF040:
            return chr(c - 0xF000)
        return ""
    t = re.sub(r"[\uf000-\uf0ff]", pua, t)
    # « L a   l o i   S a u v a d e t » : lettres séparées d'un blanc, mots de plusieurs
    morceaux = [m for m in t.split(" ") if m]
    if len(morceaux) >= 6 and sum(len(m) == 1 for m in morceaux) >= 0.85 * len(morceaux) and re.search(r"\S {2,}\S", t):
        fin = " " if t.endswith(" ") else ""
        t = " ".join(mot.replace(" ", "") for mot in re.split(r" {2,}", t.strip())) + fin
    return t


def _runs_html(contenu, gras_police, ital_police, famille=""):
    runs, b, i = [], 0, 0
    for tag, txt in re.findall(r"(<[^>]+>)|([^<]+)", contenu):
        if tag:
            nom = tag.strip("</> ").split()[0].lower() if tag.strip("</> ") else ""
            ferme = tag.startswith("</")
            if nom == "b":
                b += -1 if ferme else 1
            elif nom == "i":
                i += -1 if ferme else 1
        else:
            runs.append((normaliser_texte(html.unescape(txt), famille), b > 0 or gras_police, i > 0 or ital_police))
    return runs


def lignes_pdf(chemin):
    """Pages → listes de Ligne, d'après pdftohtml -xml (ordre du flux = ordre de lecture)."""
    xml = subprocess.run(["pdftohtml", "-xml", "-i", "-stdout", "-q", "-nodrm", str(chemin)],
                         capture_output=True).stdout.decode("utf-8", "replace")
    polices = {}
    pages = []
    for m in re.finditer(r"<page\b([^>]*)>(.*?)</page>", xml, re.S):
        h_page = float(re.search(r'height="([\d.]+)"', m.group(1)).group(1))
        lignes = []
        for fs in re.finditer(r'<fontspec id="(\d+)" size="([\d.-]+)" family="([^"]*)"', m.group(2)):
            polices[fs.group(1)] = (float(fs.group(2)), fs.group(3))
        for t in re.finditer(r'<text top="(-?[\d.]+)" left="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)" font="(\d+)">(.*?)</text>',
                             m.group(2), re.S):
            top, left, w, h = (float(t.group(k)) for k in range(1, 5))
            taille, famille = polices.get(t.group(5), (h, ""))
            gp = bool(re.search(r"bold|black|heavy|semibold|demi", famille, re.I))
            ip = bool(re.search(r"italic|oblique", famille, re.I))
            runs = _runs_html(t.group(6), gp, ip, famille)
            if not "".join(r[0] for r in runs).strip():
                continue
            n_car = len("".join(r[0] for r in runs).strip())
            der = lignes[-1] if lignes else None
            recouvre = der and (min(top + h, der.top + der.h) - max(top, der.top)) >= 0.5 * min(h, der.h)
            if der and recouvre and left >= der.right - 3:
                if left - der.right > 1 and not der.texte.endswith(" ") and not runs[0][0].startswith(" "):
                    der.runs.append((" ", False, False))
                der.runs.extend(runs)
                der.right = max(der.right, left + w)
                der.tailles[taille] += n_car
                der.taille = der.tailles.most_common(1)[0][0]
                der.top, der.h = min(der.top, top), max(der.top + der.h, top + h) - min(der.top, top)
                continue
            ln = Ligne()
            ln.top, ln.left, ln.right, ln.h, ln.taille, ln.page_h = top, left, left + w, h, taille, h_page
            ln.runs = runs
            ln.tailles[taille] += n_car
            lignes.append(ln)
        for ln in lignes:
            n = sum(len(r[0].strip()) for r in ln.runs) or 1
            ln.gras = sum(len(r[0].strip()) for r in ln.runs if r[1]) / n
            ln.ital = sum(len(r[0].strip()) for r in ln.runs if r[2]) / n
        pages.append(lignes)
    return pages


def _est_parasite(texte):
    t = texte.strip()
    if not t:
        return True
    if ENTETE.match(t) and len(t) < 140:
        return True
    if DEVISE.search(t) and len(t) < 140:
        return True
    if re.fullmatch(r"[-–—\s]*\d{1,3}[-–—\s]*", t):  # numéro de page
        return True
    if re.search(r"(\.\s?){6,}\s*(P\.?|p\.?|page)?\s*\d{0,3}\s*$", t) or re.search(r"…{3,}\s*\d", t):
        return True  # entrée de sommaire à points de conduite
    if re.fullmatch(r"\W*sommaire\W*", t, re.I):
        return True
    if re.fullmatch(r"(le\s*)?\d{1,2}\s*(er)?\s+[A-ZÉÛa-zéû]+\s+(19|20)\d\d\.?", t) and t.upper() == t:
        return True  # date du bandeau de une (« 2 DECEMBRE 1989 »)
    return False


def _joindre(lignes, vocab):
    """Lignes d'un paragraphe → runs, césures recollées."""
    runs = []
    for k, ln in enumerate(lignes):
        lr = [list(r) for r in ln.runs]
        if not lr:
            continue
        lr[0][0] = lr[0][0].lstrip()
        if k + 1 < len(lignes):
            lr[-1][0] = lr[-1][0].rstrip()
            fin = lr[-1][0]
            suivant = lignes[k + 1].texte.lstrip()
            if fin.endswith("­"):
                lr[-1][0] = fin[:-1]
            elif re.search(r"[^\W\d_]-$", fin) and suivant[:1].isalpha():
                if vocab.recoller(fin, suivant) == "":
                    lr[-1][0] = fin[:-1]
            else:
                lr[-1][0] = fin + " "
        runs.extend(tuple(r) for r in lr)
    return runs


def pages_markdown_pdf(chemin, vocab):
    """Markdown de chaque page d'un PDF à couche texte."""
    pages = lignes_pdf(chemin)
    tailles = Counter()
    for lignes in pages:
        for ln in lignes:
            tailles[round(ln.taille)] += len(ln.texte.strip())
    corps = tailles.most_common(1)[0][0] if tailles else 12

    sorties = []
    for lignes in pages:
        lignes = [ln for ln in lignes if not _est_parasite(ln.texte)]
        # colonnes : regroupement des bords gauches des lignes de corps (à 6 px près) ;
        # bord droit d'une colonne = 90e percentile des bords droits de ses lignes
        corps_l = sorted((ln for ln in lignes if abs(ln.taille - corps) <= 1.5), key=lambda l: l.left)
        groupes = []
        for ln in corps_l:
            if groupes and ln.left - groupes[-1][0] <= 6:
                groupes[-1][1].append(ln.right)
            else:
                groupes.append((ln.left, [ln.right]))
        colonnes = {g: sorted(d)[int(0.9 * (len(d) - 1))] for g, d in groupes if len(d) >= 4}

        def bord_droit(ln):
            cands = [g for g in colonnes if g <= ln.left + 8]
            return colonnes[max(cands)] if cands else ln.right

        def nature(ln):
            if ln.taille >= corps * 1.3:
                return "h2"
            if ln.taille >= corps + 1.5:
                return "h3"
            if ln.gras >= 0.9:
                return "gras"
            return "p"

        blocs, courant = [], []

        def clore():
            if courant:
                blocs.append(list(courant))
                courant.clear()

        for ln in lignes:
            if not courant:
                courant.append(ln)
                continue
            prec = courant[-1]
            texte = ln.texte.strip()
            coupe = False
            if nature(ln) != nature(prec):
                coupe = True
            elif est_puce(texte[:1]) and (texte[1:2].isspace() or "\uf000" <= texte[:1] <= "\uf0ff"):
                coupe = True
            elif est_puce(courant[0].texte.strip()[:1]) and ln.left > courant[0].left + 3 and 0 < ln.top - prec.top <= 1.6 * prec.h:
                coupe = False  # suite (en retrait) d'un élément de liste
            else:
                ecart = ln.top - prec.top
                if ecart > 1.6 * prec.h:
                    coupe = True
                elif nature(prec) in ("h2", "h3", "gras") and 0 < ecart:
                    coupe = False  # titre sur plusieurs lignes
                elif ecart > 0 or ecart < -3 * prec.h:  # même colonne, ou saut de colonne
                    courte = prec.right < bord_droit(prec) - 3 * corps / 2
                    if courte and (FIN_PHRASE.search(prec.texte) or texte[:1].isupper() or texte[:1] in "«\"“"):
                        coupe = True
                    elif ln.left > prec.left + 1.2 * corps and not courte and ecart > 0 and nature(ln) == "p":
                        coupe = True  # retrait de première ligne
            if coupe:
                clore()
            courant.append(ln)
        clore()

        md = []
        for bloc in blocs:
            n = nature(bloc[0])
            runs = _joindre(bloc, vocab)
            texte = "".join(r[0] for r in runs).strip()
            if not texte:
                continue
            # un titre ne commence pas par une minuscule (suite d'une phrase en gras) et ne
            # dépasse pas 200 caractères (paragraphe en gras ou en grand corps)
            liste = est_puce(texte[:1]) and (texte[1:2].isspace() or "\uf000" <= texte[:1] <= "\uf0ff")
            if (texte[:1].islower() or len(texte) > 200 or liste) and n in ("h2", "h3", "gras"):
                n = "p"
            if n in ("h2", "h3") or n == "gras":
                titre = re.sub(r"\s+", " ", _echapper(texte))
                md.append(("## " if n == "h2" else "### ") + titre)
                continue
            if liste:
                # la puce peut être un fragment à part (police Symbol) : on la retire du début
                restants, retire = [], False
                for r in runs:
                    if not retire:
                        t2 = retirer_puce(r[0])
                        if t2 != r[0] or not r[0].strip():
                            retire = retire or t2 != r[0]
                            if t2.strip():
                                restants.append((t2, r[1], r[2]))
                                retire = True
                            continue
                        retire = True
                    restants.append(r)
                md.append("- " + rendre_runs(restants))
                continue
            md.append(rendre_runs(runs))
        sorties.append(fusionner_paragraphes("\n\n".join(md), vocab))
    return sorties


# ------------------------------------------------------------ pages OCR

def _bruit_ocr(t, vocab):
    ms = mots(t)
    if not ms:
        return True
    connus = sum(1 for m in ms if vocab.freq[m.lower()] >= 5)
    return connus / len(ms) < 0.5 and len(t) < 400


def _majuscules(t):
    lettres = [c for c in t if c.isalpha()]
    return len(lettres) >= 6 and sum(c.isupper() for c in lettres) >= 0.85 * len(lettres)


def _nettoyer_ligne_ocr(l):
    l = re.sub(r"^[\s|‘’'`_\[\]{}]+(?=[^\W\d_])", "", l) if re.match(r"^\s*[|‘’`_\[\]{}]", l) else l
    return l.rstrip()


def page_markdown_ocr(texte, vocab):
    """Markdown d'une page océrisée (texte brut de Tesseract)."""
    blocs = [b for b in re.split(r"\n\s*\n", texte) if b.strip()]
    md = []
    for b in blocs:
        lignes = [_nettoyer_ligne_ocr(l) for l in b.split("\n")]
        lignes = [l for l in lignes if l.strip() and not _est_parasite(l)
                  and len(re.sub(r"[\W_]", "", l)) >= 2]
        if not lignes:
            continue
        brut = " ".join(l.strip() for l in lignes)
        if re.sub(r"\W+", " ", brut).strip().lower() == "combattre pour le socialisme":
            continue  # titre du journal
        if vocab is not None and _bruit_ocr(brut, vocab):
            continue  # filets, dessins ou taches lus comme du texte
        # liste à tirets
        if all(re.match(r"^\s*[-–—•]\s+", l) or not re.match(r"^\s*[-–—•]", l) for l in lignes) and \
                re.match(r"^\s*[-–—•]\s+", lignes[0]):
            items, cour = [], []
            for l in lignes:
                if re.match(r"^\s*[-–—•]\s+", l) and cour:
                    items.append(cour)
                    cour = []
                cour.append(re.sub(r"^\s*[-–—•]\s+", "", l) if not cour else l)
            items.append(cour)
            for it in items:
                md.append("- " + _echapper(_joindre_texte(it, vocab)))
            continue
        texte_bloc = _joindre_texte(lignes, vocab)
        if _majuscules(texte_bloc) and len(texte_bloc) <= 200:
            md.append("### " + _echapper(texte_bloc))
        else:
            t = _echapper(texte_bloc)
            if re.match(r"^(#|>|[-+] |\d+[.)] )", t):
                t = "\\" + t
            md.append(t)
    return fusionner_paragraphes("\n\n".join(md), vocab)


def _joindre_texte(lignes, vocab):
    sortie = ""
    for k, l in enumerate(lignes):
        l = l.strip()
        if k == 0:
            sortie = l
            continue
        if re.search(r"[^\W\d_]-$", sortie) and l[:1].isalpha():
            sep = vocab.recoller(sortie, l)
            sortie = sortie[:-1] + ("-" if sep == "-" else "") + l
        else:
            sortie += " " + l
    return re.sub(r"\s+", " ", sortie).strip()


# ------------------------------------------------------------ commun

def fusionner_paragraphes(md, vocab=None):
    """Recolle deux paragraphes consécutifs quand le premier s'interrompt au milieu
    d'une phrase et que le second commence par une minuscule (saut de colonne)."""
    blocs = md.split("\n\n")
    sortie = []
    for b in blocs:
        if sortie and _suite(sortie[-1], b):
            prec = sortie[-1]
            if prec.endswith("-") and re.match(r"[^\W\d_]", b):
                sep = vocab.recoller(prec, b) if vocab else ""
                sortie[-1] = prec[:-1] + sep + b
            else:
                sortie[-1] = prec + " " + b
        else:
            sortie.append(b)
    return "\n\n".join(sortie)


def _suite(prec, b):
    if not prec or not b or prec.startswith(("#", "|")) or b.startswith(("#", "- ", "|", ">")):
        return False
    if prec.startswith("- ") and not b.lstrip("*_\\")[:1].islower():
        return False  # après un élément de liste, seule une suite en minuscule s'y rattache
    if FIN_PHRASE.search(prec.rstrip("*")):
        return False
    debut = b.lstrip("*_\\")
    fin = prec.rstrip("*_")
    # phrase interrompue : fin en minuscule ou sur une virgule, ou suite en minuscule
    return bool(debut[:1]) and (debut[:1].islower() or fin[-1:].islower() or fin.endswith(("-", ",", "'", "’")))
