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

En chiffres : **381 publications, 1 293 articles, 118 tags**, le **texte intégral de
7 688 pages** (les 350 PDF disponibles, dont 177 numéros scannés océrisés) et une **version
Markdown de chaque article** : 1 175 articles avec leur texte, en base (`texte_markdown`) et en
fichiers `.md` avec leurs métadonnées.

Chiffres et anomalies détectées : voir [`docs/RAPPORT_QUALITE.md`](docs/RAPPORT_QUALITE.md)
(généré automatiquement à chaque construction).

## Contenu

```
data/
  cps.sqlite            base SQLite : publications, articles (avec leur texte en Markdown), tags,
                        recherche plein texte
  cps_complet.sqlite    même base + texte brut des articles + texte (brut et Markdown) de chaque page
                        de chaque numéro (non versionnée : ~200 Mo, se régénère en ~3 min avec
                        `python3 scripts/build_db.py`, sans réseau)
  markdown/<publication>/<article>.md   un fichier par article : en-tête YAML (titre, date, numéro,
                        tags, liens…) puis le texte en Markdown
  recherche.sqlite      index plein texte de l'explorateur (FTS5 avec positions, sans le texte : lu
                        dans le navigateur par requêtes HTTP Range)
  cps.json              export hiérarchique publications → articles → tags (sans les textes)
  csv/                  les tables au format CSV (UTF‑8) : publications, articles, tags, articles_tags
  textes/<article>.md|.txt  texte des articles disposant d'une page HTML ou d'un PDF propre sur le site
  pages/<publication>.txt|.md  texte intégral de chaque PDF (brut / structuré en Markdown),
                        pages séparées par un saut de page (\f)
  corrections_ocr/<publication>.json  pages scannées les plus abîmées, corrigées et contrôlées
config/
  corrections.json      corrections manuelles du sommaire du site, chacune justifiée
  regles_tags.json      règles de tags complémentaires (sur les titres et sur le texte intégral)
  articles_pdf.json     articles imprimés absents du sommaire du site, pages de début relues
sources/                pages du site utilisées (sommaire, index thématique, pages de tags)
scripts/                scripts de collecte et de construction (+ serveur.py, serveur web local)
tests/                  tests de non-régression (python3 -m unittest discover -s tests -t .)
explorateur/            page web de consultation (recherche plein texte, filtres, lecture, numéros)
docs/RAPPORT_QUALITE.md statistiques et anomalies
.github/workflows/      tests, construction de la base et publication du site (GitHub Actions)
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
| `date` | date de parution (AAAA‑MM‑JJ) donnée par le site |
| `date_imprimee` | date lue dans l'en‑tête de la une (`JJ` = `00` quand seul le mois est imprimé) ; les écarts avec `date` sont listés dans le rapport de qualité |
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
| `date_redaction` | date isolée qui clôt le texte (« Le 7 avril 2008 », « Le 2/3/1990 »), quand il y en a une |
| `url_html`, `url_pdf`, `pdf_page` | liens vers l'article sur le site (`pdf_page` : page indiquée par le site) |
| `page_debut`, `page_debut_source` | page de début dans le PDF de la publication : indiquée par le site (`site`), par le sommaire imprimé en une du numéro (`sommaire`), retrouvée en cherchant le titre de l'article dans les pages (`titre`), retrouvée par relecture ([`config/articles_pdf.json`](config/articles_pdf.json), `relecture`), ou, pour le premier article d'un numéro introuvable autrement, début de la une (`ordre`) |
| `texte_markdown` | texte intégral en Markdown, quand il a pu être obtenu (voir plus bas) |
| `texte` | le même texte, brut — **seulement dans `cps_complet.sqlite`** (dérivable du Markdown, retiré de la base légère pour rester sous 50 Mo) |
| `texte_type` | `html` / `pdf_article` (texte propre à l'article), `pdf_publication` (le supplément entier), `pages_numero` (découpé dans le PDF du numéro, du titre de l'article — surtitre compris — jusqu'au titre de l'article suivant : **découpage automatique**, qui peut déborder sur l'article voisin ; `texte_source` signale une « fin incertaine » quand l'article suivant du sommaire n'a pas été retrouvé : le texte est alors borné à 16 pages) |
| `texte_source` | URL du document dont vient le texte, pages et méthode (couche texte ou OCR) |
| `origine` | `sommaire` (sommaire du site), `index_thematique` (article présent seulement dans l'index) ou `pdf` (article imprimé dans le numéro, avec son entrée au sommaire imprimé en une, mais absent du site : voir plus bas) |

**`tags`** et **`articles_tags`** — vocabulaire et associations.

- Les 110 tags de l'[index thématique du site](http://socialisme.free.fr/recherchethem.php?tag=null)
  sont repris tels quels (`origine = site`), avec leurs catégories : Rubriques, France,
  Partis et syndicats en France, Théorie, International.
- Quelques tags ont été ajoutés (`origine = ajout`) : Irak, Tunisie, Afrique, Code du travail/emploi,
  Industrie, Ve République, Grève générale, Front unique.
- Chaque association indique sa `source` :
  - `site` : l'article figure sur la page du tag dans l'index thématique du site ;
  - `regle` : tag déduit du titre par une règle de [`config/regles_tags.json`](config/regles_tags.json)
    (l'index du site est incomplet : beaucoup d'articles n'y figurent pas) ;
  - `texte` : tag déduit du texte intégral, quand un terme du sujet (« Grèce », « Syriza »… ;
    section `texte` des règles) y revient au moins 5 fois et au moins 2 fois pour 1 000 mots
    (`detail` donne le nombre d'occurrences). Seuils choisis après contrôle d'un échantillon de
    120 associations tirées au sort par tranches de densité, jugées par des agents Haiku : le
    sujet est réellement développé dans au moins un passage de l'article dans 116 cas, cité en
    passant ou dans une énumération dans 3 cas (1 indécis) ; le motif en cause (« loi Debré »,
    aussi le nom d'une loi sur l'immigration) a été retiré.

**`pages`** (dans `cps_complet.sqlite`) — texte de chaque page de chaque PDF de publication
(`texte` brut et `markdown` structuré), avec recherche plein texte (`pages_fts`). Les numéros scannés (bulletin 1984, ancienne série et
nouvelle série jusqu'au n°45 environ) ont été océrisés avec Tesseract (français) : le texte peut
contenir des erreurs de reconnaissance.

**Localisation des articles.** Le site n'indique la page de début que pour 80 articles. Pour les
autres, trois indices sont combinés :

- le **sommaire imprimé en une** (93 numéros, lignes « TITRE ........ P.12 », points de conduite
  parfois lus comme des lettres par l'OCR), apparié aux titres du site par leurs mots ; il guide
  la recherche du titre, avec une page de tolérance car il se trompe parfois d'une page ;
- le **titre**, cherché parmi les intertitres des pages structurées en Markdown (seuls ou
  groupés : surtitre, titre, sous‑titre), au début d'un paragraphe quand l'OCR n'a pas isolé
  l'intertitre, ou réduit à sa rubrique pour les rubriques récurrentes (« Les militants
  interviennent : RATP ; Université… » → intertitre « LES MILITANTS INTERVIENNENT ») ; dans
  l'ordre du sommaire, en écartant les pages qui citent plusieurs titres (une, sommaires de
  dernière page) ;
- en dernier recours, la page du sommaire imprimé, et pour le premier article d'un numéro, la une.

Le début retenu est ensuite ajusté : le surtitre et les intertitres placés juste au‑dessus du titre
retrouvé sont inclus, et en haut de page la fin de l'article précédent lui est laissée. Le texte
va jusqu'au début de l'article suivant retrouvé dans le même PDF, sans limite de longueur, sauf
quand un article intermédiaire du sommaire n'a pas été retrouvé (« fin incertaine », texte borné
à 16 pages). Contrôle : sur les 79 articles dont le site donne la page, la méthode appliquée sans
cette information en retrouve 68, dont 65 à la page exacte et 2 à une page près.

**Recherche plein texte.** L'index `articles_fts` porte sur `titre`, `titre_index` et
`texte_markdown`. `cps.sqlite` le contient en mode allégé (recherche
par mots, opérateurs AND/OR/NOT, préfixes `mot*`, mais pas de phrase exacte entre guillemets) pour
rester sous 50 Mo. `cps_complet.sqlite` a l'index complet (phrases exactes, NEAR) sur les articles
et sur les pages. `recherche.sqlite`, utilisé par l'explorateur, a lui aussi l'index complet
(phrases exactes) mais sans le texte (table FTS5 `content=''`, table `ids` pour retrouver
l'identifiant de l'article) : environ 17 Mo, dont le navigateur ne lit que les pages utiles.

Vues pratiques : `v_articles` (articles avec leurs tags en une colonne), `v_tags` (tags avec leurs effectifs).

## Version Markdown des articles

Chaque article a une version Markdown, dans la colonne `articles.texte_markdown` et dans
`data/markdown/<publication>/<article>.md`. Les fichiers commencent par un en‑tête YAML lisible
par les générateurs de sites (Jekyll, Hugo, Eleventy…) et par Obsidian :

```yaml
---
title: "Économie : L’affirmation de l’impérialisme chinois et la radicalisation de la politique américaine approfondissent la décomposition du capitalisme"
id: "NS-096-04"
date: 2026-02-28
publication: "NS-096"
serie: "nouvelle"
type_publication: "numero"
numero: "96"
numero_cumule: 178
tags: ["chine", "crise", "noteseco", "usa"]
tags_libelles: ["Chine", "Crise du Capitalisme", "Situation Economique", "Etats-Unis"]
url_pdf_publication: "http://socialisme.free.fr/bulletin_cps_archives/2026_02_28_cps_96_178as.pdf"
page_debut: 12
texte_disponible: true
texte_type: "pages_numero"
texte_source: "http://socialisme.free.fr/bulletin_cps_archives/2026_02_28_cps_96_178as.pdf pages 12-17 (pdf_texte ; du titre de l'article à celui de l'article suivant, découpage automatique)"
---
```

Conventions : `##` titre tel qu'affiché dans le document, `###` intertitre, `>` citation, `-`
liste, `*italique*`, `**gras**`, `[^1]` notes de bas de page, tableaux. Le titre de l'article
lui‑même est dans l'en‑tête (`title`), pas dans le corps. Les articles sans texte ont un fichier
avec leur en‑tête et un renvoi au PDF.

