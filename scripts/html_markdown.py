"""Conversion des pages HTML d'articles de socialisme.free.fr en Markdown.

Deux familles de pages :
  - exports Microsoft Word, avec la charte de CPS : styles « corps »,
    « intertitre » / « OInterCPS », « citation » / « OCitaCPS », « titre » /
    « OTitrarticles », sommaires « MsoToc », notes de bas de page Word ;
  - pages du gabarit Dreamweaver du site (bandeau, menus, colonne de navigation,
    pied de page), où le texte est dans une cellule de tableau.

Étapes : isoler le contenu, lire la feuille de style pour savoir quelles classes
sont en gras / en grande taille, normaliser la mise en forme (intertitres,
citations, listes, notes), puis convertir avec markdownify.

Conventions du Markdown produit (communes avec pdf_markdown.py) :
  « ## » titre affiché dans le document, « ### » intertitre, « > » citation,
  « - » liste, « [^n] » note. Pas de titre de niveau 1 : le titre de l'article
  est dans les métadonnées.
"""
import html as htmlmod
import re
import urllib.parse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from markdownify import MarkdownConverter

MENUS = ("Haut de la page", "Textes constitutifs", "Abonnement", "Sommaire de CPS")
PUCE = r"[·•▪§o\-–—]"


def decoder(data):
    m = re.search(rb"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", data[:4000])
    enc = m.group(1).decode() if m else None
    for e in [enc, "utf-8", "cp1252"]:
        if not e:
            continue
        try:
            return data.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("cp1252", "replace")


# ------------------------------------------------------------ styles CSS

def lire_css(soup):
    """Propriétés utiles des classes définies dans les <style> : {classe: {...}}."""
    classes = {}
    for st in soup.find_all("style"):
        css = re.sub(r"/\*.*?\*/", " ", st.get_text(), flags=re.S)
        for sel, decl in re.findall(r"([^{}]+)\{([^}]*)\}", css):
            d = decl.replace(" ", "").replace("\n", "").lower()
            props = {
                "gras": "font-weight:bold" in d or "font-weight:700" in d,
                "italique": "font-style:italic" in d,
                "taille": float(m.group(1)) if (m := re.search(r"font-size:([\d.]+)pt", d)) else None,
                "centre": "text-align:center" in d,
            }
            for cls in re.findall(r"\.([A-Za-z0-9_-]+)", sel):
                c = classes.setdefault(cls.lower(), {})
                for k, v in props.items():
                    if v:
                        c[k] = v
    return classes


def role_classe(nom, css):
    """Rôle éditorial d'un paragraphe d'après le nom de sa classe Word."""
    n = (nom or "").lower()
    if not n:
        return None
    if n.startswith("msotoc"):
        return "sommaire"
    if re.search(r"soustitr|sous-titr|subtitle", n):
        return "soustitre"
    if re.search(r"intertitr|ointer|^inter$", n):
        return "intertitre"
    if re.search(r"titr|title", n) and "notedebas" not in n:
        return "titre"
    if re.search(r"cita|quote|blocktext", n):
        return "citation"
    if re.search(r"listbullet|^msolist$|listparagraph", n):
        return "liste"
    props = css.get(n, {})
    if props.get("gras") and (props.get("taille") or 0) >= 14:
        return "titre"
    if props.get("gras"):
        return "gras"
    return None


# ------------------------------------------------------------- nettoyage

def _style(tag):
    return (tag.get("style") or "").replace(" ", "").lower()


def _texte(tag):
    return re.sub(r"\s+", " ", tag.get_text(" ")).strip()


