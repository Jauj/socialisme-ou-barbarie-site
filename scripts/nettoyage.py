"""Nettoyage du Markdown des pages et des articles : bruit éditorial et intertitres.

Appliqué une fois par extraire_markdown.py (pages des publications, textes propres aux
articles), puis une fois par build_db.py sur chaque article découpé (règles propres aux
articles : hiérarchie des titres, faux intertitres, sommaires en tête des pages HTML).

Bruit retiré :
  - bulletins d'abonnement (NOM, PRÉNOM, ADRESSE…, « chèque à l'ordre de… ») ;
  - mentions légales (directeur de la publication, commission paritaire, ISSN, imprimerie)
    et coordonnées (adresse de l'A.E.P.S., e-mail et site du journal) ;
  - liens de navigation des pages HTML (« Retour à l'accueil », « Vers la section… ») ;
  - renvois de mise en page (« suite page 4 », « …/… ») et en-têtes courants restés dans
    le texte (« Supplément à C.P.S. … – 7 juillet 2019 – page 15 ») ;
  - bandeau de une (titre du journal, « Comité pour la construction… », devise, prix) ;
  - sommaires imprimés, et traînées de caractères que l'OCR a lues dans les filets et les
    points de conduite (« eeeneneeneeeeennnenen… ») ;
  - confusions systématiques de l'OCR corrigées en contexte : « Île/Îles » pour « le/les »,
    « 11/11s » pour « Il/Ils », « Ja »/« ia » pour « la ».

Intertitres :
  - intertitres sans lettre supprimés ; intertitres illisibles (OCR) supprimés ;
  - intertitre coupé en plusieurs blocs recollé (suite en minuscule, mot coupé, mot outil
    en fin de ligne) ;
  - dates et mentions « Article paru dans… » rendues au texte ;
  - lettrines recollées au mot (« **G**uerre » → « Guerre ») ; lettrine perdue par l'OCR
    rétablie d'après le corpus (« es projets de loi » → « Les projets de loi ») ;
  - dans un article : paragraphes pris pour des intertitres (trop longs, phrases
    complètes) rendus au texte ; « ## » réservé au titre, intertitres du corps décalés.
"""
import re

from html_markdown import _equilibrer, nettoyer_markdown
from pdf_markdown import fusionner_paragraphes, mots

MOIS = r"(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"
DATE = rf"(?:\d{{1,2}}(?:er)?\s+{MOIS}\s+(?:19|20)\d\d|\d{{1,2}}\s?/\s?\d{{1,2}}\s?/\s?(?:19|20)?\d\d)"
CPS = r"(?:C\s?\.?-?\s?P\s?\.?\s?[S5]\b\.?|Combattre pour le socialisme)"  # « C.P.5. » : S lu 5

# ------------------------------------------------------------------ en ligne

MENTIONS = [
    r"(?-i:D)irecteur\s+de\s+(?:[lf]a\s+)?publication\w?\s*:?\s*(?:(?-i:[A-ZÉ])[\w'’\-]+(?:\s+(?-i:[A-ZÉ])[\w'’\-]+)?)?",
    r"Commission\s+paritaire\s*(?:n\s*°|no\b|n\.)?\s*:?\s*(?:\d{4,5}|en\s+cours\b\.?)",
    r"(?:N\s*°|Num[ée]ro\s*°?)?\s*(?:[IL1]\s?\.?\s?S\s?\.?\s?S\s?\.?\s?N\s?\.?|[\w.]{2,12})?\s*:?\s*0763\s?-?\s?790\s?X?",
    r"Imprimerie\s+sp[ée]cia[il]e",
    r"(?:©\s*)?A\.?\s?E\.?\s?P\.?\s?S\.?,?\s*1\s*bis,?\s*rue\s+Gutenberg,?\s*93100\s+Montreuil",
    r"(?:St[ée]phane\s+JUST\s*[-–,]?\s*)?B\.?\s?P\.?\s*154\s*[-–,]?\s*92804(?:\s+P\s?uteaux(?:\s+C[ée]dex)?)?",
    r"(?:e[.\-]?mail|courriel)\s*:\s*socialisme@free(?:\.fr)?",
    r"Site(?:\s+web|\s+internet)?\s*:\s*https?\s?:\s?//socialisme\.free\.fr/?(?![\w/])",
    r"©\s*A\.?\s?E\.?\s?P\.?\s?S\b\.?",
]
R_MENTIONS = re.compile("|".join(f"(?:{m})" for m in MENTIONS), re.I)
SEP = r"(?:--|[-–—|•/,;])"
R_TROU = re.compile(rf"(?:\s*{SEP})*\s*\x00(?:\s*(?:{SEP}|\x00))*\s*")

R_ENTETE_PAGE = re.compile(
    rf"(?:Suppl[ée]ment\s+(?:à\s+|au\s+)?)?{CPS}[^\n]{{0,60}}?{DATE}\s*[-–—]+\s*page\s*\d+"
    rf"|\b\d{{1,2}}\s+{CPS}\s+N\s?°\s*(?:\d+\s*[-=–—]+\s*|sp[ée]cial\s*(?:[-=–—]+\s*|du\s+)?)?{DATE}", re.I)
