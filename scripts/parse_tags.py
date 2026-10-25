"""Analyse de l'index thématique de socialisme.free.fr.

- sources/index_thematique.html : liste des tags, regroupés en catégories
  (Rubriques, France, Partis et syndicats en France, Théorie, International).
- sources/tags/tag_<slug>.html : pour chaque tag, une suite de paragraphes
  <p><em>JJ/MM/AAAA: </em>Titre <a …>HTML</a> <a …>PDF</a> <a …>CPS n°N Nlle Série</a></p>
"""
import re
import urllib.parse
from pathlib import Path

from parse_sommaire import LINK_RE, clean_text, normalize_url

ISSUE_LABEL_RE = re.compile(r"^CPS\s+n°\s*(\d+)\s*(Nlle\s+S[ée]rie)?\s*$", re.I)


def parse_index(html_text):
    """Renvoie la liste ordonnée des tags : {slug, libelle, categorie}."""
    tags = []
    seen = set()
    # on parcourt les <h4> de catégorie et les liens qui les suivent
    pattern = re.compile(r"<h4>(.*?)</h4>|<a href=\"\./recherchethem\.php\?tag=([^\"]+)\">(.*?)</a>", re.S)
    category = None
    for m in pattern.finditer(html_text):
        if m.group(1) is not None:
            category = clean_text(m.group(1)).rstrip(":").strip()
            continue
        slug, label = m.group(2), clean_text(m.group(3))
        if slug == "null" or slug in seen:
            continue
        seen.add(slug)
        tags.append({"slug": slug, "libelle": label, "categorie": category})
    return tags


def parse_tag_page(html_text):
    start = html_text.find("<h3>Articles</h3>")
    end = html_text.find("<h3>Liste des tags")
    body = html_text[start:end if end > 0 else None]
    entries = []
    for p in re.findall(r"<p>(.*?)</p>", body, re.S):
        dm = re.search(r"<em>\s*(\d{2})/(\d{2})/(\d{4})\s*:?\s*</em>", p)
        date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else None
        rest = p[dm.end():] if dm else p
        links, issue = [], None
        for href, label in LINK_RE.findall(rest):
            label_t = clean_text(label)
            im = ISSUE_LABEL_RE.match(label_t)
            url, disabled = normalize_url(href)
            if im:
                issue = {"numero": int(im.group(1)), "nouvelle_serie": bool(im.group(2)), "url": url}
            elif url:
                links.append({"url": url, "label": label_t, "desactive": disabled})
        title = clean_text(LINK_RE.sub(" ", rest))
        # les suppléments n'ont pas de <em> : leur date préfixe le titre
        sm = re.match(r"^Suppl[ée]ment\s+(\d{2})/(\d{2})/(\d{4})\s*:\s*", title)
        supplement = bool(sm)
        if sm:
            date = date or f"{sm.group(3)}-{sm.group(2)}-{sm.group(1)}"
            title = title[sm.end():]
        entries.append({"date": date, "titre": title, "liens": links, "numero": issue, "supplement": supplement})
    return entries


def tag_filename(slug):
    return "tag_" + urllib.parse.quote(slug, safe="") + ".html"


def load_all(sources_dir):
    sources_dir = Path(sources_dir)
    tags = parse_index((sources_dir / "index_thematique.html").read_text(encoding="utf-8"))
    pages = {}
    for t in tags:
        f = sources_dir / "tags" / tag_filename(t["slug"])
        if f.exists():
            pages[t["slug"]] = parse_tag_page(f.read_text(encoding="utf-8", errors="replace"))
    return tags, pages
