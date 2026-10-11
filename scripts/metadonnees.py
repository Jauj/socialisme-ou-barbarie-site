"""Métadonnées déduites des textes eux-mêmes.

- date_imprimee : date lue dans l'en-tête de la une d'une publication, à comparer avec la
  date donnée par le site (écarts signalés dans le rapport de qualité) ;
- date_redaction : date qui clôt un article (« Le 7 avril 2008 », « Le 2/3/1990 ») ;
- tags_du_texte : tags déduits du texte intégral, quand un motif y revient assez souvent
  (règles « texte » de config/regles_tags.json).
"""
import calendar
import functools
import json
import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from functools import partial

MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
        "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
_MOIS = r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"
R_DATE = re.compile(rf"(?<![\d/.])(1er|\d{{1,2}})\s*(?:er)?\s+{_MOIS}\s+((?:19|20)\d\d)\b", re.I)
R_MOIS_SEUL = re.compile(rf"(?<!\w){_MOIS}\s+((?:19|20)\d\d)\b", re.I)
# ligne isolée en fin d'article : « Le 7 avril 2008 », « Paris, le 3 juin 2006 », « Le 2/3/1990 »
_LIEU = r"(?:[A-ZÉ][\w'’\- ]{1,30},\s*)?"
R_FIN = re.compile(rf"^\W*{_LIEU}(?:le\s+)?(1er|\d{{1,2}})\s*(?:er)?\s+{_MOIS}\s+((?:19|20)\d\d)\W*$", re.I)
R_FIN_NUM = re.compile(rf"^\W*{_LIEU}(?:le\s+)?(\d{{1,2}})\s*[/.]\s*(\d{{1,2}})\s*[/.]\s*((?:19|20)?\d\d)\W*$", re.I)
LIGNES_EN_TETE = 8      # la date de la une est dans les premières lignes non vides
LIGNES_FIN = 4          # la date de rédaction est dans les dernières lignes non vides
LONGUEUR_LIGNE_DATE = 60


def _sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _iso(annee, mois, jour):
    """Date ISO (jour 00 = inconnu), ou None si invalide."""
    if not (1 <= mois <= 12) or not (0 <= jour <= calendar.monthrange(annee, mois)[1]):
        return None
    return f"{annee:04d}-{mois:02d}-{jour:02d}"


def _jour(s):
    return 1 if s.lower() == "1er" else int(s)


def date_imprimee(page1, date_site, ocr=False):
    """(date ISO, extrait) lue dans l'en-tête de la une, ou None.

    Seules les dates à un an au plus de la date du site sont retenues (une date plus lointaine
    est celle d'un événement cité). Sur un scan, une date qui ne diffère de celle du site que
    d'un caractère est tenue pour une erreur d'OCR et ignorée."""
    tete = "\n".join([l for l in page1.splitlines() if l.strip()][:LIGNES_EN_TETE])
    annee = int(date_site[:4])
    trouvee = None
    for m in R_DATE.finditer(tete):
        d = _iso(int(m.group(3)), MOIS[_sans_accents(m.group(2))], _jour(m.group(1)))
        if d and abs(int(m.group(3)) - annee) <= 1:
            trouvee = (d, m.group(0))
            break
    if not trouvee:
        for m in R_MOIS_SEUL.finditer(tete):
            if abs(int(m.group(2)) - annee) <= 1:
                trouvee = (_iso(int(m.group(2)), MOIS[_sans_accents(m.group(1))], 0), m.group(0))
                break
    if not trouvee:
        return None
    d = trouvee[0]
    if ocr and d != date_site and not d.endswith("-00") and sum(a != b for a, b in zip(d, date_site)) == 1:
        return None
    return d, re.sub(r"\s+", " ", trouvee[1])


def comparer_dates(imprimee, site):
    """Nature de l'écart entre date imprimée et date du site."""
    if imprimee == site:
        return "identique"
    if imprimee.endswith("-00"):
        return "identique (mois)" if imprimee[:7] == site[:7] else "mois différent"
    if imprimee[:7] == site[:7]:
        return "jour différent"
    if imprimee[5:] == site[5:] and imprimee[5:7] == "01":
        return "millésime différent en janvier (coquille probable)"
    if imprimee[5:] == site[5:]:
        return "année différente"
    return "date différente"


def date_redaction(md, annee_pub=None):
    """(date ISO, ligne) de la date isolée qui clôt l'article, ou None.

    annee_pub : année de la publication ; une année à deux chiffres prend le siècle le plus
    proche, et une date à plus de deux ans de la publication (millésime mal lu par l'OCR,
    date historique citée) est écartée."""
    lignes = [l.strip() for l in md.rstrip().splitlines() if l.strip()]
    for l in reversed(lignes[-LIGNES_FIN:]):
        l = re.sub(r"[*_\\]", "", l).strip()
        if len(l) > LONGUEUR_LIGNE_DATE:
            continue
        m = R_FIN.match(l)
        if m:
            d = _iso(int(m.group(3)), MOIS[_sans_accents(m.group(2))], _jour(m.group(1)))
        else:
            m = R_FIN_NUM.match(l)
            if not m:
                continue
            a = int(m.group(3))
            if a < 100:
                a += min((1900, 2000), key=lambda siecle: abs(siecle + a - annee_pub)) if annee_pub else (
                    1900 if a >= 50 else 2000)
            d = _iso(a, int(m.group(2)), int(m.group(1)))
        if d and not d.endswith("-00") and (annee_pub is None or abs(int(d[:4]) - annee_pub) <= 2):
            return d, l
    return None


def compiler_regles_texte(config):
    """Règles « texte » de config/regles_tags.json → [(tag, motif compilé, min, densité)]."""
    defaut_min, defaut_densite = config.get("min", 3), config.get("densite", 1.0)
    return [(r["tag"], re.compile(r["motif"], 0 if r.get("casse") else re.I),
             r.get("min", defaut_min), r.get("densite", defaut_densite))
            for r in config["regles"]]


@functools.lru_cache(maxsize=4)
def _regles(config_json):
    return compiler_regles_texte(json.loads(config_json))


def _tags_texte(texte, config_json):
    return tags_du_texte(texte, _regles(config_json))


def tags_des_textes(textes, config, processus=None):
    """tags_du_texte pour une liste de textes, répartis sur plusieurs processus."""
    config_json = json.dumps(config, sort_keys=True)
    with ProcessPoolExecutor(processus) as ex:
        return list(ex.map(partial(_tags_texte, config_json=config_json), textes, chunksize=8))


def tags_du_texte(texte, regles):
    """[(tag, occurrences)] des règles dont le motif revient au moins `min` fois dans le texte
    et au moins `densite` fois pour 1 000 mots."""
    mots = len(re.findall(r"\w+", texte))
    if not mots:
        return []
    res = []
    for tag, motif, mini, densite in regles:
        n = sum(1 for _ in motif.finditer(texte))
        if n >= mini and n * 1000 / mots >= densite:
            res.append((tag, n))
    return res