R_SUITE = re.compile(
    r"\(\s*(?:voir\s+(?:la\s+)?)?suite\s+(?:en\s+|de\s+la\s+|à\s+la\s+)?(?:page|p\.)\s*\d+\s*\)"
    r"|(?<![\w’'])(?:voir\s+(?:la\s+)?)?suite\s+(?:en\s+)?(?:page|p\.)\s*\d+\b\.?"
    r"|(?:\.\.\.|…)\s*/\s*(?:\.\.\.|…)", re.I)
R_NAV = re.compile(r"\[\s*(?:Retour\b[^\]]*|Vers\s+(?:l.\s?accueil|la\s+section|le\s+sommaire|la\s+page)[^\]]*"
                   r"|Accueil|Haut\s+de\s+(?:la\s+)?page|Page\s+(?:pr[ée]c[ée]dente|suivante))\s*\]\([^)]*\)", re.I)
# lettrine composée à part : « **G**uerre », « ***L****es mobilisations… »
R_LETTRINE = re.compile(r"(?<![\w*\\])(\*{1,3})([A-ZÉÈÀÂÊÎÔÛÇ])\1(\*{0,3})(?=[a-zéèàçâêîôûœ])")


def _retirer(texte, regex):
    """Retire les correspondances de regex et les séparateurs qui les bordent."""
    t = regex.sub("\x00", texte)
    if "\x00" not in t:
        return texte
    t = R_TROU.sub(" ", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _spans_bruit(t, vocab, n=40):
    """Traînées de caractères sans diversité (≤ 7 lettres distinctes sur 40) et faites
    de mots inconnus : filets, points de conduite ou trames lus par l'OCR."""
    lettres = [(i, c.lower()) for i, c in enumerate(t) if c.isalpha()]
    if len(lettres) < n:
        return []
    marques = []
    for s in range(0, len(lettres) - n + 1, 4):
        w = lettres[s:s + n]
        if len({c for _, c in w}) <= 7:
            a, b = w[0][0], w[-1][0] + 1
            if marques and a <= marques[-1][1]:
                marques[-1][1] = max(marques[-1][1], b)
            else:
                marques.append([a, b])
    res = []
    for a, b in marques:
        while a > 0 and not t[a - 1].isspace():
            a -= 1
        while b < len(t) and not t[b].isspace():
            b += 1
        ms = mots(t[a:b])
        connus = sum(1 for m in ms if len(m) >= 3 and vocab is not None and vocab.freq[m.lower()] >= 5)
        if not ms or connus / len(ms) < 0.6:
            res.append((a, b))
    return res


def _sans_bruit_ocr(t, vocab):
    for a, b in reversed(_spans_bruit(t, vocab)):
        t = t[:a] + " " + t[b:]
    return re.sub(r"[ \t]{2,}", " ", t).strip()


R_ORNEMENT = re.compile(r"\s*-{2,}\s*o\s*O\s*o\s*-{2,}\s*")  # « ----- oOo ----- »


MOIS_UNITES = (r"(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre"
               r"|heures?|h|ans|jours|mois|semaines|pour|sur|à|et|ou|de|des|du)\b")
CONFUSIONS_OCR = [
    # « préparé par Île gouvernement », « dans Îles pays » (pas « la petite île de Guam »)
    (re.compile(r"(?<=[a-zéèàçâêîôû,] )Î(les?) (?!d[eu']|des |aux )(?=[a-zéèàç])"), r"\1 "),
    # « 11 faut », « 11s ont » en début de phrase (pas « 11 juin », « 11 heures »)
    (re.compile(rf"(?:(?<=^)|(?<=[.!?»«:] )|(?<=\n))11(s?) (?!{MOIS_UNITES})(?=[a-zéèàç])"), r"Il\1 "),
    # « Ja politique », « ia lutte » au milieu d'une phrase
    (re.compile(r"(?<=[a-zéèàç,] )(?:Ja|ia) (?=[a-zéèàç]{2})"), "la "),
]


def corriger_confusions_ocr(t):
    for regex, remplacement in CONFUSIONS_OCR:
        t = regex.sub(remplacement, t)
    return t


def nettoyer_en_ligne(b, vocab=None):
    b = b.replace("\u00ad", "")  # traits d'union conditionnels (« rou­lements »)
    if "~~" in b:  # suppressions des révisions Word (« ~~C~~’~~est en particulier l~~Le second degré »)
        b = re.sub(r"~~[^~\n]{0,200}?~~", "", b)
        b = re.sub(r"(^|\s)[’'](?=[A-ZÉÈÀ])", r"\1", b)
    b = R_ORNEMENT.sub(" ", b).strip()
    b = re.sub(r"^- \\?[-–—]\s+", "- ", b)  # « - \- Avec subordination »
    if len(b) < 500 and (R_MENTIONS.search(b) or re.search(r"(?:Site\s+web|e[.\-]?mail|courriel|Prenez\s+contact)", b, re.I)):
        b = re.sub(r"(?<!\\)\*+", "", b)  # bloc de coordonnées : emphases sans intérêt, qui gênent les retraits
    t = _retirer(b, R_MENTIONS)
    t = _retirer(t, R_ENTETE_PAGE)
    t = _retirer(t, R_SUITE)
    t = _retirer(t, R_NAV)
    t = _sans_bruit_ocr(t, vocab)
    t = corriger_confusions_ocr(t)
    t = R_LETTRINE.sub(r"\3\2", t)
    # emphases vidées par les retraits
    t = re.sub(r"(?<![\\*\w])(?:(\*{1,3})\s+\1|\*{4}(?:\*\*)?)(?![*\w])", " ", t)
    t = re.sub(r"(?<=[^\s*\\])(\*{1,3}) \1(?=[^\s*])", " ", t)  # « …deux* *candidats… » : une seule emphase
    # blanc laissé contre une marque d'emphase par un retrait (« *n° 53 * ») : emphase invalide
    t = re.sub(r"(?<=\S)\s+(\*{1,3})(?=\s|$)", r"\1", t)
    t = re.sub(r"(^|\s)(\*{1,3})\s+(?=\S)", r"\1\2", t)
    t = re.sub(r"[ \t]{2,}", " ", t).strip()
    if re.fullmatch(r"#{1,6}", t):
        return ""
    return t


# ------------------------------------------------------------------ blocs

def _brut(b):
    """Texte d'un bloc sans marques Markdown."""
    t = re.sub(r"^(#{1,6}\s+|>\s?|- )", "", b)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\\(.)", r"\1", t)
    return t.replace("*", "").strip()


CHAMPS = (r"(?:\b(?:NOM|PR[ÉE]NOM|ADRESSE|CODE\s+POST(?:AL|\.)|LOCALIT[ÉE]|VILLE|PROFESSION|T[ÉE]L[ÉE]PHONE|T[ÉE]L\."
          r"|E-?MAIL|COURRIEL|SIGNATURE)\b\s*[:;.]?|\b(?:ORGANISATION|SYNDICAT|ENTREPRISE|DATE)\s*:)")
R_CHAMPS = re.compile(CHAMPS, re.I)
R_ETIQUETTES = re.compile(r"\b(NOM|PR[ÉE]NOM|ADRESSE|CODE\s+POST|LOCALIT[ÉE]|VILLE|DATE)\b\s*[:;.]?", re.I)
# « NOM: …… PRENOM: …… » : les deux premiers champs suffisent quand l'OCR a défiguré les suivants
R_NOM_PRENOM = re.compile(r"\bNOM\s*[:;.…][^\n]{0,200}?\bPR[ÉE]NOM\s*[:;.…]")
R_BULLETIN = re.compile(r"\w{0,2}ULLETIN\s+D.\s?ABONNEMENT|BULLETIN\s+DE\s+(?:COMMANDE|SOUSCRIPTION)", re.I)
R_COUPON = re.compile(
    r"^\W*(?:Ch[èe]ques?\s+(?:[àa]\s+(?:établir|libeller)\s+)?(?:[àa]\s+)?l.\s?ordre\s+de"
    r"|Envoyer\s+[àa]\s*:|.{0,12}[ÉEŒ]crire\s+en\s+caract[èe]res?\s+d.imprimerie"
    r"|\d+\s+num[ée]ros?\s*:?\s*\d+|Abonnement\s+(?:de\s+soutien|ordinaire|normal|pour\s+\d+)"
    r"|Je\s+(?:m.abonne|souscris|d[ée]sire\s+(?:m.abonner|recevoir)))", re.I)
R_DEVISE = re.compile(r"on\s+ne\s+peut\s+aller\W{0,3}\s*de\s+l.\s?avant\s+si\s+l.\s?on\s+craint"
                      r"|(?:aller\s+de\s+\w?\W{0,2}\s?a\w{2}nt|craint\s+d\W{0,2}\s?aller)\b.{0,40}(?:social|L[ée]nine)", re.I)
R_BANDEAU = re.compile(
    r"^\W*(?:(?:BULLETIN\s+DU\s+)?(?:CO)?MIT[ÉE]\s+POUR|(?:CERCLE|GROUPE)\s+POUR|COMBATTRE\s+POUR(?:\s+LE\s+SOCIALISME)?"
    # titre du journal suivi de l'encadré du numéro, souvent illisible (« COMBATTRE POUR LE SOCIALISME | cPsn°88 »)
    r"|COMBATTRE\s+POUR\s+LE\s+SOCIA\w*(?:\s*\|[^\n]{0,30}|\s+C\W{0,2}P\W{0,2}S\W{0,3}\s*n\s?°\s*\d+)"
    r"|LE\s+SOCIALISME|L[ée]nine"
    r"|(?:NUM[ÉE]RO|N\s?°)\s*(?:SP[ÉE]CIAL\s*)?\d+[^\n]{0,40}"
    r"|Prix\s*:?\s*[\d,.]+\s*(?:€|euros?|F|FF|Fr|francs?)\b[^\n]{0,20})\W*$", re.I)
R_ORGANISATION = re.compile(
    r"^\W*(?:(?:BULLETIN\s+DU\s+)?(?:CO)?MIT[ÉE]\s+POUR|(?:POUR\s+)?LA\s+CONSTRUCTION|GROUPE\s+POUR|CERCLE\s+POUR)\b"
    r"[^\n]{0,200}?(?:INTERNATIONALE|PARTI\s+OUVRIER)", re.I)
R_TETE_CPS = re.compile(rf"^[^\n]{{0,6}}?(?:\d{{1,2}}\s?/\s?\d{{1,2}}\s?/\s?\d{{2,4}}\s+)?(?:Suppl[ée]ment\s+(?:[\w-]+\s+){{0,3}}(?:[àa]|au)\s+)?[«\"“\s]*(?:{CPS}|Socialisme\s+ou\s+Barbarie)[»\"”]?", re.I)
R_MOTS_ENTETE = re.compile(r"\b(?:nouvelle|ancienne)\s+s[ée]rie|sp[ée]cial|suppl[ée]ment|jeunes|cjr|n\s?°|num[ée]ro|page|p\.|\ble\b"
                           r"|\bau\b|\bdu\b|\bà\b|\bbis\b|\bter\b|\d+", re.I)
R_SOMMAIRE = re.compile(r"(?:\.{3,}|…+|(?:\.\s){3,})[\s,.]*(?:(?i:p)\s*[.,]?\s*|page\s*)?\d{1,2}(?=\s+[A-ZÉÈ«\"“*\\]|\s*$)")
# sommaire océrisé : les points de conduite sont lus comme des lettres (« … sesesesseeesnsens 28 »)
# renvoi de page d'un sommaire (« TITRE P.9 », « … p.19 - ») ; pas « P.5, et du P.C.F. » (P.S. mal lu)
R_RENVOI_PAGE = re.compile(r"(?:\.{2,}|…|[A-ZÉÈ»\"”]\s{0,3}|\s)[Pp]\s?[.,\-]\s?\d{1,2}(?![\d.,])")
R_SOMMAIRE_OCR = re.compile(r"(?:\.{3,}|…+)[^.…\d]{0,80}?(?:P\s*[.,]?\s*)?\b\d{1,2}(?=\s+[A-ZÉÈ«\"“*\\]|\s*$)")
R_CONTACT = re.compile(r"(?:https?\s?:\s?//|www\.)?socialisme\.\s?free\.\s?fr/?(?![\w/])|socialisme@free(?:\.fr)?|mailto:\S+"
                       r"|\bA\.?\s?E\.?\s?P\.?\s?S\b\.?|(?:\d+|\bI)\s*(?:bis|ter)?\s*,?\s*rue\s+Gutenberg|\b9\d\s?\d{3}\s+Montreuil"
                       r"|Site\s+(?:web|internet)\s*:?"
                       r"|Prenez\s+contact|Rejoignez[- ]nous|abonnez[- ]vous|Discutons[- ]en", re.I)
SEPARATEURS = {"(...)", "(…)", "[...]", "[…]", "\\[...\\]", "\\[…\\]", "…", "..."}
R_FILET = re.compile(r"^(?:[-*_](?:\s?[-*_]){2,}|(?:\\\*\s?){3,})$")  # « *** », « ----- » : séparateurs


def _vide(b):
    return "![" not in b and not re.search(r"[^\W_]", _brut(b))


def _est_bulletin(b):
    return bool(R_BULLETIN.search(b)) and len(b) < 400


R_COUPON_PARTOUT = re.compile(r"Envoyer\s+[àa]\s*:|Ch[èe]ques?\s+(?:[àa]\s+(?:établir|libeller)\s+)?(?:[àa]\s+)?"
                              r"l.\s?ordre\s+de\s*:|[ÉEŒ]crire\s+en\s+caract[èe]res?\s+d.imprimerie", re.I)


R_PUBLICITE = re.compile(r"brochures?\b.{0,120}?(?:franco|\d+\s*(?:F|FF|Fr|francs?|€|euros?)\b)", re.I | re.S)


def _est_champs(b):
    """Bloc de champs à remplir (« NOM :…… PRÉNOM :…… »), ligne du bulletin ou annonce
    de brochure (« La brochure : 14 F franco de port »)."""
    t = _brut(b)
    if R_PUBLICITE.search(t) and len(t) < 400:
        return True
    if (R_COUPON.search(t) or R_COUPON_PARTOUT.search(t)) and len(t) < 300:
        return True
    if not R_CHAMPS.search(t):
        return False
    reste = R_CHAMPS.sub(" ", t)
    reste = re.sub(r"\(?\s*[ÉEŒ]crire\s+en\s+caract[èe]res?\s+d.imprimerie\W*(?:Merci\W*)?", " ", reste, flags=re.I)
    reste = re.sub(r"[.…_\-–—:\s]+", " ", reste)
    return len(re.findall(r"[^\W\d_]", reste)) < 15 and len(t) < 300


def _debut_champs(t):
    """Position du premier champ d'une suite d'au moins trois champs du bulletin
    (« NOM: … PRENOM: … ADRESSE; … », même noyés dans des taches d'OCR), ou None."""
    etiq = list(R_ETIQUETTES.finditer(t))
    for k, m in enumerate(etiq):
        suite = {re.sub(r"\W", "", e.group(1)).upper().replace("É", "E") for e in etiq[k:k + 5]
                 if e.start() - m.start() < 400}
        if len(suite) >= 3 and len(t) - m.start() < 700:
            return m.start()
    m = R_NOM_PRENOM.search(t)
    if m and len(t) - m.start() < 700:
        return m.start()
    return None


def _est_sommaire(b):
    t = _brut(b)
    n = len(R_SOMMAIRE.findall(t))
    if re.fullmatch(r"\W*sommaire\W*", t, re.I):
        return True
    if n >= 2 or (n == 1 and len(t) < 150 and re.search(r"(?:\.{4,}|…{2,}|(?:\.\s){3,})\s*(?:P\s*[.,]?\s*)?\d{1,2}\s*$", t)):
        return True
    n_ocr = len(R_SOMMAIRE_OCR.findall(t))
    if n_ocr >= 2 and n_ocr >= len(t) / 250 or (n_ocr == 1 and len(t) < 200 and re.search(r"\b\d{1,2}\s*$", t)):
        return True
    # entrées « TITRE P.9 TITRE P.15 … » ou « … p.19 »
    renvois = len(R_RENVOI_PAGE.findall(t))
    if renvois >= 3 and renvois >= len(t) / 200:
        return True
    return len(t) < 200 and bool(re.search(r"(?:^|\s|\.)[Pp]\s?[.,]\s?\d{1,2}\s*$", t)) and not re.search(r"\(\s*p\.", t)


def _avant_sommaire(b):
    """Bloc sans le sommaire imprimé qu'il contient : tout le bloc s'il n'est qu'un sommaire
    (renvoie ''), sinon le texte qui précède un sommaire collé en fin de bloc par l'OCR."""
    if not _est_sommaire(b):
        return b
    if len(b) < 600:
        return ""
    t = b
    reperes = [m.start() for r in (R_SOMMAIRE, R_SOMMAIRE_OCR, R_RENVOI_PAGE) for m in r.finditer(t)]
    if not reperes:
        return ""
    p = min(reperes)
    m = R_MENTIONS.search(t[:p])  # les mentions légales précèdent le sommaire en dernière page
    if m:
        coupe = m.start()
    else:
        fins = [f.end() for f in re.finditer(r"[.!?»]\s+(?=[A-ZÉÈÀ«\"“])", t[:p])]
        coupe = fins[-1] if fins else 0
    reste = t[coupe:]
    if len(re.findall(r"[^\W\d_]", t[:coupe])) < 40:
        return ""
    if len(reperes) < (2 if len(reste) < 800 else 3):
        return b
    return t[:coupe].rstrip()


def _est_contact(b):
    """Pied de page ou encadré de contact réduit à des coordonnées ; reste de navigation
    (« Haut », « Début » : liens de retour en haut de page dont le lien a été retiré)."""
    t = _brut(b)
    if re.fullmatch(r"\W*(?:Haut(?:\s+de\s+(?:la\s+)?page)?|D[ée]but|Retour)\W*", t, re.I):
        return True
    if not R_CONTACT.search(b):
        return False
    reste = R_CONTACT.sub(" ", t)
    reste = re.sub(r"https?\s?:\s?//\S+|\S+@\S+|(?:Instagram|Facebook|Twitter|Telegram|TikTok)\s*:?\s*\S+", " ", reste)
    return len(re.findall(r"[^\W\d_]", reste)) < 4


def _est_entete_seul(t):
    """En-tête courant ou mention de supplément seuls dans un bloc
    (« C.P.S. N° 37 - 18 avril 1991 », « Supplément à CPS n°62 – 10 octobre 2016 »)."""
    if re.fullmatch(r"\W*Suppl[ée]ment\s+(?:[àa]|au)\W*", t, re.I):
        return True  # « Supplément à » resté seul (fin du bandeau sur un autre bloc)
    m = R_TETE_CPS.match(t)
    if not m or len(t) > 140:
        return False
    reste = R_MOTS_ENTETE.sub(" ", re.sub(DATE, " ", t[m.end():], flags=re.I))
    return len(re.findall(r"[^\W\d_]", reste)) < 3


MOTS_BANDEAU = ("comite", "pour", "construction", "parti", "ouvrier", "revolutionnaire", "reconstruction",
                "internationale", "ouvriere", "ive", "bulletin", "cercle", "groupe", "combattre", "socialisme",
                "redressement", "politique", "organisationnel", "pci")


def _proche(a, b):
    """a et b à au plus une lettre près (substitution, ajout ou retrait)."""
    if abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]