def nettoyer(html):
    """(soupe, corps, css) : la soupe réduite au contenu de l'article."""
    html = re.sub(r"<!--\s*#BeginLibraryItem.*?<!--\s*#EndLibraryItem\s*-->", " ", html, flags=re.S)
    html = re.sub(r"<!--\s*phpmyvisites\s*-->.*?<!--\s*/phpmyvisites\s*-->", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!\[(?:if [^\]]*|endif)\]>", "", html)  # commentaires conditionnels Word
    soup = BeautifulSoup(html, "html.parser")
    css = lire_css(soup)
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in soup(["head", "script", "style", "form", "noscript", "object", "iframe", "meta", "link",
                   "title", "xml", "input", "button", "map"]):
        t.decompose()
    for t in soup.find_all(re.compile(r"^(v|w|o|st\d*):")):
        if t.name == "o:p":
            t.unwrap()
        else:
            t.decompose()
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if not src or re.search(r"(^|/)img/|entete|spacer|logo|phpmyvisites|\.gif$", src, re.I):
            img.decompose()
    for a in soup.find_all("a"):
        if _texte(a).startswith(MENUS):
            (a.find_parent(["div", "p", "td"]) or a).decompose()
    body = soup.body or soup
    # gabarit du site : le texte est dans la cellule (sans sous-tableau) la plus fournie
    cellules = [td for td in body.find_all("td") if not td.find("td")]
    if cellules:
        principale = max(cellules, key=lambda td: len(_texte(td)))
        if len(_texte(principale)) > 0.6 * len(_texte(body)):
            principale.name, principale.attrs = "div", {}
            body = principale
    return soup, body, css


# --------------------------------------------------------- normalisation

def _aplatir_espaces(body):
    """Le source Word coupe les lignes au milieu des phrases : on aplatit les blancs."""
    for s in list(body.find_all(string=True)):
        if s.find_parent("pre"):
            continue
        nouveau = re.sub(r"[ \t\r\n\f ]+", " ", str(s))
        if nouveau != str(s):
            s.replace_with(NavigableString(nouveau))


def _taille_de(s, body, css):
    for parent in s.parents:
        if parent is body or parent is None:
            break
        m = re.search(r"font-size:([\d.]+)pt", _style(parent))
        if m:
            return float(m.group(1))
        for c in parent.get("class") or []:
            t = css.get(c.lower(), {}).get("taille")
            if t:
                return t
    return None


def _tailles(body, css):
    """Taille de police dominante de chaque bloc (data-taille) ; renvoie celle du corps du texte."""
    compte = {}
    for p in body.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        if p.find(["p", "div", "table"]):
            continue
        tailles = {}
        for s in p.find_all(string=True):
            n = len(s.strip())
            if n:
                t = _taille_de(s, body, css)
                tailles[t] = tailles.get(t, 0) + n
        if tailles:
            t = max(tailles, key=tailles.get)
            if t:
                p["data-taille"] = str(t)
            compte[t] = compte.get(t, 0) + sum(tailles.values())
    connues = {t: n for t, n in compte.items() if t}
    return max(connues, key=connues.get) if connues else 12.0


def _sortir_br(soup, body):
    """Un saut de ligne à l'intérieur d'un gras/italique casse le Markdown : on coupe l'élément."""
    while True:
        br = next((b for b in body.find_all("br") if b.parent is not None and b.parent.name in ("b", "i")), None)
        if br is None:
            return
        parent = br.parent
        apres = soup.new_tag(parent.name)
        for sib in list(br.next_siblings):
            apres.append(sib.extract())
        br.extract()
        parent.insert_after(br)
        br.insert_after(apres)


def _gras_italique(soup, body, css):
    """Spans stylés (en ligne ou par classe) → b / i ; soulignement → gras."""
    for t in list(body.find_all(True)):
        if t.name in ("span", "font", "a"):
            props = {}
            for c in t.get("class") or []:
                props.update(css.get(c.lower(), {}))
            s = _style(t)
            gras = ("font-weight:bold" in s or "font-weight:700" in s or "arialblack" in s or "impact" in s
                    or (props.get("gras") and "font-weight:normal" not in s))
            ital = "font-style:italic" in s or (props.get("italique") and "font-style:normal" not in s)
            if t.name == "a":
                continue
            if not (gras or ital):
                t.unwrap()
                continue
            t.name, t.attrs = ("b" if gras else "i"), {}
            if gras and ital:
                inner = soup.new_tag("i")
                for c in list(t.contents):
                    inner.append(c.extract())
                t.append(inner)
        elif t.name in ("u", "strong"):
            t.name, t.attrs = "b", {}
        elif t.name == "em":
            t.name, t.attrs = "i", {}
        elif t.name in ("sup", "sub", "small", "big", "nobr") and not t.find("a"):
            t.unwrap()


