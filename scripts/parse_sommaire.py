"""Analyse de sources/sommaire.html (page « Publications » de socialisme.free.fr).

La page est une longue suite de blocs <h4> mal fermés :

  <h4>JJ/MM/AAAA: CPS n°N (Nouvelle Série) <a href='…pdf'>PDF</a></h4>
  <ul><li>Titre d'article <a href='…htm'>HTML</a> <a href='…pdf'>PDF</a></li><li>…</ul>

  <h4>JJ/MM/AAAA: Supplément à CPS n°N (Nouvelle Série):<br/>Titre <a …>PDF</a></li></h4>

  <h4>JJ/MM/AAAA: CPS n°0<li>Titre d'un hors-série <a …>PDF</a></li></ul>

On découpe donc le texte brut sur « <h4> » plutôt que de faire confiance à
l'arbre HTML. Chaque bloc donne une « entrée » brute ; la normalisation
(fusion des doublons, séries, identifiants) est faite dans build_db.py.
"""
import html
import re
import urllib.parse

BASE = "http://socialisme.free.fr/"

HEAD_RE = re.compile(
    r"^\s*(?P<date>\d{2}/\d{2}/\d{4})\s*:\s*"
    r"(?P<supp>Suppl[ée]ment\s+à\s+)?CPS\s+n°\s*(?P<num>\d+)"
    r"\s*(?P<ns>\(\s*Nouvelle\s+S[ée]rie\s*\))?\s*:?\s*(?P<rest>.*)$",
    re.S,
)
LINK_RE = re.compile(r"<a\s+href\s*=\s*['\"]([^'\"]*)['\"][^>]*>(.*?)</a>", re.S | re.I)


def clean_text(fragment):
    """Texte lisible à partir d'un fragment HTML."""
    t = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    t = re.sub(r"<[^>]*>", " ", t)
    t = html.unescape(t)
    t = t.replace(" ", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_url(href):
    """URL absolue propre, ou None si le lien est vide / factice.

    Renvoie (url, desactive) : un lien préfixé par « # » sur le site est un
    lien neutralisé (fichier pas encore en ligne) ; on le garde, marqué.
    """
    h = html.unescape(href).strip()
    disabled = False
    if h.startswith("#"):
        h = h[1:].strip()
        disabled = True
    if h in ("", "X", "x", "#") or h.startswith("#"):
        return None, False
    if h.startswith("mailto:"):
        return None, False
    url = urllib.parse.urljoin(BASE, h)
    # « page13 » sans « = » : coquille fréquente du site
    url = re.sub(r"#page(\d+)$", r"#page=\1", url)
    url = url.replace(" ", "%20")
    return url, disabled


def extract_links(fragment):
    links = []
    for href, label in LINK_RE.findall(fragment):
        url, disabled = normalize_url(href)
        if url is None:
            continue
        links.append({"url": url, "label": clean_text(label), "desactive": disabled})
    return links


def split_title_and_links(fragment):
    """Sépare le titre (texte hors liens) des liens d'un item."""
    links = extract_links(fragment)
    title = clean_text(LINK_RE.sub(" ", fragment))
    return title, links


def parse(html_text):
    start = html_text.find("Toutes les Publications")
    body = html_text[start:]
    end = body.find("</body>")
    if end > 0:
        body = body[:end]
    blocks = re.split(r"(?=<h4>)", body)[1:]
    entries = []
    for pos, block in enumerate(blocks):
        block = block[len("<h4>"):]
        # en-tête : jusqu'au premier </h4>, <ul> ou <li>
        m = re.search(r"</h4>|<ul>|<li>", block, re.I)
        head = block[: m.start()] if m else block
        tail = block[m.start():] if m else ""
        hm = HEAD_RE.match(clean_text(re.sub(r"<a\s.*?</a>", " ", head, flags=re.S)) or "")
        if not hm:
            raise ValueError(f"en-tête non reconnu : {head[:200]!r}")
        head_links = extract_links(head)
        head_rest = hm.group("rest").strip()
        # dans un en-tête de supplément, le titre suit « :<br/> »
        if hm.group("supp"):
            after_br = re.split(r"<br\s*/?>", head, maxsplit=1, flags=re.I)
            title_html = after_br[1] if len(after_br) > 1 else ""
            head_rest, _ = split_title_and_links(title_html)
        items = []
        for li in re.split(r"<li>", tail, flags=re.I)[1:]:
            li = re.split(r"</li>|</ul>|</h4>", li, maxsplit=1, flags=re.I)[0]
            title, links = split_title_and_links(li)
            if not title and not links:
                continue
            items.append({"titre": title, "liens": links})
        d, mth, y = hm.group("date").split("/")
        entries.append({
            "position": pos,
            "date": f"{y}-{mth}-{d}",
            "supplement": bool(hm.group("supp")),
            "numero": int(hm.group("num")),
            "nouvelle_serie": bool(hm.group("ns")),
            "titre_entete": head_rest,
            "liens_entete": head_links,
            "items": items,
        })
    return entries


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "sources" / "sommaire.html"
    data = parse(src.read_text(encoding="utf-8"))
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