def _fragment_bandeau(t):
    """Morceau du bandeau « Comité pour la construction du parti ouvrier révolutionnaire… »
    coupé ou déformé par l'OCR (« IE POUR LA CONSTRUCTION », « DU PART », « COMBATTF LE SOCIALISME »)."""
    from localiser import jetons
    if re.search(r"\b(?:d[ée]claration|appel|communiqu[ée]|r[ée]solution|adresse|motion|lettre|rapport|tract)",
                 t, re.I):
        return False  # « DÉCLARATION DU COMITÉ POUR LA CONSTRUCTION… » : titre d'un texte
    js = [j for j in jetons(t) if len(j) > 2]
    bons = sum(1 for j in js if any(m == j or (len(j) >= 4 and (m.startswith(j) or m.endswith(j)))
                                    or (len(j) >= 5 and (_proche(j, m) or _proche(j, m[:len(j)]))) for m in MOTS_BANDEAU))
    return bool(js) and (bons == len(js) or (bons >= 4 and bons >= 0.8 * len(js)))


def est_bandeau_supplement(b):
    """Bandeau d'un supplément ou d'un tract reproduit dans un numéro (« GROUPE pour la
    construction du Parti ouvrier révolutionnaire… », « Supplément à CPS n°74 – 15 novembre
    2019 », devise) : il appartient au texte qui suit."""
    t = _brut(b)
    return len(t) <= 260 and bool(R_ORGANISATION.match(t) or (R_DEVISE.search(t) and len(t) < 160)
                                  or _est_entete_seul(t))