def _fusionner_emphases(body):
    """Mise en forme Word fragmentée : on fusionne les b/i adjacents, on retire ceux
    qui sont vides ou ne portent que sur des blancs ou de la ponctuation."""
    change = True
    while change:
        change = False
        for el in list(body.find_all(["b", "i"])):
            if el.parent is None:
                continue
            if not re.search(r"\w", el.get_text()) and not el.find(["img", "a"]):
                el.unwrap()
                change = True
                continue
            if el.parent.name == el.name:  # <b><b>x</b></b>
                el.unwrap()
                change = True
                continue
            suivant = el.next_sibling
            entre = []
            while isinstance(suivant, NavigableString) and not str(suivant).strip():
                entre.append(suivant)
                suivant = suivant.next_sibling
            if isinstance(suivant, Tag) and suivant.name == el.name:
                for e in entre:
                    el.append(e.extract())
                for c in list(suivant.contents):
                    el.append(c.extract())
                suivant.decompose()
                change = True


def _bords_emphases(body):
    """Règles de CommonMark : un « * » collé à une lettre d'un côté et à de la
    ponctuation de l'autre ne s'ouvre ou ne se ferme pas. On sort de l'emphase la
    ponctuation de bord quand elle touche une lettre à l'extérieur."""
    def car_avant(el):
        s = el.find_previous(string=True)
        while s is not None and not str(s):
            s = s.find_previous(string=True)
        return str(s)[-1] if s else " "

    def car_apres(el):
        s = el.find_next(string=lambda x: x and not any(p is el for p in x.parents))
        while s is not None and not str(s):
            s = s.find_next(string=True)
        return str(s)[0] if s else " "

    for el in body.find_all(["b", "i"]):
        textes = [t for t in el.find_all(string=True) if str(t)]
        if not textes:
            continue
        premier, dernier = textes[0], textes[-1]
        # début : ponctuation intérieure précédée d'une lettre à l'extérieur
        m = re.match(r"^([^\w\s]+)", str(premier))
        if m and car_avant(el).isalnum():
            premier.replace_with(NavigableString(str(premier)[m.end():]))
            el.insert_before(NavigableString(m.group(1)))
            textes = [t for t in el.find_all(string=True) if str(t)]
            if not textes:
                el.unwrap()
                continue
            dernier = textes[-1]
        m = re.search(r"([^\w\s]+)$", str(dernier))
        if m and car_apres(el).isalnum():
            dernier.replace_with(NavigableString(str(dernier)[:m.start()]))
            el.insert_after(NavigableString(m.group(1)))


def _equilibrer(md):
    """Dernier filet : un paragraphe aux marqueurs d'emphase déséquilibrés perd son emphase."""
    sortie = []
    for para in md.split("\n\n"):
        sans_echap = para.replace("\\*", "")
        gras = sans_echap.count("**")
        simples = sans_echap.replace("**", "").count("*")
        if gras % 2 or simples % 2 or re.search(r"(?<!\\)\*{4,}", para):
            para = re.sub(r"(?<!\\)\*", "", para)
        sortie.append(para)
    return "\n\n".join(sortie)


def _notes(body):
    """Notes Word (#_ftnN / #_ednN) → [^N], et leurs définitions."""
    defs = []
    for div in body.find_all(["div", "p"], id=re.compile(r"^(ftn|edn)\d+$")):
        cle = div["id"].replace("ftn", "").replace("edn", "e")
        for a in div.find_all("a", href=re.compile(r"#_(ftn|edn)ref\d+")):
            a.decompose()
        defs.append((cle, div.extract()))
    for liste in body.find_all("div", style=re.compile(r"mso-element:\s*(footnote|endnote)-list", re.I)):
        liste.decompose()
    for a in body.find_all("a", href=re.compile(r"#_(ftn|edn)\d+$")):
        m = re.search(r"#_(ftn|edn)(\d+)$", a["href"])
        cle = m.group(2) if m.group(1) == "ftn" else "e" + m.group(2)
        a.replace_with(NavigableString(f"[^{cle}]"))
    return defs


