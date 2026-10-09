#!/usr/bin/env python3
"""Construit la base de données « Combattre pour le socialisme ».

Entrées :
  sources/sommaire.html, sources/index_thematique.html, sources/tags/*.html
  config/corrections.json   corrections manuelles justifiées
  config/regles_tags.json   règles de tags complémentaires (sur les titres)
  data/textes/<id>.txt      textes intégraux éventuels (voir fetch_textes.py)

Sorties :
  data/cps.sqlite           base SQLite (tables + vues + recherche plein texte)
  data/csv/*.csv            mêmes tables au format CSV (UTF-8)
  data/cps.json             export hiérarchique publications → articles → tags
  docs/RAPPORT_QUALITE.md   anomalies détectées et statistiques

Usage : python3 scripts/build_db.py
"""
import csv
import difflib
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import localiser  # noqa: E402
import parse_sommaire  # noqa: E402
import parse_tags  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"
CONFIG = ROOT / "config"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

SERIES = {
    "bulletin1984": {"prefixe": "B84", "libelle": "Bulletin 1984 (avant l'ancienne série)"},
    "ancienne": {"prefixe": "AS", "libelle": "Ancienne série (1985-2000)"},
    "nouvelle": {"prefixe": "NS", "libelle": "Nouvelle série (depuis novembre 2000)"},
}
# n° cumulé : la nouvelle série reprend la numérotation après les 82 numéros
# de l'ancienne (ex. « N°98 (N°180) », fichiers « …_180as.pdf »).
DECALAGE_NOUVELLE_SERIE = 82


# ---------------------------------------------------------------- utilitaires

def norm(s):
    """Forme normalisée d'un titre pour les comparaisons."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("œ", "oe").replace("æ", "ae")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def url_sans_ancre(url):
    return url.split("#", 1)[0] if url else url


def page_pdf(url):
    m = re.search(r"#page=(\d+)", url or "")
    return int(m.group(1)) if m else None


def date_depuis_fichier(url):
    """Date AAAA-MM-JJ lue dans un nom de fichier « AAAA_MM_JJ_… » (JJ=00 accepté)."""
    m = re.search(r"/(\d{4})_(\d{2})_(\d{2})_", url or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def ecart_jours(d1, d2):
    def p(d):
        y, m, j = (int(x) for x in d.split("-"))
        return date(y, max(m, 1), max(j, 1))
    return abs((p(d1) - p(d2)).days)


def cle_entree(e):
    k = f"{e['date']}|{'supp' if e['supplement'] else 'cps'}|{e['numero']}"
    return k + ("|NS" if e["nouvelle_serie"] else "")


DEBUT_NOUVELLE_SERIE = "2000-11-01"


def serie_de(e):
    """Série d'une entrée : mention « Nouvelle Série » du site, sinon d'après la date
    (le site omet parfois la mention, ex. « Supplément à CPS n°82 » de 2022)."""
    if e["nouvelle_serie"] or e["date"] >= DEBUT_NOUVELLE_SERIE:
        return "nouvelle"
    return "bulletin1984" if e["date"] < "1985-01-01" else "ancienne"


def est_lien_supplement(url):
    f = url.lower().rsplit("/", 1)[-1]
    return "/supplements/" in url.lower() or re.search(r"supp?l?|decla", f) is not None


def classer_liens(liens):
    """Répartit les liens d'un article : html, pdf, page pdf, autres."""
    out = {"url_html": None, "url_pdf": None, "pdf_page": None, "autres_liens": []}
    for l in liens:
        u, lab = l["url"], l["label"].upper()
        base = url_sans_ancre(u).lower()
        if l.get("desactive"):
            out["autres_liens"].append({"url": u, "libelle": l["label"], "note": "lien désactivé sur le site"})
        elif (lab == "HTML" or base.endswith((".htm", ".html"))) and out["url_html"] is None and base.endswith((".htm", ".html")):
            out["url_html"] = u
        elif base.endswith(".pdf") and out["url_pdf"] is None:
            out["url_pdf"] = url_sans_ancre(u)
            out["pdf_page"] = page_pdf(u)
        else:
            out["autres_liens"].append({"url": u, "libelle": l["label"]})
    return out


# ------------------------------------------------ sommaire → publications

