# Rapport de qualité

Généré automatiquement par `scripts/build_db.py`. Ne pas modifier à la main.

## Statistiques

| Élément | Nombre |
|---|---|
| Publications (total) | 382 |
| — numéros, bulletin 1984 | 2 |
| — numéros, ancienne série | 81 |
| — numéros, nouvelle série | 98 |
| — numéros spéciaux | 1 |
| — hors-séries | 7 |
| — suppléments | 193 |
| Articles | 1309 |
| — dont ajoutés depuis l'index thématique (absents du sommaire) | 0 |
| — dont ajoutés d'après le sommaire imprimé du numéro (absents du site) | 15 |
| — avec lien HTML | 334 |
| — avec lien PDF propre ou page de PDF | 335 |
| — avec texte intégral (page HTML ou PDF propre) | 401 |
| — avec texte intégral (PDF de la publication) | 148 |
| — avec texte découpé dans le PDF du numéro (titre → article suivant) | 735 |
| — avec texte (total, Markdown et brut) | 1284 |
| — page de début indiquée par le site | 80 |
| — page de début donnée par le sommaire imprimé en une | 266 |
| — page de début retrouvée par le titre | 456 |
| — premier article du sommaire, non retrouvé : début de la première page | 23 |
| — page de début retrouvée par relecture (config/articles_pdf.json) | 132 |
| — page de début retrouvée par le début du texte (page HTML ou PDF de l'article) | 122 |
| — texte découpé dont la fin est incertaine (article suivant non retrouvé) | 18 |
| Publications dont le texte intégral est disponible (pages) | 350 |
| — dont océrisées (scans) | 177 |
| Pages de texte | 7688 |
| Tags | 118 |
| Associations article-tag (index du site) | 1535 |
| Associations article-tag (règles sur les titres) | 1268 |
| Associations article-tag (déduites du texte intégral) | 1592 |
| Publications dont la date imprimée en une a été lue | 307 |
| Articles dont la date de rédaction a été lue (fin du texte) | 536 |
| Articles sans aucun tag | 5 |

## Texte des articles : contrôles

Nombre d'articles dont le texte Markdown présente encore le défaut (après nettoyage).

| Contrôle | Articles |
|---|---|
| Articles avec texte | 1284 |
| Bulletin d'abonnement | 0 |
| Mentions légales (directeur de la publication, commission paritaire, ISSN) | 1 |
| En-tête de page resté dans le texte (« C.P.S. … – page N ») | 0 |
| Lien de navigation du site | 0 |
| Intertitre sans lettre | 0 |
| Intertitre de 30 mots ou plus | 52 |
| « ## » ailleurs qu'en tête (réservé au titre) | 0 |
| Texte commençant au milieu d'une phrase (minuscule) | 24 |

## Dates

Date lue dans l'en-tête de la une (premières lignes de la page 1), comparée à la date donnée par le site. Les écarts ne sont pas corrigés : ils sont à vérifier sur le PDF.

| Comparaison | Publications |
|---|---|
| identique | 250 |
| jour différent | 27 |
| identique (mois) | 19 |
| date différente | 9 |
| mois différent | 2 |

| Publication | Date du site | Date imprimée | Lu en une | Écart |
|---|---|---|---|---|
| `AS-007-S1` | 1986-01-18 | 1986-02-15 | 15 février 1986 | date différente |
| `AS-012-S2` | 1986-12-08 | 1986-10-23 | 23 octobre 1986 | date différente |
| `AS-014-S1` | 1987-01-27 | 1986-09-00 | Septembre 1986 | mois différent |
| `AS-016` | 1987-05-03 | 1986-12-08 | 8 décembre 1986 | date différente |
| `AS-024-S1` | 1988-11-20 | 1988-11-13 | 13 NOVEMBRE 1988 | jour différent |
| `AS-048-S1` | 1993-06-20 | 1993-05-31 | 31 MAI 1993 | date différente |
| `AS-079` | 1999-10-01 | 1999-09-25 | 25 SEPTEMBRE 1999 | date différente |
| `NS-012` | 2003-05-22 | 2003-05-31 | 31 MAI 2003 | jour différent |
| `NS-017` | 2004-10-01 | 2004-10-17 | 17 OCTOBRE 2004 | jour différent |
| `NS-032` | 2008-03-31 | 2008-03-29 | 29 MARS 2008 | jour différent |
| `NS-033-S1` | 2008-05-17 | 2008-05-31 | 31 MAI 2008 | jour différent |
| `NS-038` | 2009-09-09 | 2009-10-09 | 9 OCTOBRE 2009 | date différente |
| `NS-046` | 2012-04-19 | 2012-04-18 | 18 AVRIL 2012 | jour différent |
| `HS-2012-05-27` | 2012-05-27 | 2012-06-25 | 25 juin 2012 | date différente |
| `NS-049` | 2013-01-14 | 2013-01-15 | 15 janvier 2013 | jour différent |
| `NS-053-S1` | 2014-03-18 | 2014-03-16 | 16 mars 2014 | jour différent |
| `NS-063` | 2016-11-12 | 2016-12-07 | 7 DÉCEMBRE 2016 | date différente |
| `NS-067-S2` | 2018-02-09 | 2018-02-19 | 19 février 2018 | jour différent |
| `NS-071-S1` | 2018-12-11 | 2018-12-12 | 12 décembre 2018 | jour différent |
| `NS-072-S4` | 2019-04-18 | 2019-04-19 | 19 avril 2019 | jour différent |
| `NS-072-S5` | 2019-05-05 | 2019-05-06 | 6 mai 2019 | jour différent |
| `NS-072-S7` | 2019-05-10 | 2019-05-11 | 11 mai 2019 | jour différent |
| `NS-073-S4` | 2019-09-22 | 2019-09-25 | 25 septembre 2019 | jour différent |
| `NS-074-S1` | 2019-10-07 | 2019-10-09 | 9 octobre 2019 | jour différent |
| `NS-075-S1` | 2019-12-26 | 2019-12-23 | 23 DÉCEMBRE 2019 | jour différent |
| `NS-075-S2` | 2020-01-08 | 2020-01-07 | 7 janvier 2020 | jour différent |
| `NS-076-S5` | 2020-05-28 | 2020-05-17 | 17 mai 2020 | jour différent |
| `NS-085-S5` | 2023-02-24 | 2023-02-23 | 23 février 2023 | jour différent |
| `NS-086` | 2023-03-01 | 2023-03-02 | 02 MARS 2023 | jour différent |
| `NS-088` | 2023-09-29 | 2023-09-27 | 27 septembre 2023 | jour différent |
| `NS-090-S4` | 2024-04-19 | 2024-04-29 | 29 avril 2024 | jour différent |
| `NS-091-S1` | 2024-06-22 | 2024-06-21 | 21 juin 2024 | jour différent |
| `NS-093-S1` | 2025-03-21 | 2025-02-00 | FÉVRIER 2025 | mois différent |
| `NS-093-S4` | 2025-05-06 | 2025-05-08 | 8 mai 2025 | jour différent |
| `NS-094-S2` | 2025-06-22 | 2025-06-24 | 24 juin 2025 | jour différent |
| `NS-094-S4` | 2025-09-16 | 2025-09-15 | 15 septembre 2025 | jour différent |
| `NS-097` | 2026-04-30 | 2026-04-06 | 6 avril 2026 | jour différent |
| `NS-097-S1` | 2026-06-01 | 2026-05-30 | 30 mai 2026 | date différente |

### Dates de rédaction éloignées de la date de publication (8)

Date qui clôt le texte postérieure de plus de 15 jours à la date de la publication, ou antérieure de plus de 400 jours : date de publication erronée, texte republié, ou texte rattaché au mauvais numéro.

- `AS-002-S1-01` : rédigé le 1985-09-10, publication du 1985-05-09 (+124 j) — Numéro spécial « Aux militants du P.C.I. » - 9 mai 1985
- `AS-016-02` : rédigé le 1987-04-24, publication du 1986-12-08 (+137 j) — Défense de la Sécurité Sociale
- `AS-016-05` : rédigé le 1987-04-21, publication du 1986-12-08 (+134 j) — Déclaration du groupe "Que faire"
- `AS-044-04` : rédigé le 1993-05-28, publication du 1992-10-03 (+237 j) — La crise du syndicalisme (I: La crise des syndicats ouvriers: une réalité qui fait couler 
- `AS-045-04` : rédigé le 1993-05-28, publication du 1992-12-05 (+174 j) — La crise du syndicalisme (II: les réponses de la direction de la CGT)
- `AS-046-04` : rédigé le 1993-05-28, publication du 1993-02-04 (+113 j) — La crise du syndicalisme ( III: Aux origines de la CGT-FO. IV: FO des "trente glorieuses" 
- `NS-005-02` : rédigé le 2002-10-11, publication du 2001-10-12 (+364 j) — Editorial
- `NS-038-04` : rédigé le 2009-11-03, publication du 2009-10-09 (+25 j) — L'enjeu du 49ème congrès de la CGT : combattre l'orientation du "syndicalisme rassemblé" d

## Anomalies

### Entrées sans mention « Nouvelle Série » rattachées à la nouvelle série d'après leur date (2)

- `2022-03-01|supp|82` : mention « Nouvelle Série » absente sur le site ; série déduite de la date
- `2022-01-26|supp|81` : mention « Nouvelle Série » absente sur le site ; série déduite de la date

### Numéros listés plusieurs fois dans le sommaire (21)

- `NS-013` : entrée du 2003-09-19 requalifiée en supplément : Pour briser l'offensive du gouvernement Chirac-Raffarin …
- `NS-015` : entrée du 2004-04-15 requalifiée en supplément : Comment faire face à l'offensive ultra-réactionnaire du gouvernement Chirac-Raff
- `NS-018` : entrée du 2005-03-11 requalifiée en supplément : Après le 10 mars, l’ennemi qu’il faut combattre et défaire, c’est le gouvernemen
- `NS-022` : entrée du 2005-09-23 requalifiée en supplément : Faire face à l’offensive redoublée du gouvernement UMP Chirac-Villepin-Sarkozy e
- `NS-022` : entrée du 2005-11-12 requalifiée en supplément : Après l’armée à la SNCM, les juges à la RTM, l’état d’urgence ! L’ennemi qu’il f
- `NS-026` : entrée du 2006-10-30 requalifiée en supplément : Supplément à CPS du 30 octobre 06 : pour le retrait du projet de loi sur le « di
- `NS-030` : entrée du 2007-09-15 requalifiée en supplément : Pour faire face et stopper l’offensive redoublée du gouvernement : Rupture des «
- `NS-030` : entrée du 2007-10-13 requalifiée en supplément : Pour sauver les acquis les plus fondamentaux, il faut combattre et vaincre le go
- `NS-031` : entrée du 2008-02-23 requalifiée en supplément : Faire barrage au gouvernement Sarkozy-Fillon
- `NS-034` : entrée du 2008-10-04 requalifiée en supplément : Le capitalisme en faillite entraîne le monde au bord du gouffre : On ne peut all
- `NS-036` : entrée du 2009-01-31 requalifiée en supplément : 2 millions et plus de manifestants contre le gouvernement Sarkozy-Fillon et le M
- `NS-037` : entrée du 2009-05-16 requalifiée en supplément : Pour en finir avec les licenciements, les suppressions de postes, les contre-réf
- `NS-038` : entrée du 2009-09-13 requalifiée en supplément : Un projet de budget ultra-réactionaire devant le Parlement. Il faut exiger des d
- `NS-064` : entrée du 2017-01-20 requalifiée en supplément : Brésil, Congrès de la CNTE (Entretien avec un militant brésilien, après le congr
- `NS-067` : entrée du 2018-01-26 requalifiée en supplément : Universités : La loi dite « pour l'Orientation et la Réussite des Étudiants » (O
- `NS-067` : entrée du 2018-02-09 requalifiée en supplément : Fonction publique : Comité inter ministériel du 1er Février : le gouvernement a 
- `NS-078` : entrée du 2021-04-20 requalifiée en supplément : Déclaration de « Maghreb socialiste » sur la situation en Algérie
- `NS-078` : entrée du 2021-05-13 requalifiée en supplément : Déclaration sur la Palestine
- `NS-079` : entrée du 2021-08-28 requalifiée en supplément : Déclaration sur l'Afghanistan
- `NS-089` : entrée du 2024-02-18 requalifiée en supplément : Palestine - Communiqué du Groupe pour la construction du Parti ouvrier révolutio
- `NS-091` : entrée du 2024-05-22 fusionnée avec le numéro (1 article(s))

### Liens morts sur le site (0)


### Entrées de l'index thématique non rattachées (0)