def _dans_gras(s, p):
    for parent in s.parents:
        if parent is p:
            return False
        if parent.name == "b":
            return True
    return False


def _entierement_gras(p):
    tout = re.sub(r"\W+", "", p.get_text())
    gras = re.sub(r"\W+", "", "".join(s for s in p.find_all(string=True) if _dans_gras(s, p)))
    return bool(tout) and len(gras) >= 0.9 * len(tout)


def _roles(soup, body, css, corps=12.0):
    """Intertitres, titres, sous-titres, citations, sommaires, listes."""
    for p in list(body.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"])):
        if p.parent is None or p.find(["p", "div", "table"]):
            continue
        txt = _texte(p)
        if not txt:
            continue
        role = None
        for c in p.get("class") or []:
            role = role_classe(c, css) or role
        if p.name in ("h1", "h2"):
            role = "titre"
        elif p.name in ("h3", "h4", "h5", "h6"):
            role = "intertitre"
        taille = float(p.get("data-taille") or 0)
        if role in (None, "gras") and len(txt) <= 220 and not p.find_parent(["li", "table"]):
            if taille >= corps + 2:
                role = "titre"
            elif taille >= corps + 1.5 or _entierement_gras(p):
                role = "intertitre"
        if role in ("titre", "intertitre") and len(txt) > 300:
            role = "gras"  # paragraphe entier mis en relief plutôt qu'un titre
        if role in ("titre", "intertitre"):
            p.name, p.attrs = ("h2" if role == "titre" else "h3"), {}
            for em in p.find_all(["b", "i"]):  # un titre est déjà mis en relief
                em.unwrap()
        elif role == "soustitre":
            p.name, p.attrs = "p", {}
            b = soup.new_tag("b")
            for c in list(p.contents):
                b.append(c.extract())
            p.append(b)
        elif role == "citation":
            p.name, p.attrs = "p", {"data-citation": "1"}
        elif role in ("sommaire", "liste"):
            p.name, p.attrs = "li", {"data-puce": "1"}
            premier = next((s for s in p.find_all(string=True) if s.strip()), None)
            if premier is not None:
                premier.replace_with(NavigableString(re.sub(rf"^\s*{PUCE}\s+", "", str(premier), count=1)))
            if role == "sommaire":  # numéros de page des sommaires Word
                dernier = [s for s in p.find_all(string=True) if s.strip()]
                if dernier:
                    dernier[-1].replace_with(NavigableString(re.sub(r"[\s.…]*\d+\s*$", "", str(dernier[-1]))))
        elif p.name == "p":
            # listes à puces simulées
            texte = p.get_text().lstrip()
            if re.match(rf"^{PUCE}\s+\S", texte):
                premier = next((s for s in p.find_all(string=True) if s.strip()), None)
                premier.replace_with(NavigableString(re.sub(rf"^\s*{PUCE}\s+", "", str(premier), count=1)))
                p.name, p.attrs = "li", {"data-puce": "1"}
    # regrouper : li isolés → ul ; citations consécutives → blockquote
    for attr, nom in (("data-puce", "ul"), ("data-citation", "blockquote")):
        for el in body.find_all(attrs={attr: "1"}):
            if el.parent is None or el.parent.name == nom or (nom == "ul" and el.parent.name in ("ul", "ol")):
                continue
            conteneur = soup.new_tag(nom)
            el.insert_before(conteneur)
            courant = el
            while isinstance(courant, Tag) and courant.get(attr) == "1":
                suivant = courant.find_next_sibling()
                conteneur.append(courant.extract())
                courant = suivant
    for attr in ("data-puce", "data-taille"):
        for el in body.find_all(attrs={attr: True}):
            del el[attr]
    for el in body.find_all(attrs={"data-citation": True}):
        del el["data-citation"]


def _tableaux(body):
    """Tableaux de mise en page (cellules longues, une colonne) → contenu à plat."""
    for table in list(body.find_all("table"))[::-1]:
        lignes = table.find_all("tr")
        cellules = [len(tr.find_all(["td", "th"], recursive=False)) for tr in lignes]
        longues = any(len(_texte(c)) > 250 for c in table.find_all(["td", "th"]))
        donnees = len(lignes) >= 2 and max(cellules or [0]) >= 2 and not longues and not table.find("table")
        if not donnees:
            for c in table.find_all(["td", "th"]):
                c.name, c.attrs = "div", {}
            for t in table.find_all(["tr", "tbody", "thead", "tfoot", "caption", "colgroup", "col"]):
                t.unwrap()
            table.name, table.attrs = "div", {}
        else:
            for c in table.find_all(["td", "th"]):  # pas de paragraphes dans une cellule
                for blk in c.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
                    blk.unwrap()


# ------------------------------------------------------------ conversion

class _Convertisseur(MarkdownConverter):
    def convert_img(self, el, text, parent_tags=None, **kw):
        src = el.get("src") or ""
        alt = re.sub(r"\s+", " ", el.get("alt") or "").strip()
        return f"![{alt}]({urllib.parse.urljoin(self.options['base_url'], src)})" if src else ""

    def convert_a(self, el, text, parent_tags=None, **kw):
        href = (el.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:")) or not text.strip():
            return text
        href = urllib.parse.urljoin(self.options["base_url"], href).replace(" ", "%20")
        return f"[{text.strip()}]({href})"


def _convertir(soup_el, url):
    conv = _Convertisseur(heading_style="ATX", bullets="-", strong_em_symbol="*", base_url=url,
                          escape_underscores=False, escape_misc=False, newline_style="backslash",
                          table_infer_header=True)
    return conv.convert_soup(soup_el)


def html_vers_markdown(data, url):
    """Markdown du contenu d'une page d'article (octets HTML)."""
    soup, body, css = nettoyer(decoder(data))
    _aplatir_espaces(body)
    corps = _tailles(body, css)
    _gras_italique(soup, body, css)
    _sortir_br(soup, body)
    _fusionner_emphases(body)
    _bords_emphases(body)
    _fusionner_emphases(body)
    defs = _notes(body)
    _tableaux(body)
    _roles(soup, body, css, corps)
    md = _convertir(body, url)
    if defs:
        notes = []
        for cle, d in defs:
            _aplatir_espaces(d)
            _gras_italique(soup, d, css)
            _fusionner_emphases(d)
            notes.append(f"[^{cle}]: " + re.sub(r"\s*\n\s*", " ", _convertir(d, url)).strip())
        md += "\n\n" + "\n\n".join(notes)
    return nettoyer_markdown(_equilibrer(nettoyer_markdown(md)))


def nettoyer_markdown(md):
    md = md.replace(" ", " ").replace("\r", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"(\\\n\s*){2,}", "\n\n", md)            # sauts de ligne forcés répétés
    md = re.sub(r"\\\n(\s*\n)", r"\1", md)               # saut forcé en fin de paragraphe
    md = re.sub(r"^(#+ .*?)\s*\\$", r"\1", md, flags=re.M)
    md = re.sub(r"^#+\s*$", "", md, flags=re.M)          # titres vides
    md = re.sub(r"^>\s*$\n(?=>\s*$)", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    lignes = [l.rstrip() for l in md.split("\n")]
    return "\n".join(lignes).strip() + "\n"


def markdown_vers_texte(md):
    """Texte brut lisible à partir du Markdown produit par ce projet."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"\[([^\]^][^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t, flags=re.S)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"\1", t, flags=re.S)
    t = re.sub(r"\\\n", "\n", t)
    t = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>|])", r"\1", t)
    t = re.sub(r"^>\s?", "", t, flags=re.M)
    t = re.sub(r"\[\^(\w+)\]", r"[\1]", t)
    return htmlmod.unescape(re.sub(r"\n{3,}", "\n\n", t)).strip()