def commence_par_bandeau(md):
    """Le texte s'ouvre-t-il sur le bandeau d'un supplément ou d'un tract reproduit dans un
    numéro (« GROUPE pour la construction du Parti… ») ? Il se nettoie alors comme un début
    de document."""
    premier = _brut(next((b for b in md.split("\n\n") if b.strip()), ""))
    return len(premier) <= 260 and bool(R_ORGANISATION.match(premier))


def _est_bandeau(b, zone):
    t = _brut(b)
    if len(t) > 260:
        return False
    if R_DEVISE.search(t) and len(t) < 160:
        return True
    if _est_entete_seul(t):
        return True
    if not zone:
        return False
    if R_BANDEAU.match(t) or R_ORGANISATION.match(t) or (len(t) < 120 and _fragment_bandeau(t)):
        return True
    # date, coordonnées, numéro ou prix seuls en tête de document (« C.P.8. N°74 (10 F) »)
    reste = re.sub(DATE, " ", R_CONTACT.sub(" ", t), flags=re.I)
    lettres = len(re.findall(r"[^\W\d_]", reste))
    return lettres < 3 or (len(t) < 40 and lettres <= 6 and bool(re.search(r"\d", t)))


MOTS_SEULS = {"a", "à", "y", "ô", "o", "ou", "et", "non", "oui", "si", "ni", "or", "eh", "ah", "oh", "etc", "bis", "fin"}


