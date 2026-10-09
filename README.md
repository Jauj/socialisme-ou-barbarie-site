# Combattre pour le socialisme — base de données des articles

Base de données propre, **article par article et avec tags**, de la totalité des numéros
de *Combattre pour le socialisme* (CPS) publiés en ligne sur
[socialisme.free.fr](http://socialisme.free.fr/) :

| Série | Numéros | Période |
|---|---|---|
| Bulletin de 1984 | n°1 et n°2 | octobre – novembre 1984 |
| Ancienne série | n°1 à n°82 (dont le n°73‑74 double et un n°21 bis) | janvier 1985 – octobre 2000 |
| Nouvelle série | n°1 à n°98 (n° cumulé 83 à 180) | novembre 2000 – octobre 2026 |

S'y ajoutent les **suppléments** (déclarations, tracts, communiqués…) et les **hors‑séries**
(brochures, rapports de conférence) listés sur le site.

Chiffres et anomalies détectées : voir [`docs/RAPPORT_QUALITE.md`](docs/RAPPORT_QUALITE.md)
(généré automatiquement à chaque construction).

## Contenu

```
data/
  cps.sqlite            base SQLite : publications, articles, tags, textes d'articles, recherche plein texte
  cps_complet.sqlite    même base + texte de chaque page de chaque numéro (non versionnée, voir plus bas)
  cps.json              export hiérarchique publications → articles → tags (sans les textes)
  csv/                  les tables au format CSV (UTF‑8) : publications, articles, tags, articles_tags
  textes/<article>.txt  texte des articles disposant d'une page HTML ou d'un PDF propre sur le site
  pages/<publication>.txt  texte intégral de chaque PDF, pages séparées par un saut de page (\f)
config/
  corrections.json      corrections manuelles du sommaire du site, chacune justifiée
  regles_tags.json      règles de tags complémentaires (expressions régulières sur les titres)
sources/                pages du site utilisées (sommaire, index thématique, pages de tags)
scripts/                scripts de collecte et de construction
explorateur/            page web de consultation (filtres par série, tag, année, recherche)
docs/RAPPORT_QUALITE.md statistiques et anomalies
```

## Modèle de données

**`publications`** — un numéro, un numéro spécial, un supplément ou un hors‑série.

| Colonne | Description |
|---|---|
| `id` | `B84-001`, `AS-082` (ancienne série), `NS-098` (nouvelle série), `AS-021bis`, `NS-098-S1` (1er supplément au n°98), `HS-1989-04-16` (hors‑série) |
| `type` | `numero`, `numero_special`, `supplement`, `hors_serie` |
| `serie` | `bulletin1984`, `ancienne`, `nouvelle` |
| `numero`, `numero_label` | n° dans la série (`73-74` pour le numéro double) |
| `numero_cumule` | n° continu (nouvelle série : n° + 82, ex. NS‑98 = n°180) |
| `date` | date de parution (AAAA‑MM‑JJ) |
| `parent_id` | numéro auquel se rattache un supplément |
| `url_pdf` | PDF du numéro complet sur le site |
| `nb_pages`, `texte_methode` | pages dont le texte a été extrait ; `pdf_texte` (couche texte) ou `ocr_tesseract` (scan océrisé) |

**`articles`** — un article d'une publication, dans l'ordre du sommaire.

| Colonne | Description |
|---|---|
| `id` | `<publication>-<ordre>`, ex. `NS-098-02` |
| `titre` | titre tel que dans le sommaire du site |
| `titre_index` | titre plus complet donné par l'index thématique, quand il diffère |
| `date`, `serie` | reprises de la publication |
| `url_html`, `url_pdf`, `pdf_page` | liens vers l'article sur le site (page de début dans le PDF du numéro quand elle est connue) |
| `texte` | texte intégral quand il a pu être obtenu |
| `texte_type` | `html` / `pdf_article` (texte propre à l'article), `pdf_publication` (le supplément entier), `pages_numero` (pages du numéro, **découpage approximatif**) |
| `origine` | `sommaire` (sommaire du site) ou `index_thematique` (article présent seulement dans l'index) |

**`tags`** et **`articles_tags`** — vocabulaire et associations.

- Les 110 tags de l'[index thématique du site](http://socialisme.free.fr/recherchethem.php?tag=null)
  sont repris tels quels (`origine = site`), avec leurs catégories : Rubriques, France,
  Partis et syndicats en France, Théorie, International.
- Quelques tags ont été ajoutés (`origine = ajout`) : Irak, Tunisie, Afrique, Code du travail/emploi,
  Industrie, Ve République, Grève générale, Front unique.
- Chaque association indique sa `source` :
  - `site` : l'article figure sur la page du tag dans l'index thématique du site ;
  - `regle` : tag déduit du titre par une règle de [`config/regles_tags.json`](config/regles_tags.json)
    (l'index du site est incomplet : beaucoup d'articles n'y figurent pas).

**`pages`** (dans `cps_complet.sqlite`) — texte de chaque page de chaque PDF de publication,
avec recherche plein texte (`pages_fts`). Les numéros scannés (ancienne série et premières années
de la nouvelle) ont été océrisés avec Tesseract (français) : le texte peut contenir des erreurs de
reconnaissance.

Vues pratiques : `v_articles` (articles avec leurs tags en une colonne), `v_tags` (tags avec leurs effectifs).

## Exemples de requêtes

```sql
-- Tous les articles tagués « Bolivie », du plus récent au plus ancien
SELECT date, publication_id, titre, url_html, url_pdf FROM v_articles
WHERE ';' || tags || ';' LIKE '%;bolivie;%' ORDER BY date DESC;

-- Les éditoriaux de l'ancienne série
SELECT a.date, a.titre FROM articles a JOIN articles_tags t ON t.article_id = a.id
WHERE t.tag = 'editorial' AND a.serie = 'ancienne' ORDER BY a.date;

-- Recherche plein texte dans les titres et textes d'articles (sans accents ni casse)
SELECT a.id, a.date, a.titre FROM articles_fts f JOIN articles a ON a.rowid = f.rowid
WHERE articles_fts MATCH 'echelle mobile' ORDER BY a.date;

-- Recherche dans toutes les pages de tous les numéros (cps_complet.sqlite)
SELECT p.publication_id, p.page, snippet(pages_fts, 0, '[', ']', '…', 12)
FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid
WHERE pages_fts MATCH '"gouvernement ouvrier"' ORDER BY p.publication_id;
```

Avec Python : `sqlite3.connect("data/cps.sqlite")`, ou avec pandas
`pd.read_csv("data/csv/articles.csv")`. Les fichiers CSV s'ouvrent aussi dans un tableur.

## Explorateur web

`explorateur/index.html` permet de parcourir la base (recherche, filtres par série, type, tag,
période). Il lit `data/cps.json` : servir le dépôt avec un serveur web, par exemple
`python3 -m http.server` puis ouvrir <http://localhost:8000/explorateur/>, ou activer GitHub Pages
sur la racine du dépôt.

## Reconstruire la base

Python 3.9+ avec `beautifulsoup4`, et `poppler-utils` (pdftotext, pdftoppm) ;
`tesseract-ocr` + `tesseract-ocr-fra` pour l'OCR.

```sh
pip install -r requirements.txt
python3 scripts/fetch_sources.py      # sommaire + index thématique → sources/ (--refresh pour mettre à jour)
python3 scripts/build_db.py           # → data/ (sans réseau)
python3 scripts/fetch_textes.py       # textes des articles HTML/PDF → data/textes/
python3 scripts/extraire_pages.py     # texte des PDF de numéros (OCR des scans, long) → data/pages/
python3 scripts/build_db.py           # reconstruction avec les textes
```

`build_db.py` ne fait aucun accès réseau : `cps_complet.sqlite` (trop volumineux pour être
versionné) se régénère en quelques secondes à partir de `data/pages/`.

Pour intégrer un nouveau numéro : `fetch_sources.py --refresh`, `fetch_textes.py`,
`extraire_pages.py`, puis `build_db.py`.

## Corrections apportées au sommaire du site

Le sommaire du site contient quelques erreurs ; elles sont corrigées dans
[`config/corrections.json`](config/corrections.json), chaque fois avec un motif, par exemple :

- numéros saisis avec une mauvaise année (« CPS n°33 » daté de 2009 au lieu de 2008, communiqué
  sur l'Irak de 2003 daté de 2009) ;
- le n°1 et le n°2 de 1985 pointaient vers les PDF des bulletins de 1984 ;
- le n°52 de la nouvelle série était listé sous l'en‑tête d'un supplément RATP ;
- le n°73 de l'ancienne série est en fait le numéro double **73‑74** (couverture vérifiée) :
  il n'y a pas de n°74 manquant ;
- des « CPS n°0 » qui sont des hors‑séries, des entrées en double qui sont des suppléments.

Les autres incohérences repérées automatiquement (dates du sommaire différentes de celle du
nom de fichier PDF, etc.) sont listées dans le rapport de qualité sans être corrigées.

## Droits

Les textes sont ceux publiés par le Groupe pour la construction du Parti ouvrier révolutionnaire
(et auparavant le Comité) sur socialisme.free.fr ; cette base en est un index et une copie de
travail destinés à la recherche et à la consultation. Les liens renvoient toujours vers les
documents originaux du site.