def construire_publications(entries, corrections):
    """Transforme les entrées brutes du sommaire en publications + articles."""
    anomalies = []
    corr_utilisees = set()

    # 1. appliquer les corrections et qualifier chaque entrée
    qualifiees = []
    for e in entries:
        k = cle_entree(e)
        c = corrections.get(k, {})
        if c:
            corr_utilisees.add(k)
        if "scinder_numero" in c:
            # en-tête de supplément suivi des articles d'un numéro : on scinde
            qualifiees.append({**e, "items": [], "_type": "supplement", "_cle": k, "_corr": c})
            qualifiees.append({**e, "supplement": False, "date": c["scinder_numero"]["date"],
                               "titre_entete": "", "liens_entete": [], "_type": "numero",
                               "_cle": k + " (scindé)", "_corr": c})
            continue
        typ = c.get("type") or ("supplement" if e["supplement"] else "numero")
        if e["numero"] == 0 and typ in ("numero", "supplement"):
            typ = "hors_serie"  # « CPS n°0 » / « Supplément à CPS n°0 » : texte hors série
        if not e["nouvelle_serie"] and e["numero"] and e["date"] >= DEBUT_NOUVELLE_SERIE and "serie" not in c:
            anomalies.append(("serie_implicite", k, "mention « Nouvelle Série » absente sur le site ; série déduite de la date"))
        qualifiees.append({**e, "date": c.get("date", e["date"]), "_type": typ, "_cle": k, "_corr": c})

    for k in corrections:
        if k not in corr_utilisees:
            anomalies.append(("correction_inutilisee", k, "correction sans entrée correspondante (le site a changé ?)"))

    # 2. regrouper les entrées « numéro » par (série, n°)
    groupes = defaultdict(list)
    autres = []
    for q in qualifiees:
        if q["_type"] == "numero":
            groupes[(q["_corr"].get("serie") or serie_de(q), q["numero"])].append(q)
        else:
            autres.append(q)

    publications, articles = {}, []

    def ajouter_articles(pub_id, items, date_sommaire, ordre0=0, origine="sommaire"):
        n = ordre0
        for it in items:
            n += 1
            lk = classer_liens(it["liens"])
            articles.append({
                "id": f"{pub_id}-{n:02d}", "publication_id": pub_id, "ordre": n,
                "titre": it["titre"] or "(sans titre)", "date_sommaire": date_sommaire,
                **lk, "origine": origine,
            })
        return n

    for (serie, num), grp in sorted(groupes.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        # entrée principale : celle qui a le plus d'articles (puis la plus ancienne)
        grp.sort(key=lambda q: (-len(q["items"]), q["date"]))
        principale, secondaires = grp[0], grp[1:]
        pub_id = f"{SERIES[serie]['prefixe']}-{num:03d}"
        liens = principale["liens_entete"]
        pdf = principale["_corr"].get("pdf_numero") or next(
            (url_sans_ancre(l["url"]) for l in liens if l["url"].lower().split("#")[0].endswith(".pdf")), None)
        pdf_desactive = any(l["desactive"] for l in liens)
        d = principale["date"]
        dfich = date_depuis_fichier(pdf)
        if dfich and ecart_jours(d, dfich) > 45 and not principale["_corr"].get("date"):
            anomalies.append(("date_numero", pub_id, f"date du sommaire {d} ≠ date du fichier PDF {dfich}"))
        publications[pub_id] = {
            "id": pub_id, "type": "numero", "serie": serie, "numero": num,
            "numero_label": principale["_corr"].get("numero_label", str(num)), "numero_cumule": num + DECALAGE_NOUVELLE_SERIE if serie == "nouvelle" else (num if serie == "ancienne" else None),
            "date": d, "titre": None, "parent_id": None,
            "url_pdf": pdf, "pdf_disponible": 0 if (pdf_desactive or not pdf) else 1,
            "cles_sommaire": [principale["_cle"]],
        }
        n = ajouter_articles(pub_id, principale["items"], principale["date"])
        for s in secondaires:
            liens_items = [l["url"] for it in s["items"] for l in it["liens"]]
            if len(s["items"]) == 1 and liens_items and all(est_lien_supplement(u) for u in liens_items):
                # entrée isolée renvoyant vers un supplément : c'est un supplément
                autres.append({**s, "_type": "supplement", "titre_entete": s["items"][0]["titre"],
                               "liens_entete": s["items"][0]["liens"], "items": [],
                               "_parent": pub_id})
                anomalies.append(("doublon_numero", pub_id, f"entrée du {s['date']} requalifiée en supplément : {s['items'][0]['titre'][:80]}"))
            else:
                n = ajouter_articles(pub_id, s["items"], s["date"], n)
                publications[pub_id]["cles_sommaire"].append(s["_cle"])
                anomalies.append(("doublon_numero", pub_id, f"entrée du {s['date']} fusionnée avec le numéro ({len(s['items'])} article(s))"))

    # 3. suppléments, numéros spéciaux, hors-séries
    supp_par_parent = defaultdict(list)
    for q in autres:
        serie = q["_corr"].get("serie") or serie_de(q)
        if q["_type"] == "supplement":
            parent = q.get("_parent") or f"{SERIES[serie]['prefixe']}-{q['numero']:03d}"
            supp_par_parent[parent].append(q)
        elif q["_type"] == "numero_special":
            label = q["_corr"]["numero_label"]
            pub_id = f"{SERIES[serie]['prefixe']}-{label.replace(' ', '')}"
            pdf = next((url_sans_ancre(l["url"]) for it in q["items"] for l in it["liens"] if ".pdf" in l["url"].lower()), None)
            publications[pub_id] = {
                "id": pub_id, "type": "numero_special", "serie": serie, "numero": q["numero"],
                "numero_label": label, "numero_cumule": None, "date": q["date"],
                "titre": q["_corr"].get("titre"), "parent_id": f"{SERIES[serie]['prefixe']}-{q['numero']:03d}",
                "url_pdf": pdf, "pdf_disponible": 1 if pdf else 0, "cles_sommaire": [q["_cle"]],
            }
            ajouter_articles(pub_id, q["items"], q["date"])
        elif q["_type"] == "hors_serie":
            pub_id = f"HS-{q['date']}"
            pdf = q["_corr"].get("pdf_numero")
            if not pdf:
                pdfs = {url_sans_ancre(l["url"]) for it in q["items"] for l in it["liens"] + q["liens_entete"]
                        if ".pdf" in l["url"].lower()}
                if not q["items"]:
                    pdfs |= {url_sans_ancre(l["url"]) for l in q["liens_entete"] if ".pdf" in l["url"].lower()}
                pdf = pdfs.pop() if len(pdfs) == 1 else None
            if not q["items"]:
                # texte isolé : un seul article, qui porte le titre de l'entrée
                q = {**q, "items": [{"titre": q["titre_entete"], "liens": q["liens_entete"]}]}
            publications[pub_id] = {
                "id": pub_id, "type": "hors_serie", "serie": serie, "numero": None,
                "numero_label": "hors série", "numero_cumule": None, "date": q["date"],
                "titre": q["_corr"].get("titre") or q["titre_entete"] or None, "parent_id": None,
                "url_pdf": pdf, "pdf_disponible": 1 if pdf else 0, "cles_sommaire": [q["_cle"]],
            }
            ajouter_articles(pub_id, q["items"], q["date"])

    for parent, supps in supp_par_parent.items():
        supps.sort(key=lambda q: (q["date"], -q["position"]))
        if parent not in publications:
            anomalies.append(("supplement_orphelin", parent, f"{len(supps)} supplément(s) rattaché(s) à un numéro absent du sommaire"))
        for i, q in enumerate(supps, 1):
            pub_id = f"{parent}-S{i}"
            titre = q["_corr"].get("titre") or q["titre_entete"] or "Supplément"
            lk = classer_liens(q["liens_entete"])
            pdf = q["_corr"].get("pdf_numero") or lk["url_pdf"]
            publications[pub_id] = {
                "id": pub_id, "type": "supplement", "serie": publications.get(parent, {}).get("serie") or ("nouvelle" if parent.startswith("NS") else "ancienne"),
                "numero": q["numero"], "numero_label": f"supplément au n°{q['numero']}",
                "numero_cumule": None, "date": q["date"], "titre": titre, "parent_id": parent,
                "url_pdf": pdf, "pdf_disponible": 1 if pdf else 0, "cles_sommaire": [q["_cle"]],
            }
            if q["items"]:
                ajouter_articles(pub_id, q["items"], q["date"])
            else:
                # un supplément sans sommaire = un seul texte, qui porte son titre
                ajouter_articles(pub_id, [{"titre": titre, "liens": q["liens_entete"]}], q["date"])

    # 4. contrôles : numéros manquants dans les séries
    for serie in ("ancienne", "nouvelle"):
        nums = set()
        for p in publications.values():
            if p["serie"] == serie and p["type"] == "numero":
                bornes = [int(x) for x in re.findall(r"\d+", p["numero_label"])]  # « 73-74 » = numéro double
                nums.update(range(min(bornes), max(bornes) + 1))
        if nums:
            manquants = [n for n in range(1, max(nums) + 1) if n not in nums]
            for n in manquants:
                anomalies.append(("numero_manquant", f"{SERIES[serie]['prefixe']}-{n:03d}", "numéro absent du sommaire du site"))

    for a in articles:
        a["date"] = publications[a["publication_id"]]["date"]
        a["serie"] = publications[a["publication_id"]]["serie"]
    return publications, articles, anomalies


# ------------------------------------------------------- tags du site

def candidats_pour(entree_tag, publications, index_pub):
    """Publications que désigne l'étiquette « CPS n°N [Nlle Série] » d'une entrée de tag."""
    num = entree_tag["numero"]
    if not num:
        return None
    if num["nouvelle_serie"] or (entree_tag["date"] or "") >= DEBUT_NOUVELLE_SERIE and num["numero"]:
        bases = [f"NS-{num['numero']:03d}"]
    elif entree_tag["date"] and entree_tag["date"] < "1985-01-01":
        bases = [f"B84-{num['numero']:03d}"]
    elif num["numero"] == 0:
        bases = [p for p in publications if p.startswith("HS-")]
    else:
        bases = [f"AS-{num['numero']:03d}"]
    ids = set()
    for b in bases:
        ids.add(b)
        ids.update(index_pub.get(b, []))  # suppléments, numéros spéciaux
    return ids


def similarite(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) > 25 and len(b) > 25 and (a.startswith(b) or b.startswith(a)):
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def associer_tags_du_site(publications, articles, tag_pages):
    """Rattache chaque entrée des pages de tags à un article du sommaire."""
    index_pub = defaultdict(list)
    for p in publications.values():
        if p["parent_id"]:
            index_pub[p["parent_id"]].append(p["id"])
    par_pub = defaultdict(list)
    par_url = defaultdict(list)
    for a in articles:
        par_pub[a["publication_id"]].append(a)
        for u in [a["url_html"], a["url_pdf"]] + [l["url"] for l in a["autres_liens"]]:
            if u:
                par_url[url_sans_ancre(u)].append(a)

    liens, non_trouves, ajouts = [], [], []
    for slug, entrees in tag_pages.items():
        for e in entrees:
            cands = candidats_pour(e, publications, index_pub)
            meilleur, score, methode = None, 0.0, None
            # 1. par URL d'article
            for l in e["liens"]:
                for a in par_url.get(url_sans_ancre(l["url"]), []):
                    if cands and a["publication_id"] not in cands:
                        continue
                    s = similarite(a["titre"], e["titre"])
                    if a["pdf_page"] and page_pdf(l["url"]) and a["pdf_page"] != page_pdf(l["url"]):
                        s -= 0.5
                    if meilleur is None or s > score:
                        meilleur, score, methode = a, s, "url"
            if meilleur is not None and score < 0.3 and len(par_url.get(url_sans_ancre(e["liens"][0]["url"]), [])) > 1:
                meilleur = None  # URL partagée (PDF de numéro complet) et titre différent
            # 2. par titre parmi les articles du numéro désigné
            if meilleur is None and cands:
                for pid in cands:
                    for a in par_pub.get(pid, []):
                        s = similarite(a["titre"], e["titre"])
                        if s > score:
                            meilleur, score, methode = a, s, "numero+titre"
                if score < 0.75:
                    meilleur = None
            # 3. par titre sur toute la base, à date identique
            if meilleur is None:
                score = 0.0
                for a in articles:
                    if e["date"] and a["date_sommaire"] != e["date"] and a["date"] != e["date"]:
                        continue
                    s = similarite(a["titre"], e["titre"])
                    if s > score:
                        meilleur, score, methode = a, s, "date+titre"
                if score < 0.8:
                    meilleur = None
            if meilleur is None:
                non_trouves.append((slug, e))
            else:
                liens.append((meilleur["id"], slug, "site", methode))
                # l'index thématique donne parfois un titre plus complet que le sommaire
                if norm(e["titre"]) != norm(meilleur["titre"]) and len(e["titre"]) > len(meilleur.get("titre_index") or meilleur["titre"]):
                    meilleur["titre_index"] = e["titre"]
    return liens, non_trouves


def ajouter_articles_index(publications, articles, non_trouves):
    """Articles présents dans l'index thématique mais absents du sommaire."""
    index_pub = defaultdict(list)
    for p in publications.values():
        if p["parent_id"]:
            index_pub[p["parent_id"]].append(p["id"])
    nouveaux = {}
    liens = []
    restants = []
    for slug, e in non_trouves:
        cands = candidats_pour(e, publications, index_pub) or set()
        base = next((c for c in sorted(cands) if c in publications and publications[c]["type"] in ("numero", "hors_serie")), None)
        if base is None:
            restants.append((slug, e))
            continue
        cle = (base, norm(e["titre"]))
        if cle not in nouveaux:
            # même article déjà ajouté depuis une autre page de tag ? (titre proche)
            dup = next((a for (b, _), a in nouveaux.items() if b == base and similarite(a["titre"], e["titre"]) > 0.9), None)
            if dup:
                nouveaux[cle] = dup
            else:
                ordre = max([a["ordre"] for a in articles if a["publication_id"] == base] + [0]) + 1
                lk = classer_liens(e["liens"])
                a = {"id": f"{base}-{ordre:02d}", "publication_id": base, "ordre": ordre,
                     "titre": e["titre"], "date_sommaire": e["date"], **lk,
                     "origine": "index_thematique", "date": publications[base]["date"],
                     "serie": publications[base]["serie"]}
                articles.append(a)
                nouveaux[cle] = a
        liens.append((nouveaux[cle]["id"], slug, "site", "index_thematique"))
    return liens, restants, len({id(a) for a in nouveaux.values()})


# ------------------------------------------------------ tags par règles

def appliquer_regles(articles, regles, existants):
    """Tags complémentaires déduits des titres par expressions régulières."""
    liens = []
    deja = {(a, t) for a, t, *_ in existants}
    compilees = []
    for r in regles["regles"]:
        flags = 0 if r.get("casse") else re.I
        compilees.append((r["tag"], re.compile(r["motif"], flags), re.compile(r["sauf"], flags) if r.get("sauf") else None))
    for a in articles:
        titre = a["titre"] + " | " + (a.get("titre_index") or "")
        for tag, motif, sauf in compilees:
            if motif.search(titre) and not (sauf and sauf.search(titre)) and (a["id"], tag) not in deja:
                liens.append((a["id"], tag, "regle", motif.pattern))
                deja.add((a["id"], tag))
    return liens


# ----------------------------------------------------------- écriture

SCHEMA = """
CREATE TABLE series (
  code TEXT PRIMARY KEY,
  prefixe TEXT NOT NULL,
  libelle TEXT NOT NULL
);
CREATE TABLE publications (
  id TEXT PRIMARY KEY,            -- ex. NS-098, AS-082, NS-098-S1, HS-1989-04
  type TEXT NOT NULL CHECK (type IN ('numero','numero_special','supplement','hors_serie')),
  serie TEXT NOT NULL REFERENCES series(code),
  numero INTEGER,                 -- n° dans la série (n° du numéro parent pour un supplément)
  numero_label TEXT,
  numero_cumule INTEGER,          -- n° continu depuis 1985 (nouvelle série = n° + 82)
  date TEXT NOT NULL,             -- AAAA-MM-JJ
  titre TEXT,                     -- pour suppléments et hors-séries
  parent_id TEXT REFERENCES publications(id),
  url_pdf TEXT,
  pdf_disponible INTEGER NOT NULL,
  nb_pages INTEGER,               -- pages du PDF dont le texte a été extrait
  texte_methode TEXT,             -- pdf_texte (couche texte) | ocr_tesseract (scan océrisé)
  cles_sommaire TEXT              -- entrée(s) d'origine dans le sommaire du site
);
CREATE TABLE pages (
  publication_id TEXT NOT NULL REFERENCES publications(id),
  page INTEGER NOT NULL,          -- n° de page dans le PDF (1 = couverture)
  texte TEXT NOT NULL,
  methode TEXT NOT NULL,          -- pdf_texte | ocr_tesseract
  PRIMARY KEY (publication_id, page)
);
CREATE TABLE articles (
  id TEXT PRIMARY KEY,            -- <publication>-<ordre>
  publication_id TEXT NOT NULL REFERENCES publications(id),
  ordre INTEGER NOT NULL,
  titre TEXT NOT NULL,            -- titre tel que dans le sommaire du site
  titre_index TEXT,               -- titre plus complet donné par l'index thématique, s'il diffère
  date TEXT NOT NULL,             -- date de la publication
  date_sommaire TEXT,             -- date affichée par le site pour l'entrée d'origine
  serie TEXT NOT NULL,
  url_html TEXT,
  url_pdf TEXT,
  pdf_page INTEGER,               -- page dans le PDF quand le site la précise
  page_debut INTEGER,             -- page de début dans le PDF de la publication (ou dans url_pdf)
  page_debut_source TEXT,         -- site | localisation (titre retrouvé dans le texte des pages)
  autres_liens TEXT,              -- JSON
  origine TEXT NOT NULL,          -- sommaire | index_thematique
  texte TEXT,                     -- texte intégral quand il a pu être extrait
  texte_type TEXT,                -- html | pdf_article | pdf_publication | pages_numero (découpage approximatif)
  texte_source TEXT               -- URL ou description de la source du texte
);
CREATE TABLE tags (
  slug TEXT PRIMARY KEY,
  libelle TEXT NOT NULL,
  categorie TEXT NOT NULL,
  origine TEXT NOT NULL           -- site (index thématique) | ajout (créé par ce projet)
);
CREATE TABLE articles_tags (
  article_id TEXT NOT NULL REFERENCES articles(id),
  tag TEXT NOT NULL REFERENCES tags(slug),
  source TEXT NOT NULL,           -- site | regle
  detail TEXT,                    -- méthode de rapprochement ou motif de la règle
  PRIMARY KEY (article_id, tag)
);
CREATE INDEX idx_articles_pub ON articles(publication_id);
CREATE INDEX idx_articles_date ON articles(date);
CREATE INDEX idx_at_tag ON articles_tags(tag);

CREATE VIEW v_articles AS
SELECT a.id, a.date, a.serie, p.type AS type_publication, p.numero_label,
       p.id AS publication_id, a.ordre, a.titre, a.titre_index,
       (SELECT group_concat(tag, ';') FROM (SELECT tag FROM articles_tags t WHERE t.article_id = a.id ORDER BY tag)) AS tags,
       a.url_html, a.url_pdf, a.pdf_page, a.page_debut, p.url_pdf AS url_pdf_numero,
       a.texte IS NOT NULL AS texte_disponible
FROM articles a JOIN publications p ON p.id = a.publication_id;

CREATE VIEW v_tags AS
SELECT t.slug, t.libelle, t.categorie, t.origine,
       count(at.article_id) AS nb_articles,
       sum(at.source = 'site') AS nb_site,
       sum(at.source = 'regle') AS nb_regle
FROM tags t LEFT JOIN articles_tags at ON at.tag = t.slug
GROUP BY t.slug;
"""


def ecrire_sqlite(path, publications, articles, tags, liens_tags, pages, avec_pages=True):
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO series VALUES (?,?,?)",
                   [(k, v["prefixe"], v["libelle"]) for k, v in SERIES.items()])
    db.executemany("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (p["id"], p["type"], p["serie"], p["numero"], p["numero_label"], p["numero_cumule"], p["date"],
         p["titre"], p["parent_id"], p["url_pdf"], p["pdf_disponible"],
         len(pages[p["id"]]["pages"]) if p["id"] in pages else None,
         pages[p["id"]]["methode"] if p["id"] in pages else None,
         " ; ".join(p["cles_sommaire"]))
        for p in publications])
    if avec_pages:
        db.executemany("INSERT INTO pages VALUES (?,?,?,?)", [
            (pid, i, t, v["methode"]) for pid, v in sorted(pages.items()) for i, t in enumerate(v["pages"], 1)])
    db.executemany("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (a["id"], a["publication_id"], a["ordre"], a["titre"], a.get("titre_index"), a["date"], a["date_sommaire"], a["serie"],
         a["url_html"], a["url_pdf"], a["pdf_page"], a.get("page_debut"), a.get("page_debut_source"),
         json.dumps(a["autres_liens"], ensure_ascii=False) if a["autres_liens"] else None,
         a["origine"], a.get("texte"), a.get("texte_type"), a.get("texte_source"))
        for a in articles])
    db.executemany("INSERT INTO tags VALUES (?,?,?,?)",
                   [(t["slug"], t["libelle"], t["categorie"], t["origine"]) for t in tags])
    db.executemany("INSERT INTO articles_tags VALUES (?,?,?,?)", liens_tags)
    # recherche plein texte (titres + textes)
    try:
        db.execute("CREATE VIRTUAL TABLE articles_fts USING fts5(titre, titre_index, texte, content='articles', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2')")
        db.execute("INSERT INTO articles_fts(rowid, titre, titre_index, texte) SELECT rowid, titre, coalesce(titre_index,''), coalesce(texte,'') FROM articles")
        if avec_pages:
            db.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(texte, content='pages', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2')")
            db.execute("INSERT INTO pages_fts(rowid, texte) SELECT rowid, texte FROM pages")
    except sqlite3.OperationalError as exc:
        print(f"FTS5 indisponible : {exc}", file=sys.stderr)
    db.commit()
    db.execute("VACUUM")
    db.close()


def ecrire_csv(dossier, publications, articles, tags, liens_tags):
    dossier.mkdir(parents=True, exist_ok=True)
    tags_par_article = defaultdict(list)
    for aid, tag, *_ in liens_tags:
        tags_par_article[aid].append(tag)

    def w(nom, champs, lignes):
        with open(dossier / nom, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(lignes)

    w("publications.csv", ["id", "type", "serie", "numero", "numero_label", "numero_cumule", "date", "titre",
                           "parent_id", "url_pdf", "pdf_disponible"], publications)
    w("articles.csv", ["id", "publication_id", "ordre", "date", "serie", "titre", "titre_index", "tags", "url_html", "url_pdf",
                       "pdf_page", "page_debut", "page_debut_source", "origine", "texte_disponible"],
      [{**a, "tags": ";".join(sorted(tags_par_article[a["id"]])), "texte_disponible": int(bool(a.get("texte")))}
       for a in articles])
    w("tags.csv", ["slug", "libelle", "categorie", "origine", "nb_articles"],
      [{**t, "nb_articles": sum(1 for _, s, *_ in liens_tags if s == t["slug"])} for t in tags])
    w("articles_tags.csv", ["article_id", "tag", "source", "detail"],
      [dict(zip(["article_id", "tag", "source", "detail"], l)) for l in liens_tags])


def ecrire_json(path, publications, articles, tags, liens_tags):
    tags_par_article = defaultdict(list)
    for aid, tag, source, _ in liens_tags:
        tags_par_article[aid].append({"tag": tag, "source": source})
    arts = defaultdict(list)
    for a in articles:
        arts[a["publication_id"]].append({
            k: a.get(k) for k in ("id", "ordre", "titre", "titre_index", "date", "url_html", "url_pdf", "pdf_page",
                                  "page_debut", "page_debut_source", "origine")
        } | {"tags": sorted(tags_par_article[a["id"]], key=lambda t: t["tag"]),
             "texte_disponible": bool(a.get("texte"))})
    out = {
        "titre": "Combattre pour le socialisme — base des articles",
        "source": "http://socialisme.free.fr/",
        "series": SERIES,
        "tags": tags,
        "publications": [{**{k: v for k, v in p.items() if k != "cles_sommaire"}, "articles": arts[p["id"]]}
                         for p in publications],
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def ecrire_rapport(path, publications, articles, tags, liens_tags, anomalies, non_trouves, nb_ajouts, pages):
    pubs = list(publications)
    lignes = ["# Rapport de qualité", "",
              "Généré automatiquement par `scripts/build_db.py`. Ne pas modifier à la main.", "",
              "## Statistiques", ""]
    def compte(f):
        return sum(1 for p in pubs if f(p))
    lignes += [
        "| Élément | Nombre |", "|---|---|",
        f"| Publications (total) | {len(pubs)} |",
        f"| — numéros, bulletin 1984 | {compte(lambda p: p['type']=='numero' and p['serie']=='bulletin1984')} |",
        f"| — numéros, ancienne série | {compte(lambda p: p['type']=='numero' and p['serie']=='ancienne')} |",
        f"| — numéros, nouvelle série | {compte(lambda p: p['type']=='numero' and p['serie']=='nouvelle')} |",
        f"| — numéros spéciaux | {compte(lambda p: p['type']=='numero_special')} |",
        f"| — hors-séries | {compte(lambda p: p['type']=='hors_serie')} |",
        f"| — suppléments | {compte(lambda p: p['type']=='supplement')} |",
        f"| Articles | {len(articles)} |",
        f"| — dont ajoutés depuis l'index thématique (absents du sommaire) | {nb_ajouts} |",
        f"| — avec lien HTML | {sum(1 for a in articles if a['url_html'])} |",
        f"| — avec lien PDF propre ou page de PDF | {sum(1 for a in articles if a['url_pdf'])} |",
        f"| — avec texte intégral (page HTML ou PDF propre) | {sum(1 for a in articles if a.get('texte_type') in ('html', 'pdf_article'))} |",
        f"| — avec texte intégral (PDF de la publication) | {sum(1 for a in articles if a.get('texte_type') == 'pdf_publication')} |",
        f"| — avec texte approximatif (pages du numéro) | {sum(1 for a in articles if a.get('texte_type') == 'pages_numero')} |",
        f"| — page de début connue (site) | {sum(1 for a in articles if a.get('page_debut_source') == 'site')} |",
        f"| — page de début retrouvée par le titre | {sum(1 for a in articles if a.get('page_debut_source') == 'localisation')} |",
        f"| Publications dont le texte intégral est disponible (pages) | {sum(1 for p in pubs if p['id'] in pages)} |",
        f"| — dont océrisées (scans) | {sum(1 for p in pubs if pages.get(p['id'], {}).get('methode') == 'ocr_tesseract')} |",
        f"| Pages de texte | {sum(len(v['pages']) for k, v in pages.items() if k in {p['id'] for p in pubs})} |",
        f"| Tags | {len(tags)} |",
        f"| Associations article-tag (index du site) | {sum(1 for l in liens_tags if l[2]=='site')} |",
        f"| Associations article-tag (règles) | {sum(1 for l in liens_tags if l[2]=='regle')} |",
        f"| Articles sans aucun tag | {len({a['id'] for a in articles} - {l[0] for l in liens_tags})} |",
        "",
    ]
    par_type = defaultdict(list)
    for typ, ref, msg in anomalies:
        par_type[typ].append((ref, msg))
    titres = {
        "numero_manquant": "Numéros absents du sommaire du site",
        "date_numero": "Dates du sommaire en désaccord avec le nom du fichier PDF (non corrigées)",
        "doublon_numero": "Numéros listés plusieurs fois dans le sommaire",
        "supplement_orphelin": "Suppléments rattachés à un numéro absent",
        "correction_inutilisee": "Corrections sans effet",
        "serie_implicite": "Entrées sans mention « Nouvelle Série » rattachées à la nouvelle série d'après leur date",
    }
    lignes += ["## Anomalies", ""]
    for typ, items in par_type.items():
        lignes += [f"### {titres.get(typ, typ)} ({len(items)})", ""]
        lignes += [f"- `{ref}` : {msg}" for ref, msg in items]
        lignes.append("")
    morts = []
    for nom in ("textes", "pages"):
        f = DATA / nom / "index.json"
        if f.exists():
            for ref, v in json.loads(f.read_text(encoding="utf-8")).items():
                if v.get("statut") == "introuvable":
                    morts.append((ref, v["source"]))
    lignes += [f"### Liens morts sur le site ({len(morts)})", ""]
    lignes += [f"- `{ref}` : {url}" for ref, url in sorted(morts)]
    lignes.append("")
    lignes += [f"### Entrées de l'index thématique non rattachées ({len(non_trouves)})", ""]
    lignes += [f"- tag `{slug}` — {e['date']} — {e['titre'][:120]}" for slug, e in non_trouves]
    lignes.append("")
    path.write_text("\n".join(lignes), encoding="utf-8")


# --------------------------------------------------------------- main

def corriger_liens(obj, table):
    """Remplace en place les URL erronées (config/corrections.json, section « liens »)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "url" and isinstance(v, str):
                base, _, ancre = v.partition("#")
                if base in table:
                    obj[k] = table[base] + ("#" + ancre if ancre else "")
            else:
                corriger_liens(v, table)
    elif isinstance(obj, list):
        for x in obj:
            corriger_liens(x, table)


def charger_pages(publications):
    """Textes page par page produits par extraire_pages.py."""
    dossier = DATA / "pages"
    meta_path = dossier / "index.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    pages = {}
    for pid, m in meta.items():
        if m.get("statut") != "ok" or pid not in publications:
            continue
        f = dossier / f"{m.get('identique_a', pid)}.txt"
        if f.exists():
            pages[pid] = {"pages": f.read_text(encoding="utf-8").rstrip("\n").split("\f"),
                          "methode": m["methode"], "source": m["source"]}
    return pages, meta


MAX_PAGES_ARTICLE = 12


def charger_textes(articles, publications, pages):
    """Page de début et texte de chaque article.

    Page de début dans le PDF de la publication : celle indiquée par le site
    (page_debut_source = site), sinon celle trouvée en cherchant le titre dans le
    texte des pages (localisation, voir localiser.py).

    Texte, par ordre de préférence :
    1. page HTML ou PDF propre à l'article (fetch_textes.py) ;
    2. PDF entier d'une publication qui ne contient qu'un article (supplément…) ;
    3. pages du PDF à partir de la page de début, jusqu'à la page où commence
       l'article suivant (incluse) : découpage approximatif."""
    dossier = DATA / "textes"
    meta_path = dossier / "index.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    pages_par_url = {v["source"]: v for v in pages.values()}
    par_pub = defaultdict(list)
    for a in articles:
        par_pub[a["publication_id"]].append(a)

    # 1. pages de début
    for pid, arts in par_pub.items():
        pub = publications[pid]
        for a in arts:
            a["page_debut"], a["page_debut_source"] = None, None
            if a["pdf_page"] and (a["url_pdf"] == pub["url_pdf"] or a["url_pdf"] in pages_par_url):
                a["page_debut"], a["page_debut_source"] = a["pdf_page"], "site"
        if pid in pages and len(arts) > 1:
            for a, page in zip(arts, localiser.localiser([a["titre"] for a in arts], pages[pid]["pages"])):
                if page and not a["page_debut"]:
                    a["page_debut"], a["page_debut_source"] = page, "localisation"

    # 2. textes
    for a in articles:
        m = meta.get(a["id"], {})
        f = dossier / f"{m.get('identique_a', a['id'])}.txt"
        if m.get("statut") == "ok" and f.exists():
            a["texte"] = f.read_text(encoding="utf-8").strip()
            a["texte_type"] = "html" if m.get("type") == "html" else "pdf_article"
            a["texte_source"] = m["source"]
            continue
        pub = publications[a["publication_id"]]
        if len(par_pub[pub["id"]]) == 1 and pub["id"] in pages and (not a["url_pdf"] or a["url_pdf"] == pub["url_pdf"]) and not a["pdf_page"]:
            v = pages[pub["id"]]
            a["texte"] = "\n\n".join(p for p in v["pages"] if p.strip())
            a["texte_type"] = "pdf_publication"
            a["texte_source"] = f"{v['source']} ({v['methode']})"
            continue
        if not a["page_debut"]:
            continue
        # PDF dans lequel se trouve l'article : celui de sa publication, ou celui qu'il cite
        if a["page_debut_source"] == "site" and a["url_pdf"] in pages_par_url:
            v, url = pages_par_url[a["url_pdf"]], a["url_pdf"]
        elif pub["id"] in pages:
            v, url = pages[pub["id"]], pub["url_pdf"]
        else:
            continue
        debut = a["page_debut"]
        suivants = sorted({b["page_debut"] for b in par_pub[pub["id"]]
                           if b is not a and b["page_debut"] and b["page_debut"] > debut
                           and (b["url_pdf"] if b["page_debut_source"] == "site" else pub["url_pdf"]) == url})
        fin = suivants[0] if suivants else debut
        fin = max(debut, min(fin, debut + MAX_PAGES_ARTICLE - 1, len(v["pages"])))
        extrait = v["pages"][debut - 1:fin]
        if any(p.strip() for p in extrait):
            a["texte"] = "\n\n".join(extrait)
            a["texte_type"] = "pages_numero"
            how = "page indiquée par le site" if a["page_debut_source"] == "site" else "page trouvée par le titre"
            a["texte_source"] = f"{v['source']} pages {debut}-{fin} ({v['methode']} ; {how} ; découpage approximatif)"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Construit la base de données CPS.")
    ap.add_argument("--sans-complet", action="store_true", help="ne pas produire data/cps_complet.sqlite")
    args = ap.parse_args()
    entries = parse_sommaire.parse((SOURCES / "sommaire.html").read_text(encoding="utf-8"))
    config_corr = json.loads((CONFIG / "corrections.json").read_text(encoding="utf-8"))
    corrections = config_corr["entrees"]
    liens_corriges = {k: v for k, v in config_corr.get("liens", {}).items() if not k.startswith("_")}
    corriger_liens(entries, liens_corriges)
    publications, articles, anomalies = construire_publications(entries, corrections)

    tags_site, tag_pages = parse_tags.load_all(SOURCES)
    for page in tag_pages.values():
        corriger_liens(page, liens_corriges)
    manquantes = [t["slug"] for t in tags_site if t["slug"] not in tag_pages]
    if manquantes:
        print(f"attention : {len(manquantes)} page(s) de tag non téléchargée(s) : {manquantes}", file=sys.stderr)
    liens_site, non_trouves = associer_tags_du_site(publications, articles, tag_pages)
    liens_ajout, non_trouves, nb_ajouts = ajouter_articles_index(publications, articles, non_trouves)

    regles = json.loads((CONFIG / "regles_tags.json").read_text(encoding="utf-8"))
    tags = [{**t, "origine": "site"} for t in tags_site]
    slugs = {t["slug"] for t in tags}
    for t in regles.get("nouveaux_tags", []):
        if t["slug"] not in slugs:
            tags.append({**t, "origine": "ajout"})
            slugs.add(t["slug"])
    # dédoublonnage : un article peut apparaître plusieurs fois sur une même page de tag
    vus, liens_tags = set(), []
    for l in liens_site + liens_ajout:
        if (l[0], l[1]) not in vus:
            vus.add((l[0], l[1]))
            liens_tags.append(l)
    liens_tags += appliquer_regles(articles, regles, liens_tags)
    inconnus = {l[1] for l in liens_tags} - slugs
    if inconnus:
        raise SystemExit(f"tags inconnus dans les règles : {inconnus}")

    pages, _ = charger_pages(publications)
    charger_textes(articles, publications, pages)

    ordre_type = {"numero": 0, "numero_special": 1, "hors_serie": 2, "supplement": 3}
    pubs = sorted(publications.values(), key=lambda p: (p["date"], ordre_type[p["type"]], p["id"]))
    articles.sort(key=lambda a: (publications[a["publication_id"]]["date"], a["publication_id"], a["ordre"]))
    liens_tags.sort()

    DATA.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    # base principale (versionnée) : sans le texte page par page, pour rester légère ;
    # base complète : avec la table pages et sa recherche plein texte
    ecrire_sqlite(DATA / "cps.sqlite", pubs, articles, tags, liens_tags, pages, avec_pages=False)
    if not args.sans_complet:
        ecrire_sqlite(DATA / "cps_complet.sqlite", pubs, articles, tags, liens_tags, pages, avec_pages=True)
    ecrire_csv(DATA / "csv", pubs, articles, tags, liens_tags)
    ecrire_json(DATA / "cps.json", pubs, articles, tags, liens_tags)
    ecrire_rapport(DOCS / "RAPPORT_QUALITE.md", pubs, articles, tags, liens_tags, anomalies, non_trouves, nb_ajouts, pages)
    print(f"{len(pubs)} publications, {len(articles)} articles, {len(tags)} tags, "
          f"{len(liens_tags)} associations, {len(non_trouves)} entrées de tag non rattachées")


if __name__ == "__main__":
    main()