def _monotone(b):
    """Tache d'OCR faite de quelques lettres répétées (« AAA TT ATTAATTT TTTATA »)."""
    lettres = [c.lower() for c in _brut(b) if c.isalpha()]
    return len(lettres) >= 15 and len(set(lettres)) <= 5


def _est_debris(b):
    """Paragraphe d'une à trois lettres qui n'est pas un mot (« he », « Re ») : tache lue par l'OCR."""
    if b.startswith(("#", "- ", ">", "[^", "|", "!")) or b.strip() in SEPARATEURS or R_FILET.match(b):
        return False
    t = _brut(b).strip()
    lettres = re.findall(r"[^\W\d_]", t)
    if not 0 < len(lettres) <= 3 or re.search(r"\d", t):
        return False
    if re.fullmatch(r"[IVX]{1,4}\s*[.)\-–]?|[A-Za-z]\s*[.)]", t):
        return False  # numéro de partie (« II », « B. », « a) »)
    return t.strip(" .,;:!?«»\"()").lower() not in MOTS_SEULS


# ------------------------------------------------------------ intertitres

FONCTION = {"de", "du", "des", "la", "le", "les", "l", "d", "à", "au", "aux", "et", "ou", "pour", "contre", "par",
            "sur", "dans", "en", "avec", "sans", "un", "une", "que", "qui", "son", "sa", "ses", "leur", "leurs",
            "ce", "cette", "ces", "est", "sont", "entre", "vers", "chez", "comme", "dont", "ne", "se", "sous",
            "mais", "donc", "ni", "car", "notre", "nos", "votre", "vos", "leurs", "d'un", "d'une"}