Comment le Markdown est obtenu :

- **pages HTML du site** (334 articles) : exports Word convertis en s'appuyant sur la charte de
  CPS (styles `intertitre`, `citation`, `titre`… et feuille de style), notes Word converties en
  notes Markdown, menus et bandeaux du site retirés ;
- **PDF à couche texte** (numéros récents, suppléments) : polices, tailles, gras et italique lus
  avec `pdftohtml -xml` ; paragraphes reconstitués (interlignes, retraits, colonnes), en‑têtes
  courants, numéros de page et sommaires de une retirés ;
- **PDF scannés** (OCR) : paragraphes de Tesseract recousus aux sauts de colonne, intertitres en
  capitales reconnus, bruit (filets, taches) écarté ;
- partout, les **césures** de fin de ligne sont recollées d'après le vocabulaire du corpus
  (« mar‑quées » → « marquées », mais « Jospin‑Gayssot » reste composé) ;
- puis le **nettoyage** ([`scripts/nettoyage.py`](scripts/nettoyage.py)), sur les pages puis sur
  chaque article découpé :
  - bruit éditorial retiré : bulletins d'abonnement, mentions légales (directeur de la
    publication, commission paritaire, ISSN), coordonnées et pieds de page du site, liens de
    navigation (« Retour à l'accueil »), renvois « suite page 4 », en‑têtes courants restés dans
    le texte, bandeau de une (« Comité pour la construction… », devise), annonces de brochures,
    sommaires imprimés, traînées de caractères que l'OCR a lues dans les filets et les points de
    conduite ;
  - intertitres : vides ou illisibles supprimés, coupés en plusieurs blocs recollés, paragraphes
    pris pour des intertitres (30 mots et plus, phrases complètes) rendus au texte, dates et
    mentions « Article paru dans… » rendues au texte, lettrines recollées (« **G**uerre » →
    « Guerre ») ou rétablies quand l'OCR les a perdues (« es projets de loi » → « Les projets de
    loi », d'après les débuts de phrase du corpus) ; dans chaque article, `##` est réservé au
    titre et les intertitres du corps sont décalés d'un niveau.

Contrôles : les 1 175 textes sont rendus par un moteur CommonMark sans aucune emphase cassée,
les 1 293 en‑têtes YAML sont valides, et pour chaque page la part des mots du texte brut retrouvés
dans le Markdown est vérifiée (les 44 pages PDF mal reconstruites, sur environ 3 500, ont été
refaites à partir du texte brut). Le rapport de qualité compte à chaque construction le bruit
qui subsiste (bulletins, mentions légales, en‑têtes, faux intertitres…). Limites : les textes
océrisés gardent des erreurs de reconnaissance (« Île » pour « le », colonnes parfois mêlées),
et le découpage automatique des numéros peut déborder sur l'article voisin, en particulier
quand le sommaire du site omet un article du numéro.

### Mesures avant et après le nettoyage et le nouveau découpage

Nombre d'articles concernés, sur l'ensemble des textes (1 086 textes avant, 1 175 après) :

| Défaut | Avant | Après |
|---|---|---|
| Bulletin d'abonnement dans le texte | 106 | 0 |
| Mentions légales (directeur de la publication, commission paritaire) | 202 | 1 |
| Pied de page ou coordonnées du site | 164 | 4 |
| Liens de navigation (« Retour à l'accueil ») | 130 | 0 |
| En‑tête de page resté dans le texte | 75 | 28 |
| Renvoi « suite page N » | 16 | 0 |
| Bandeau de une (« Comité pour la construction… ») | 21 | 0 |
| Lettrine cassée (« **G**uerre ») | 10 | 0 |
| Intertitre sans lettre (« ## • ») | 164 | 0 |
| Intertitre de plus de 20 mots | 437 | 402 |
| « ## » ailleurs que dans le titre | 201 | 0 |
| Texte commençant au milieu d'une phrase | 20 | 10 |
| Texte découpé sur 12 pages ou plus (avant : coupé par une limite de 12 pages) | 73 | 47 |

Découpage : 90 articles ont désormais un texte (rubriques « Les militants interviennent »,
articles retrouvés grâce au sommaire imprimé), 16 commencent à une page corrigée (titre repris
en une, ou intertitre de conclusion, auparavant pris pour le début) ; un seul texte a disparu,
qui n'était en fait qu'un morceau de sommaire. Les longs intertitres restants sont pour la
plupart de vrais intertitres de CPS, souvent des phrases entières.

Relecture par des agents Haiku (même consigne, mêmes 58 articles tirés au sort, note de 0 à 5) :
moyenne 3,14 avant, 3,26 après (15 articles mieux notés, 34 inchangés, 9 moins bien) ; textes
d'articles en PDF 3,4 → 4,2, découpages des numéros 2,8 → 2,9, suppléments 3,0 → 3,1, pages
HTML 3,4 → 3,3. Les baisses ont été vérifiées : sauf un paragraphe retiré à tort (corrigé
depuis), les passages en cause sont identiques avant et après ; l'écart vient de la variabilité
de la notation. Cette relecture a porté sur la version qui précède les dernières retouches
qu'elle a suggérées (puces converties en listes, sommaires HTML retirés, révisions Word).

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
WHERE articles_fts MATCH 'echelle AND mobile AND salaires' ORDER BY a.date;

-- Le texte Markdown d'un article
SELECT texte_markdown FROM articles WHERE id = 'NS-022-07';

-- Seulement dans les titres
SELECT a.id, a.date, a.titre FROM articles_fts f JOIN articles a ON a.rowid = f.rowid
WHERE articles_fts MATCH 'titre:bolivie' ORDER BY a.date;

-- Phrase exacte dans toutes les pages de tous les numéros (cps_complet.sqlite)
SELECT p.publication_id, p.page, snippet(pages_fts, 0, '[', ']', '…', 12)
FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid
WHERE pages_fts MATCH '"gouvernement ouvrier et paysan"' ORDER BY p.publication_id;
```

Avec Python : `sqlite3.connect("data/cps.sqlite")`, ou avec pandas
`pd.read_csv("data/csv/articles.csv")`. Les fichiers CSV s'ouvrent aussi dans un tableur.

## Explorateur web

**En ligne : <https://jauj.github.io/socialisme-ou-barbarie-site/>** (GitHub Pages, branche
`gh-pages`).

`explorateur/index.html` permet de parcourir la base et de **lire les articles** :

- **recherche dans le texte intégral** des articles : tous les mots sont requis,
  `"expression exacte"` entre guillemets (ou « … »), préfixe `trotsk*`, exclusion `-mot`, sans
  accents ni casse ; résultats triés par pertinence (BM25, titres favorisés) et combinables avec
  les autres filtres. Elle interroge `data/recherche.sqlite` directement dans le navigateur
  ([sql.js-httpvfs](https://github.com/phiresky/sql.js-httpvfs), copie dans
  `explorateur/vendor/`), qui ne télécharge que les pages de l'index nécessaires (requêtes HTTP
  Range : 150 ko environ pour une recherche) ;
- recherche instantanée dans les titres, filtres par série, type, tag, numéro, période ;
- **lecteur** : la version Markdown mise en forme, les termes recherchés surlignés (bouton
  « Occurrence suivante »), boutons et flèches ← → pour passer à l'article précédent ou suivant
  (dans la liste affichée, ou à défaut dans le numéro), liens vers le PDF à la bonne page ;
- **vue d'un numéro** (lien sur le nom du numéro, ou `#pub=NS-065`) : ses articles dans l'ordre
  du sommaire, la date imprimée en une quand elle diffère de celle du site ;
- chaque état a une adresse partageable, par exemple
  `…/explorateur/#qt=%22front+unique%22&lire=NS-022-07`.

Tags : ceux de l'index thématique du site en clair, ceux déduits du titre en italique, ceux
déduits du texte intégral en pointillé.

En local, il faut un serveur qui accepte les requêtes HTTP Range (ce que ne fait pas
`python3 -m http.server`) : `python3 scripts/serveur.py` à la racine du dépôt, puis
<http://localhost:8000/explorateur/>.

## Reconstruire la base

Python 3.9+ avec `beautifulsoup4` et `markdownify`, et `poppler-utils` (pdftotext, pdftoppm,
pdfimages, pdftohtml) ; `tesseract-ocr` pour l'OCR, de préférence avec le modèle français
« best » (`fra.traineddata` de *tessdata_best*, plus précis que celui des distributions), passé
par `--tessdata <dossier>`.

```sh
pip install -r requirements.txt
python3 scripts/fetch_sources.py      # sommaire + index thématique → sources/ (--refresh pour mettre à jour)
python3 scripts/build_db.py           # → data/ (sans réseau)
python3 scripts/fetch_textes.py       # textes des articles HTML/PDF → data/textes/
python3 scripts/extraire_pages.py --tessdata DOSSIER   # texte des PDF de numéros (OCR des scans, long) → data/pages/
python3 scripts/extraire_markdown.py  # versions Markdown des pages et des articles
python3 scripts/build_db.py           # reconstruction avec les textes
python3 -m unittest discover -s tests -t .   # tests de non-régression
```

`build_db.py` ne fait aucun accès réseau et n'utilise que la bibliothèque standard de Python
(plus `markdownify`/`beautifulsoup4` pour des fonctions partagées) : la base se régénère en
environ 5 minutes à partir de `data/pages/`, `data/textes/`, `data/corrections_ocr/` et `config/`
(découpage des articles, nettoyage de chacun avec `scripts/nettoyage.py`, dates et tags déduits
des textes avec `scripts/metadonnees.py`) ; `--sans-complet` saute `cps_complet.sqlite`, trop
volumineux pour être versionné. `extraire_markdown.py` (environ 5 minutes quand les PDF sont en
cache, option `--garder-pdf`) applique le même nettoyage aux pages et aux textes propres aux
articles. `extraire_pages.py --refaire-ocr` refait l'OCR des numéros scannés déjà traités et
garde, page par page, la version la plus lisible.

Pour intégrer un nouveau numéro : `fetch_sources.py --refresh`, `fetch_textes.py`,
`extraire_pages.py`, `extraire_markdown.py`, puis `build_db.py`.

**Intégration continue.** À chaque envoi sur la branche `main`, GitHub Actions
([`.github/workflows/construction.yml`](.github/workflows/construction.yml)) lance les tests,
reconstruit la base et publie le site sur la branche `gh-pages` (sources, base, Markdown, CSV et
JSON construits). Les demandes de fusion sont testées et construites sans publication ; le
workflow peut aussi être lancé à la main (onglet *Actions*). Les tests portent sur le nettoyage
du Markdown, le découpage des articles, la reconstitution des paragraphes, les dates et les
tags déduits des textes, et la construction de la base.

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