def niveau(b):
    m = re.match(r"^(#{1,6})\s", b)
    return len(m.group(1)) if m else 0


def texte_titre(b):
    return re.sub(r"^#{1,6}\s+", "", b).strip()


def _nb_mots(t):
    return len(re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", _brut(t)))


def _majuscules(t):
    lettres = [c for c in t if c.isalpha()]
    return len(lettres) >= 4 and sum(c.isupper() for c in lettres) >= 0.85 * len(lettres)


def _a_suivre(t1, t2, minuscules=True):
    """Le second intertitre continue-t-il le premier ? (minuscules : une initiale minuscule
    signale une suite, sauf dans les textes dont les intertitres sont en minuscules)"""
    a = _brut(t1).rstrip()
    b = _brut(t2).lstrip(" «\"“(")
    if not a or not b:
        return False
    if a.endswith("-") and b[:1].isalpha():
        return True
    if b[:1].islower() and minuscules:
        return True
    if re.match(r"(?:\.\.\.|…)", b) and re.search(r"(?:\.\.\.|…)$", a):
        return True  # « D'importants acquis politiques... » + « ... et organisationnels »
    if re.search(r"[.!?:;»)\]]$", a):
        return False
    dernier = re.findall(r"[^\W\d_]+$", a)
    return bool(dernier) and dernier[0].lower() in FONCTION


def _joindre_titres(t1, t2, vocab):
    if t1.endswith("-") and re.match(r"[^\W\d_]", t2):
        sep = vocab.recoller(t1, t2) if vocab is not None else ""
        return t1[:-1] + sep + t2
    return t1 + " " + t2


R_DATE_SEULE = re.compile(rf"^\W*(?:(?:le|fait\s+le|paris,?\s+le)\s+)?{DATE}\W*$", re.I)
R_PARU = re.compile(r"^\W*(?:Article|Texte|D[ée]claration|Tract|[ÉE]ditorial|Interview|Interventions?)\s+"
                    r"(?:paru|publi[ée]e?s?|diffus[ée]e?|du\s+bulletin)\s", re.I)


def _illisible(t, vocab):
    if vocab is None:
        return False
    ms = [m for m in mots(_brut(t)) if len(m) >= 2]
    if len(ms) < 3:
        return False
    connus = sum(1 for m in ms if vocab.freq[m.lower()] >= 5)
    return connus / len(ms) < 0.34


def _faux_titre(t):
    """Paragraphe, chapeau ou motion pris pour un intertitre."""
    brut = _brut(t)
    n = _nb_mots(brut)
    if n >= 30:
        return True
    if n >= 15 and re.search(r"[^\W\d_]{2,}[»”\"]?\s*\.$", brut):
        return True  # phrase complète terminée par un point
    return n >= 15 and bool(re.search(r"[a-zéèàç]{2,}[.!?]\s+[A-ZÉÈÀ][a-zéèàç]", brut))


LETTRES_INITIALES = "ABCDEFGHIJLMNOPQRSTUVÉÀÇ"


def _lettrine_perdue(b, vocab):
    """« es projets de loi » (lettrine non lue par l'OCR) → « Les projets de loi »."""
    m = re.match(r"([a-zéèàçâêîôûœ]+)(?=\s|$)", b)
    if not m or vocab is None:
        return b
    w = m.group(1)
    suite = re.match(r"[\s’']*([^\W\d_]+)", b[m.end():])
    suivant = suite.group(1).lower() if suite else None

    def score(mot):
        cap = mot[:1].upper() + mot[1:]
        return (vocab.debuts2[(cap, suivant)] if suivant else 0, vocab.debuts[cap])

    meilleur, s_meilleur = None, (0, 0)
    for L in LETTRES_INITIALES:
        c = L.lower() + w
        s = score(c)
        if s > s_meilleur:
            meilleur, s_meilleur = c, s
    if meilleur is None:
        return b
    s_orig = score(w)
    inconnu = vocab.freq[w] < 3 or (len(w) == 1 and w not in "aàyô")
    if suite and suite.group(1)[:1].isupper() and s_meilleur[0] < 5:
        return b  # « e Une intervention… » : puce lue « e », pas une lettrine
    if (inconnu and (s_meilleur[0] >= 2 or s_meilleur[1] >= 20)) or \
            (s_meilleur[0] >= 5 and s_meilleur[0] >= 10 * max(s_orig[0], 1) and s_meilleur[1] >= 5 * max(s_orig[1], 1)):
        return meilleur[:1].upper() + meilleur[1:] + b[m.end():]
    return b


# ------------------------------------------------------------------ principal

def nettoyer(md, vocab=None, debut_document=False, article=False, titre=None, recoudre=True):
    """Markdown nettoyé (voir le docstring du module).

    debut_document : le texte commence au début d'une publication ou d'un document
                     (bandeau de une cherché dans les premiers blocs) ;
    article        : texte d'un article entier (règles sur la hiérarchie des titres
                     et les faux intertitres) ; titre = titre de l'article (protégé) ;
    recoudre       : recoller les paragraphes coupés (PDF, OCR), pas pour le HTML dont les
                     paragraphes sont sûrs."""
    md = md.replace("\r", "")
    # un intertitre forme toujours un bloc à lui seul
    md = re.sub(r"\n(?=#{1,6} )", "\n\n", md)
    md = re.sub(r"^(#{1,6} [^\n]*)\n(?=[^\n])", r"\1\n\n", md, flags=re.M)
    corps, notes = [], []
    for b in md.split("\n\n"):
        b = b.strip()
        if not b:
            continue
        (notes if b.startswith("[^") and re.match(r"\[\^\w+\]:", b) else corps).append(b)

    # 1. retraits en ligne et blocs de bruit (None : bloc retiré, pour ne pas recoller
    #    deux intertitres qu'il séparait)
    blocs, coupon = [], False
    for k, b in enumerate(corps):
        if b in SEPARATEURS or R_FILET.match(b):
            blocs.append(b)
            continue
        b = _avant_sommaire(b)
        if not b:
            blocs.append(None)
            continue
        m = R_BULLETIN.search(b)
        if m and len(b) >= 400 and len(b) - m.start() < 600:
            b = b[:m.start()].rstrip()  # bulletin collé à la fin d'un paragraphe (OCR)
            coupon = True
        i = _debut_champs(_brut(b))
        if i is not None:
            coupon = True
            avant = _brut(b)[:i]
            if len(re.findall(r"[^\W\d_]", avant)) < 40:
                blocs.append(None)
                continue
            b = b[:b.find(avant[-20:]) + len(avant[-20:])].rstrip() if avant[-20:] in b else avant.rstrip()
        b = nettoyer_en_ligne(b, vocab)
        if not b or _vide(b):
            blocs.append(None)
            continue
        if _est_bulletin(b):
            coupon = True
            blocs.append(None)
            continue
        if _est_champs(b) or (coupon and len(_brut(b)) < 200 and (R_CHAMPS.search(b) or re.search(
                r"\d+\s*(?:F|FF|Fr|francs?|€|euros?)\b|soutien|r[èe]glement", b, re.I))):
            blocs.append(None)
            continue
        coupon = False
        if _est_sommaire(b) or _est_contact(b) or _est_bandeau(b, debut_document and k < 8) or _est_debris(b) \
                or _monotone(b):
            blocs.append(None)
            continue
        blocs.append(b)

    # 2. intertitres ; certains textes HTML ont des intertitres en minuscules (mis en
    #    capitales par la feuille de style) : l'initiale minuscule n'y signale pas une suite
    minuscules = not any(niveau(b) and _brut(texte_titre(b))[:1].islower() and k and blocs[k - 1]
                         and not niveau(blocs[k - 1]) for k, b in enumerate(blocs) if b)
    res, contigu = [], False
    for b in blocs:
        if b is None:
            contigu = False
            continue
        puce = re.match(r"^(?:#{1,6}\s+)?[·•●▪◆♦➢►✓]\s+(?=\S)", b)
        if puce:
            b = "- " + b[puce.end():]  # « ## · Assez de journées d'action ! » : élément de liste
        n = niveau(b)
        if n:
            t = re.sub(r"^(?:[a-zé]\s+|[|!\\]+\s*)+(?=[A-ZÉÈÀ«\"“(\d])", "", texte_titre(b))
            if _vide(t) or _illisible(t, vocab):
                contigu = False
                continue
            if R_DATE_SEULE.match(_brut(t)) or R_PARU.match(_brut(t)):
                res.append(t[:1].upper() + t[1:])  # date, source : du texte, pas un intertitre
            elif contigu and niveau(res[-1]) == n and _a_suivre(texte_titre(res[-1]), t, minuscules):
                res[-1] = "#" * n + " " + _joindre_titres(texte_titre(res[-1]), t, vocab)
            else:
                res.append("#" * n + " " + t)
            contigu = True
            continue
        if b[:1].islower() and R_PARU.match(b):
            b = b[:1].upper() + b[1:]
        if b[:1].islower() and res and niveau(res[-1]) and contigu:
            b = _lettrine_perdue(b, vocab)
        res.append(b)
        contigu = True

    sortie = "\n\n".join(res)
    if recoudre:
        sortie = fusionner_paragraphes(sortie, vocab)
    if article:
        sortie = "\n\n".join(_hierarchie(_sans_sommaire_html(sortie.split("\n\n")), titre))
    if notes:
        sortie += "\n\n" + "\n\n".join(notes)
    return nettoyer_markdown(_equilibrer(sortie)) if sortie.strip() else ""


def _sans_sommaire_html(blocs):
    """Sommaire en tête d'un article HTML (liste des intertitres qui suivent, liens vers les
    ancres « _Toc ») : retiré, il double les intertitres."""
    from localiser import jetons

    def norm(b):
        return " ".join(jetons(_brut(texte_titre(b))))
    titres = {}
    for k, b in enumerate(blocs):
        if niveau(b) and norm(b):
            titres.setdefault(norm(b), []).append(k)
    doublons = {k for k, b in enumerate(blocs)
                if not niveau(b) and len(b) < 250 and any(p > k for p in titres.get(norm(b), []))}
    return [b for k, b in enumerate(blocs) if k not in doublons] if len(doublons) >= 2 else blocs


def _correspond(t, titre):
    from localiser import jetons, jetons_titre
    tt = set(jetons_titre(titre, n=12))
    if not tt:
        return False
    return len(tt & set(jetons(t))) / len(tt) >= 0.6


def _hierarchie(blocs, titre):
    """Titre d'article en « ## » ; faux intertitres rendus au texte ; intertitres du corps
    décalés d'un niveau quand ils emploient « ## »."""
    res = []
    for i, b in enumerate(blocs):
        n = niveau(b)
        if n and _faux_titre(texte_titre(b)) and not (titre and i < 4 and _correspond(texte_titre(b), titre)):
            b = texte_titre(b)
        elif n and i + 1 < len(blocs) and not niveau(blocs[i + 1]) and blocs[i + 1][:1].islower() \
                and _nb_mots(b) >= 8 and not re.search(r"[.!?:»]\s*\**$", b) and not _majuscules(b):
            # début de phrase en gras dont la suite est en texte courant
            blocs[i + 1] = texte_titre(b) + " " + blocs[i + 1]
            continue
        res.append(b)
    # groupe de titre : intertitres en tête de l'article, éventuellement après une mention
    # de source, une date ou un chapeau, ou premier groupe qui reprend le titre de l'article
    j = 0
    while j < len(res) and not niveau(res[j]) and j < 3 and (
            R_PARU.match(_brut(res[j])) or R_DATE_SEULE.match(_brut(res[j])) or len(res[j]) < 100):
        j += 1
    if j < len(res) and not niveau(res[j]) and titre:
        k = next((k for k in range(j, min(j + 4, len(res))) if niveau(res[k])), None)
        if k is not None and _correspond(texte_titre(res[k]), titre):
            j = k
    i0 = j
    while i0 < len(res) and niveau(res[i0]):
        i0 += 1
    if i0 > j:
        res[j] = "## " + texte_titre(res[j])
        for k in range(j + 1, i0):
            if niveau(res[k]) < 2:
                res[k] = "## " + texte_titre(res[k])
    else:
        i0 = 0
    if any(0 < niveau(b) <= 2 for b in res[i0:]):
        for k in range(i0, len(res)):
            n = niveau(res[k])
            if n:
                res[k] = "#" * min(6, max(n, 2) + 1) + " " + texte_titre(res[k])
    return res
