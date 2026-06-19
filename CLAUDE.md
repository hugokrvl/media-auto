# MediaAuto (HK Média) — Documentation complète

Pipeline automatisé de **veille média → analyse IA → dataviz de marque → posts réseaux sociaux**,
avec **validation humaine** avant publication. Tourne chaque nuit à 1h (Paris) via GitHub Actions.

> Objectif : 5-7 posts/jour de qualité (finance, tech, actu, sport, fact-check), au format
> visuel unique « HK Média », validés d'un clic le matin sur un site de planning.

---

## Sommaire
1. [Architecture & flux](#1-architecture--flux)
2. [Structure du dépôt](#2-structure-du-dépôt)
3. [Services & comptes](#3-services--comptes-tous-gratuits)
4. [Limites Groq & architecture 2 modèles](#4-limites-groq--architecture-2-modèles)
5. [Sources (RSS · YouTube · Email)](#5-sources--pipelinesourcespy)
6. [Dédup intelligent](#6-dédup-intelligent--pipelinededuppy)
7. [Identité visuelle HK Média](#7-identité-visuelle--charte-hk-média) (dataviz + Breaking News + images libres + **résultats sportifs §7.3**)
8. [Base de données Supabase](#8-base-de-données-supabase)
9. [Site de planning](#9-site-de-planning-docs--github-pages)
10. [Variables d'environnement / secrets](#10-variables-denvironnement--secrets)
11. [Tests locaux](#11-tests-locaux)
12. [Ordre de mise en place](#12-ordre-de-mise-en-place)
13. [Roadmap / Phase 2](#13-roadmap--phase-2)

---

## 1. Architecture & flux

```
GitHub Actions (cron 23:00 UTC = 1h Paris)
  → pipeline/main.py  (orchestrateur)
      1. scraper.py        RSS + YouTube + Email → articles des dernières 24h
      2. analyzer.py       Groq → score, vérification, tri, données structurées
      2bis. dedup.py       new / duplicate / update (vs historique 14 j)
      3. dataviz.py        matplotlib → PNG 1080×1080 (charte HK)
      4. generator.py      Groq → captions FR par réseau (X / Instagram / LinkedIn)
      5. storage.py        Supabase (table posts + bucket post-images)
      6. notifier.py       ntfy → notification push téléphone
  → docs/ (GitHub Pages)   ← VALIDATION HUMAINE (bouton « Approuver »)
  → poster/                ← publication après approbation (X/IG/LinkedIn)

GitHub Actions (cron 15 min)  ← 2e entrée, indépendante
  → pipeline/reprocess.py  régénère les posts dont une transcription a été collée
                           sur le site (digest 8b + enrichissement 70b) — voir §9.1

GitHub Actions (cron 30 min, 17h→02h UTC)  ← 3e entrée, indépendante
  → pipeline/sports/sports_main.py  résultats sportifs : 1 post/championnat/jour
                           publié quand TOUS les matchs du jour sont finis — voir §7.3

GitHub Actions (cron 21h30 UTC, lun-ven)  ← 4e entrée, indépendante
  → pipeline/markets/markets_main.py  clôture des marchés : 1 post/jour
                           (indices + BTC + Or via Yahoo Finance) — voir §7.4

GitHub Actions (cron lun-ven / sam / dim)  ← 5e entrée, indépendante
  → pipeline/markets/markets_extra.py  Top/Flop actions (jour/semaine)
                           + sentiment VIX & crypto le dimanche — voir §7.5
```

Le pipeline **génère et stocke** les posts en statut `pending`. Rien n'est publié
automatiquement : l'utilisateur approuve chaque post sur le site avant mise en ligne.

---

## 2. Structure du dépôt

```
media-auto/
├── .github/workflows/
│   ├── daily_scan.yml     # cron nocturne (pipeline complet) + workflow_dispatch
│   ├── reprocess.yml      # retraitement transcriptions collées (toutes les 15 min)
│   ├── sports_results.yml # résultats sportifs (toutes les 30 min, 17h→02h UTC) — voir §7.3
│   ├── markets_close.yml  # clôture des marchés (21h30 UTC, lun-ven) — voir §7.4
│   └── markets_extra.yml  # Top/Flop actions + sentiment (lun-ven/sam/dim) — voir §7.5
├── pipeline/
│   ├── main.py            # orchestrateur (boucle, dédup, max 7 posts/nuit)
│   ├── reprocess.py       # regénère un post depuis une transcription collée
│   ├── sources.py         # liste centralisée des sources (rss/youtube/email)
│   ├── scraper.py         # récupération + dispatch par type de source
│   ├── youtube.py         # résolution chaîne→flux + transcription (+ repli desc.)
│   ├── email_sources.py   # lecture newsletters IMAP + cascade de filtres
│   ├── analyzer.py        # Groq : score / tri / données chart structurées
│   ├── dedup.py           # doublon vs mise à jour (empreintes sujet + données)
│   ├── dataviz.py         # moteur d'infographies HK (5 types)
│   ├── brand.py           # charte : couleurs, polices, helpers (fr(), variations())
│   ├── generator.py       # Groq : captions FR adaptées par réseau
│   ├── storage.py         # client Supabase (insert post + upload image + historique)
│   ├── notifier.py        # ntfy push
│   ├── _fonts/            # polices OFL bundlées (DM Serif Display, Anton, Barlow)
│   ├── validate_sources.py# OUTIL : teste chaque flux en réel
│   ├── gallery.py         # OUTIL : planche-contact de tous les designs
│   ├── make_preview.py    # OUTIL : aperçu du site de planning (PNG)
│   ├── _test_*.py         # tests offline (dedup, email, youtube) — voir §11
│   ├── sports/            # MODULE résultats sportifs (flux indépendant) — voir §7.3
│   │   ├── sports_main.py     # orchestrateur (1 post/championnat/jour quand tout est fini)
│   │   ├── api_client.py      # client API-Sports (foot/basket/F1/rugby) + ESPN (sans clé)
│   │   ├── leagues.py         # config championnats suivis + saisons courantes
│   │   └── scores_renderer.py # rendu PIL des posts scores + podium F1 (+ portrait vainqueur)
│   └── markets/           # MODULE marchés (flux indépendant) — voir §7.4 / §7.5
│       ├── markets_main.py     # clôture des indices (1 post/jour, Yahoo Finance)
│       ├── markets_extra.py    # Top/Flop actions (jour/semaine) + sentiment VIX/crypto
│       └── markets_renderer.py # rendus PIL (clôture, top/flop, sentiment)
├── docs/                  # SITE de planning (GitHub Pages) : index.html, app.js, style.css
├── poster/                # publication réseaux (phase ultérieure)
├── requirements.txt
├── .env.example           # modèle de config (committé, SANS secrets)
├── .env                   # secrets réels — IGNORÉ par git, JAMAIS committé
└── CLAUDE.md              # ce fichier
```

> ⚠️ **Environnement de dev** : Windows + PowerShell. Pour les scripts qui affichent
> des emojis/accents, préfixer par `$env:PYTHONIOENCODING="utf-8"` (sinon `UnicodeEncodeError`).

---

## 3. Services & comptes (tous gratuits)

| Service | Usage | Variable(s) |
|---------|-------|-------------|
| **Groq** | LLM analyse + génération | `GROQ_API_KEY` |
| **Supabase** | DB posts + stockage images | `SUPABASE_URL`, `SUPABASE_KEY` |
| **GitHub Actions** | Cron nocturne | — |
| **GitHub Pages** | Site de planning (`/docs`) | — |
| **ntfy.sh** | Notifications push | `NTFY_TOPIC` |
| **Email (IMAP)** | Newsletters | `NEWSLETTER_EMAIL`, `NEWSLETTER_PASSWORD` |
| **X / Instagram / LinkedIn** | Publication (phase 2) | voir §10 |

### Groq — https://console.groq.com
- API Keys → New key. Modèles utilisés : voir §4.
- ⚠️ Clé de service uniquement dans les secrets, jamais dans le code committé.

### Supabase — https://supabase.com
- New project (nom `mediaauto`, région West EU / Ireland pour la latence France).
- Schéma de table + bucket : voir §8.
- ⚠️ La clé `service_role` (legacy JWT) va dans les secrets GitHub ; la clé `anon`
  (legacy JWT, lecture publique) va dans `docs/app.js`. Les nouvelles clés
  `sb_secret_…` ne sont PAS supportées par supabase-py 2.7.4 → utiliser les
  **clés JWT legacy** (Settings → API → onglet *Legacy API keys*).

### ntfy — https://ntfy.sh
- Installer l'app, s'abonner à un topic unique (ex. `mediaauto-hugo-2024`).
- Test : `curl -d "Test" ntfy.sh/mediaauto-hugo-2024`.

---

## 4. Limites Groq & architecture 2 modèles

**Limites du compte gratuit** (vérifier les siennes : console.groq.com/settings/limits) :

| Modèle | Req/min | Req/jour | **Tokens/min** | **Tokens/jour** | Usage |
|--------|--------:|---------:|---------------:|----------------:|-------|
| `llama-3.3-70b-versatile` | 30 | 1 000 | **12 000** | **100 000** | qualité (génération finale) |
| `llama-3.1-8b-instant` | 30 | 14 400 | 6 000 | **500 000** | volume (triage) |
| `whisper-large-v3` | 20 | 2 000 | — | 28 800 s audio/jour | transcription audio (phase 2) |

**Le goulot, ce sont les TOKENS**, pas les requêtes (surtout 100k/jour sur le 70b).

### Architecture à 2 modèles (✅ IMPLÉMENTÉE)

Analyser 60 articles/nuit avec le 70b ≈ **~96-107k tokens/jour** → dépasserait les
100k/jour gratuits. `analyzer.py` fonctionne donc en **2 passes** :

| Passe | Modèle | Rôle |
|-------|--------|------|
| **1. Triage** des ~60 articles | `llama-3.1-8b-instant` | score / vérif / catégorie / garder-jeter (sortie minimale) |
| **1bis. Digest vidéo** (si transcription) | `llama-3.1-8b-instant` (`GROQ_DIGEST_MODEL`) | compresse la transcription complète en résumé dense en données |
| **2. Enrichissement** des ≤12 retenus | `llama-3.3-70b-versatile` | titre FR, sous-titre, type de graphique + données (max 500 tokens) |
| **3. Captions** (X / Instagram / LinkedIn) | `llama-3.1-8b-instant` (`GROQ_CAPTION_MODEL`) | textes adaptés par réseau (max 600 tokens) |

Le 70b est réservé à l'enrichissement structuré uniquement — les captions basculent
sur le 8b (500k/jour) pour économiser le quota. Consommation 70b estimée : ~12k/100k/jour.

> ⚠️ **TODO — qualité captions** : les captions sont actuellement sur `llama-3.1-8b-instant`
> pour économiser le quota 70b (on avait dépassé 100k/jour en testant plusieurs runs le même jour).
> En production normale (1 run/nuit), la conso 70b serait ~12k → quota largement suffisant.
> **Repasser `GROQ_CAPTION_MODEL` sur `llama-3.3-70b-versatile`** dans `generator.py` dès que
> la qualité des captions 8b semble insuffisante, ou si le quota n'est jamais atteint en pratique.

**Digest vidéo (map-reduce)** — une transcription d'1h ≈ 13k tokens, trop gros pour le
70b (100k/jour). On la « digère » d'abord avec le modèle pas cher (500k/jour) : découpe
en morceaux → extraction des seules DONNÉES (chiffres, %, montants, dates) → résumé
condensé (~1200 car.). Le 70b ne voit que ce digest → **toutes les données de la vidéo
captées, tokens du 70b préservés**. Plafonné à `GROQ_MAX_DIGEST` (5) vidéos/nuit, et
seulement pour les vidéos qui passent le triage. Pour des vidéos très longues, mettre un
modèle à plus haut TPM (ex. `meta-llama/llama-4-scout-17b-16e-instruct`, 30k TPM) via
`GROQ_DIGEST_MODEL`.

Garde-fous tokens (tous en place) :
- **Pacing** entre appels Groq (`PACE_SECONDS`, défaut 2,2 s) + **back-off** exponentiel sur rate-limit (`_chat`).
- Transcription vidéo gardée complète (≤ 20 000 car.) mais **digérée** par le modèle pas
  cher avant le 70b (map-reduce) → le 70b ne voit qu'un condensé (~1200 car.).
- Résumés d'articles tronqués (350 car. au triage, 600 à l'enrichissement).
- Filtres email **avant** Groq (voir §5) → ~45 % d'appels en moins.
- Envois **séquentiels**.

Réglages par env : `GROQ_TRIAGE_MODEL`, `GROQ_MODEL`, `GROQ_DIGEST_MODEL`,
`GROQ_MAX_ANALYZE` (60), `GROQ_MAX_ENRICH` (12), `GROQ_MAX_DIGEST` (5),
`GROQ_DIGEST_CHARS` (14000), `GROQ_PACE_SECONDS` (2.2), `GROQ_SCORE_KEEP` (6).
Test offline (mock, sans réseau) : `python _test_analyzer.py`.

---

## 5. Sources (`pipeline/sources.py`)

Chaque source porte un champ `type` (défaut `"rss"`) :

| Type | Champ requis | Comportement |
|------|--------------|--------------|
| `rss` | `url` | Flux RSS/Atom classique (`feedparser`) |
| `youtube` | `url` (page de chaîne) | Résout le flux → titre + description (+ transcription si possible) |
| `email` | — | Lit les newsletters de la boîte IMAP dédiée |

**Ajouter une source** = ajouter un dict dans `SOURCES`, puis **valider** :
```bash
cd pipeline && python validate_sources.py   # teste chaque flux en réel (RSS + YouTube)
```
**État validé : 30/30 sources OK.** Beaucoup de médias FR (Reuters, Les Échos,
Boursorama, RMC…) n'ont plus de flux RSS natif fonctionnel → on passe par
**Google News** via le helper `_gn("site:domaine.fr when:1d")` (articles récents du
domaine, fiable, toujours à jour ; les URLs d'articles sont alors des liens
news.google.com, sans impact sur l'analyse — le nom du média affiché reste le vrai).
Flux natifs conservés là où ils marchent (CoinDesk, FT, WSJ, BBC, Le Monde, 01net,
L'Équipe via `dwh.lequipe.fr`, Le Parisien, Ouest-France, Numerama, The Verge…).

**Équilibrage (`scraper.py`)** : certains flux renvoient 100 articles. Pour éviter
qu'une source noie les autres dans les 60 analysés, le scraper **plafonne à
`SCRAPER_MAX_PER_SOURCE` (12) articles/source** puis **entrelace** les sources en
round-robin → les 60 premiers couvrent toutes les catégories.

### 5.1 YouTube (`youtube.py`)
- Le flux RSS YouTube exige un `channel_id` (UC…) : `resolve_feed()` le déduit en
  lisant la page de la chaîne (`@handle`, `/c/Nom`, `/channel/UC…`), avec cache.
  **Testé OK** sur Chéron, Baccino, Stefani, Hasheur.
- **Transcription** (`youtube-transcript-api`) : code compatible API **0.x et 1.x**
  (`get_transcript` classmethod OU instance `.fetch()`). ⚠️ souvent **bloquée depuis
  GitHub Actions** (YouTube bannit les IP datacenter) → repli automatique sur le
  **titre + description** (toujours dans le flux RSS). Marche mieux en local (IP résidentielle).
- **Exploitation des données vidéo** : quand la transcription est disponible, elle est
  gardée *complète* (`article["transcript"]`, jusqu'à 20 000 car.) et, si la vidéo passe
  le triage, **digérée** par le modèle pas cher pour en extraire toutes les données
  chiffrées sans surcharger le 70b (voir §4, « Digest vidéo »). On capte donc les chiffres
  enfouis à la 45ᵉ minute, pas seulement le début.
- Quand la transcription est bloquée : repli sur la description (souvent un résumé chiffré
  chez les YouTubeurs finance). Transcription garantie → Phase 2 (§13) : Groq Whisper.

### 5.2 Newsletters par email (`email_sources.py`)

Boîte mail dédiée → toutes les newsletters y sont abonnées → le pipeline les lit
chaque nuit en **IMAP** (stdlib `imaplib`, aucune install).

**Configuration** :
- `NEWSLETTER_EMAIL` + `NEWSLETTER_PASSWORD` (= **mot de passe d'application**, pas le
  mot de passe du compte ; nécessite la **2FA** activée).
- Serveur IMAP **déduit du domaine** (gmail/outlook/yahoo/icloud) ; `NEWSLETTER_IMAP`
  force un autre serveur. Sans `EMAIL`/`PASSWORD` → module désactivé proprement.

**⚠️ Outlook ne marche PAS** : Microsoft a désactivé l'IMAP basic-auth sur les comptes
personnels (erreur `AUTHENTICATE failed` même avec 2FA + mot de passe d'application,
IMAP activé). → **Gmail** est la solution retenue (`hugo1actualite@gmail.com`).
Gmail : 2FA → myaccount.google.com → recherche « mots de passe des applications ».

**Cascade de filtres** (du moins cher au plus cher, pour épargner Groq) :
1. **Sécurité boîte perso** — seuls les emails avec `List-Unsubscribe`/`List-Id`
   (= vraies newsletters) sont traités ; les mails personnels (1-to-1) sont **ignorés**.
   → on peut pointer un Gmail existant sans toucher au courrier privé.
2. **Filtre bruit** (`_is_noise`) — écarte notifications réseaux sociaux (LinkedIn,
   GitHub…), paris sportifs, streaming, pétitions, transactionnel. Liste d'expéditeurs
   + sujets type « run failed », « nouveau message », « ça commence dans ».
3. **Dédoublonnage** — même expéditeur + même sujet = une seule analyse.
4. **Anti-pub** (`_is_promotional`) — codes promo, soldes, -X %, emojis commerciaux 🔥💰.
5. **IA Groq** — filtre sémantique final (score de pertinence).

Résultat sur la vraie boîte test : **26 mails → 14 envoyés à Groq** (~45 % économisés),
toutes les sources finance conservées (Zonebourse, Chéron, Aktionnaire, Guilmin…).
Tests offline : `python _test_email.py` · test connexion réelle : `python _test_email_live.py`.

### 5.3 Sources volontairement EXCLUES
- **Profils X / Twitter** et **Instagram** : aucun flux RSS, scraping bloqué/illégal ;
  API payantes (X ~100 $/mois) ou compte business requis (IG Graph). Pour les créateurs
  concernés (Baccino, Hasheur, Chéron) on récupère leur **YouTube + site + newsletter**.

---

## 6. Dédup intelligent (`pipeline/dedup.py`)

Évite de reposter la même info **tout en suivant l'actu quand elle bouge**. Pour chaque
article, deux empreintes comparées à l'historique 14 j (table `posts`) :
- **`topic_key`** — de QUOI on parle : tokens du titre FR (sans accents/mots-outils, triés). Similarité = Jaccard.
- **`data_sig`** — ce que DIT l'info : `label=valeur` des chiffres (ou points clés).

| Verdict | Condition | Action |
|---------|-----------|--------|
| `new` | sujet jamais vu (similarité < 0.55) | on publie |
| `duplicate` | même sujet **et** chiffres partagés inchangés (±2 %) | **ignoré** |
| `update` | même sujet **mais** un chiffre partagé a bougé > 2 % | publié, **taggé « MISE À JOUR »** |

- Un article qui mentionne *moins* de chiffres (sous-ensemble) n'est PAS une mise à jour.
- Tourne aussi *au sein d'une nuit* (deux quasi-doublons → un seul).
- Updates : `is_update=true` + `update_of` (id du post précédent) + badge « ↻ Mise à jour » sur le site.
- **Dégradation gracieuse** : historique injoignable → tout en `new`, jamais bloquant.
- Réglages : `SIM_THRESHOLD`, `FIGURE_TOLERANCE` en tête de fichier. Test : `python _test_dedup.py`.

---

## 7. Identité visuelle — charte HK Média

Direction artistique : **« Data punch » éditorial** · serif fort · jaune moutarde + crème.

- **Charte centralisée** : `pipeline/brand.py` (couleurs, polices, helpers `fr()`, `variations()`).
  - Couleurs : crème `#F5EDDA`, moutarde `#E2A50F`, encre `#1C1A15`.
  - Polices custom (OFL, bundlées dans `pipeline/_fonts/`) :
    - Titres → **DM Serif Display** · Gros chiffres → **Anton** · Texte → **Barlow**.
  - `brand.ensure_fonts()` enregistre les polices (commitées → pas de téléchargement
    à l'exécution ; fallback DejaVu si absentes).
- **Moteur de rendu** : `pipeline/dataviz.py`.
  - Chrome commun : cadre encadré, tag catégorie, **monogramme HK** (haut droite), footer source.
  - 5 types : `kpi`, `donut`, `bar`, `courbe`, `infographic` (dernier recours).
  - **Ordre de priorité du choix de type** (dans `ENRICH_PROMPT`) :
    1. `kpi` → au moins 1 chiffre clé (montant, %, taux, rang…)
    2. `bar` → 2+ valeurs comparables (pays, entreprises, produits…)
    3. `donut` → répartition en parts (~100 %)
    4. `courbe` → série temporelle (mois, trimestres, années…)
    5. `infographic` → **dernier recours**, article 100 % qualitatif sans aucun chiffre
  - **Diversité garantie** (`main.py`) : les articles avec graphique sont triés en tête ;
    maximum **2 infographics sur 7 posts** par nuit (`MAX_INFOGRAPHIC=2`).
  - Texte des key_points affiché sur **jusqu'à 2 lignes** (boîtes à hauteur adaptative).
  - Format **carré 1080×1080** universel (3 réseaux). Portrait/paysage = layouts dédiés (plus tard).
- Tester le rendu : `python dataviz.py` (→ `test_*.png`). Planche-contact : `python gallery.py`.

### 7.1 Posts Breaking News (`pipeline/breaking.py`)

Posts photo plein cadre pour les articles **score ≥ 8 + vérifiés**, maximum **2/nuit**.
Générés après les dataviz dans `main.py`, stockés avec `chart_type="breaking"`.

**Design** :
- Photo 1080×1080 (recadrage centre + légère désaturation pour faire ressortir le texte)
- Gradient noir de 30 % à 100 % (alpha progressif)
- Cadre jaune moutarde (`_MUSTARD`, 16 px)
- Badges haut gauche : **catégorie** (couleur par cat.) + **BREAKING** (rouge)
- Monogramme **HK** (cercle moutarde, Anton 36 px) haut droite
- Titre **ALL CAPS Anton blanc**, chiffres/€/% automatiquement en **jaune moutarde** (regex `_NUM_RE`)
- Ombre portée 4 px sur le titre
- Séparateur moutarde + footer `DÉCRYPTAGE EN DESCRIPTION` / `@HK.MÉDIA`

**Taille de police adaptative** (selon longueur du titre) :
| Police | Wrap | Quand |
|--------|------|-------|
| 88 px | 18 car./ligne | ≤ 2 lignes |
| 76 px | 20 car./ligne | ≤ 3 lignes |
| 64 px | 23 car./ligne | ≤ 4 lignes |
| 54 px | 26 car./ligne | fallback |

Titre tronqué à **80 caractères** max (coupe au dernier mot entier + `…`) pour rester percutant.

### 7.2 Recherche d'images libres de droits (`pipeline/image_fetch.py`)

Cascade par ordre de priorité :

1. **Wikimedia Commons** (sans clé API) — photos éditoriales réelles : hommes politiques,
   villes, bâtiments, marques, événements. Licence CC-BY-SA / domaine public.
   - Cascade de requêtes du plus spécifique au plus large :
     1. Noms propres extraits du titre (ex : `"Poutine Moscou"`, `"Decathlon"`)
     2. Requête complète traduite FR→EN
     3. 2 premiers mots-clés
   - Filtres anti-bruit : exclut `.svg`, cartes, drapeaux, logos, screenshots, icônes
     (liste `_WIKI_SKIP`) + largeur minimum 400 px.
   - Miniature redimensionnée à **1080 px** via l'API `iiurlwidth`.

2. **Unsplash** (`UNSPLASH_ACCESS_KEY`) — photos créatives haute qualité, licence libre commerciale.
   Utilise la clé **Access Key** (pas la Secret Key) avec header `Client-ID`.

3. **Pexels** (`PEXELS_API_KEY`) — fallback final, photos libres de droits.

**Traduction FR→EN** : dictionnaire `_TRANSLATE` dans `image_fetch.py` (canicule→heatwave,
guerre→war, taux directeur→key interest rate, ukraine→ukraine, etc.) pour que la recherche
Wikimedia/Unsplash/Pexels trouve des résultats pertinents depuis des titres en français.

**Mots à ne pas utiliser comme contexte catégorie** (`_CAT_CONTEXT`) :
- `general` → pas d'ancrage (les mots du titre suffisent)
- `finance` → `"finance economy"`, `tech` → `"technology digital"`, `sport` → `"sport athlete"`

Tester : `python _test_wikimedia.py` (génère des Breaking News avec images Wikimedia en local).

### 7.3 Posts Résultats Sportifs (`pipeline/sports/`)

Flux **indépendant** du pipeline nocturne : un **post par championnat et par jour**, publié
**uniquement quand TOUS les matchs prévus du jour sont terminés** (jamais de score partiel).
Tourne via `sports_results.yml` toutes les 30 min (17h→02h UTC) pour rattraper chaque fin de
match. Comme le reste, les posts arrivent en `status='pending'` sur le site de planning.

**Sources de données (deux étages)** :
| Source | Clé | Couvre | Pourquoi |
|--------|-----|--------|----------|
| **ESPN** (`site.api.espn.com`) | aucune | Coupe du Monde, Euro, Copa América | temps réel, **sans clé**, couvre 2026 (la CdM en cours) |
| **API-Sports** (`*.api-sports.io`) | `API_SPORTS_KEY` | Ligue 1/2/National, La Liga, Premier League, Bundesliga, Serie A, C1, C3, NBA, Betclic Élite, F1, Top 14, Champions Cup | championnats nationaux, **une seule clé** pour tous les sports |

> ⚠️ **Plan gratuit API-Sports limité aux saisons 2022-2024** → impossible d'accéder à 2026.
> C'est pour ça que les compétitions internationales 2026 passent par **ESPN** (public, sans
> clé), qui tourne **en premier** dans l'orchestrateur. API-Sports ne sert qu'aux ligues
> nationales et n'est appelé que si `API_SPORTS_KEY` est présent (sinon ignoré proprement).

**Fichiers** :
- `leagues.py` — config centralisée : `FOOTBALL_LEAGUES`, `BASKETBALL_LEAGUES`, `RUGBY_LEAGUES`,
  `ESPN_COMPETITIONS`, couleurs par championnat, `CURRENT_SEASON_*` (foot = 2024 sur le free tier).
- `api_client.py` — `get_football_fixtures()`, `get_espn_scores()`, `get_f1_race/results()`, etc.
  + helpers `all_finished()` / `espn_all_finished()` (statuts terminés : `FT/AET/PEN/AWD/WO/CANC/PST/ABD`).
- `sports_main.py` — orchestrateur : `run_espn()` (toujours), puis `run_football/basketball/f1/rugby()`
  si clé. `_already_posted()` (anti-doublon via Supabase) + `_save_scores_post()` (upload + insert).
- `scores_renderer.py` — rendu PIL 1080×1080 (voir design ci-dessous).

**Design des posts** (`scores_renderer.py`, charte HK) :
- Fond **ardoise dégradé bleuté** (jamais noir pur), **une ligne par match** : logo · nom · score · nom · logo.
- En-tête léger : accent vertical coloré + titre + sous-titre (PAS de bandeau lourd). **Espacement
  calculé dynamiquement** (`_header()` mesure chaque ligne → zéro chevauchement titre/sous-titre).
- Score : gagnant en **jaune moutarde**, perdant en gris foncé, nul en gris clair.
- **Logos** : viennent collés à chaque équipe par l'API (`team["logo"]`) → toujours le bon
  logo pour la bonne équipe (un mauvais logo = forcément une donnée de test, jamais la prod).
  ESPN fournit des **drapeaux PNG** pour les sélections nationales.
- **Traduction FR 100% fiable** (`_fr`, dict `_FR_RAW` normalisé sans accents) : pays
  (`Türkiye/Turkiye/TURKEY → Turquie`) ET clubs (`Barcelona → Barcelone`, `Bayern → Bayern Munich`).
  Insensible à la casse/accents → robuste quelle que soit la graphie de l'API.

**Podium F1 + portrait du vainqueur** (`make_f1_podium`) :
- Classement 1/2/3 (or/argent/bronze) à gauche, **portrait du vainqueur à droite** (badge VAINQUEUR).
- Portrait par ordre de fiabilité : **(1)** override curaté Commons (`_PORTRAIT_FILES`, dict de
  fichiers vérifiés, **rotation par jour** si plusieurs photos) → **(2)** image d'infobox Wikipédia
  (`fr` puis `en`, fiable pour ~18 des 22 pilotes) → **(3)** recherche Wikimedia générique.
- L'override sert aux pilotes dont l'infobox renvoie une voiture/photo de loin (ex. **Piastri**).
  Les vainqueurs récurrents (Verstappen, Norris, Leclerc, Hamilton, Russell, Antonelli) ont déjà
  un bon visage via l'infobox.
- **Robustesse Wikimedia** : on demande des **miniatures aux tailles cachées** (`iiurlwidth`, pas
  l'original pleine résolution) + **backoff sur HTTP 429** dans `_download()`. Le 429 ne survient
  qu'en cas de téléchargements massifs (tests) ; en prod = 1 portrait/course, jamais un souci.

**Tester en local** (génère des PNG de démo) :
```bash
cd pipeline/sports
$env:PYTHONIOENCODING="utf-8"   # Windows : éviter UnicodeEncodeError sur les accents
python sports_main.py            # run réel (ESPN sans clé ; API-Sports si API_SPORTS_KEY)
```
Volume estimé : ~2-6 posts/jour en période chargée (1 par championnat ayant fini sa journée).

### 7.4 Post Clôture des Marchés (`pipeline/markets/`)

Flux **indépendant** : **un post par jour** récapitulant la clôture des grands indices
boursiers + BTC + Or. Tourne via `markets_close.yml` à **21h30 UTC en semaine** (après la
clôture de Wall Street). Arrive en `status='pending'` sur le site de planning.

**Source de données** : **Yahoo Finance** (endpoint public `query1.finance.yahoo.com/v8/finance/chart/{symbol}`,
**sans clé**). Couvre indices, crypto et matières premières d'un seul endpoint. Pour chaque
symbole : `regularMarketPrice` (clôture) et `chartPreviousClose` → variation % du jour.

**Indices suivis** (`INDICES` dans `markets_main.py`, ordre = affichage) :
| Zone | Indices |
|------|---------|
| États-Unis | S&P 500 (`^GSPC`), Nasdaq (`^IXIC`), Dow Jones (`^DJI`) |
| Europe | Stoxx 600 (`^STOXX`), CAC 40 (`^FCHI`), DAX (`^GDAXI`), FTSE 100 (`^FTSE`) |
| Asie | Nikkei 225 (`^N225`), Hang Seng (`^HSI`), Shanghai (`000001.SS`) |
| Crypto & Matières | Bitcoin (`BTC-USD`), Or once (`GC=F`) |

> Ajouter/retirer un indice = éditer la liste `INDICES` (champ `section` = groupe d'affichage,
> `decimals`/`prefix` pour le format). Aucun autre changement requis.

**Fichiers** :
- `markets_main.py` — `fetch_quote()` (Yahoo), `build_rows()`, anti-doublon Supabase
  (`chart_type='markets'`, 1/jour), `_save_post()`, libellé de date FR.
- `markets_renderer.py` — rendu PIL 1080×1080. **Réutilise la charte commune** des posts
  sport (`_bg`, `_header`, `_footer`, polices) → look identique. Indices groupés par zone,
  valeur de clôture (format FR `7 500,58`), variation **vert (hausse) / rouge (baisse)** avec
  triangle ▲▼ dessiné en PIL (pas d'emoji).

**Tester en local** :
```bash
cd pipeline/markets
$env:PYTHONIOENCODING="utf-8"
python markets_main.py    # run réel (Yahoo sans clé ; Supabase si SUPABASE_*)
```

### 7.5 Posts marchés étendus — Top/Flop & Sentiment (`pipeline/markets/markets_extra.py`)

Trois posts supplémentaires, **dispatchés selon le jour** par un seul script
(`markets_extra.py`, workflow `markets_extra.yml`) — `main()` lit `date.weekday()` :

| Jour | Post | Donnée |
|------|------|--------|
| **Lun-Ven** (21h40 UTC) | **Top / Flop du jour** | variation du jour des actions de l'univers |
| **Samedi** (10h UTC) | **Top / Flop de la semaine** | variation ~5 séances (historique Yahoo `range=1mo`) |
| **Dimanche** (16h UTC) | **Sentiment des marchés** | **VIX** (`^VIX`) + **Fear & Greed crypto** (alternative.me) |

**Fiabilité = univers curaté.** Plutôt qu'un *screener* instable, `WORLD_STOCKS`
(`markets_extra.py`) liste ~40 grandes capitalisations mondiales (US / Europe / Asie)
dont on classe la variation → top 5 hausses + top 5 baisses. Chaque cours vient du
endpoint `v8/chart` éprouvé (sans clé). Devises multiples gérées (`$ € £ ¥ ₩…`).

**Sentiment (dimanche)** — deux panneaux avec jauge colorée + curseur :
- **Bourse · VIX** : <15 Calme · 15-20 Normal · 20-30 Nervosité · >30 Panique (échelle 0-40).
- **Crypto · Fear & Greed** : 0-24 Peur extrême · …· 75-100 Avidité extrême (échelle 0-100).
- Sources sans clé : VIX via Yahoo, indice crypto via `api.alternative.me/fng/`.

**Rendus** (`markets_renderer.py`) : `make_movers_post()` (2 sections hausses/baisses,
variation en gros coloré + triangle) et `make_sentiment_post()` (2 panneaux + jauges
segmentées dessinées en PIL). Même charte que la clôture (§7.4).

**Tester en local** :
```bash
cd pipeline/markets
$env:PYTHONIOENCODING="utf-8"
python markets_extra.py   # choisit automatiquement le post selon le jour courant
```

---

## 8. Base de données Supabase

**Table `posts`** (SQL Editor) :
```sql
create table posts (
  id uuid primary key,
  created_at timestamptz default now(),
  article_url text,
  article_title text,
  source text,
  category text,
  relevance_score int,
  verified boolean,
  key_data text[],
  chart_type text,
  caption_twitter text,
  caption_instagram text,
  caption_linkedin text,
  image_twitter text,
  image_instagram text,
  image_linkedin text,
  status text default 'pending',   -- pending | approved | posted | needs_transcript | to_regenerate
  network text,
  posted_at timestamptz,
  -- Dédup intelligent
  topic_key text,
  data_sig text,
  is_update boolean default false,
  update_of uuid,
  -- Transcription vidéo collée manuellement
  needs_transcript boolean default false,  -- vidéo sans script auto -> à compléter
  pending_transcript text                  -- script collé sur le site, en attente de retraitement
);

alter table posts enable row level security;
create policy "Public read" on posts for select using (true);
create policy "Service write" on posts for all using (true) with check (true);
```

**Table déjà existante (avant le dédup)** → migration :
```sql
alter table posts add column if not exists topic_key text;
alter table posts add column if not exists data_sig text;
alter table posts add column if not exists is_update boolean default false;
alter table posts add column if not exists update_of uuid;
alter table posts add column if not exists needs_transcript boolean default false;
alter table posts add column if not exists pending_transcript text;
```
> Compatibilité : si la migration n'est pas faite, `storage.py` retombe sur un insert
> sans ces colonnes (mais le dédup perd la mémoire des chiffres entre deux nuits).

**Bucket Storage** : Storage → New bucket → `post-images` → Public : OUI.

---

## 9. Site de planning (`docs/` — GitHub Pages)

- Servi depuis le dossier **`/docs`** (Settings → Pages → Deploy from branch → `/docs`).
- `docs/app.js` lignes 2-3 : `SUPABASE_URL` + `SUPABASE_ANON_KEY` (clé anon JWT legacy, lecture publique).
- Grille sombre de cartes : image générée + catégorie + score + titre + caption + boutons.
- Bouton **« Approuver »** (choix du réseau) → passe le post en `approved` dans Supabase.
- Badge **« ↻ Mise à jour »** sur les posts `is_update`.
- Aperçu local sans déploiement : `python make_preview.py` (→ `preview_planning.png`).

### 9.1 Transcription vidéo collée manuellement (`reprocess.py`)

Quand `youtube-transcript-api` échoue (IP cloud bloquée), le post vidéo est créé depuis
la **description** mais flagué `status='needs_transcript'`. Sur le site, ce post affiche
une **zone de collage** + un lien vers la vidéo + un bouton **« Générer »**.

Flux complet :
```
1. Pipeline : vidéo sans script -> post créé (description) + needs_transcript=true
   (les AUTRES posts continuent normalement, jamais bloqués)
2. Site : l'utilisateur copie le script sur YouTube, le colle, clique « Générer »
   -> écrit pending_transcript + status='to_regenerate' dans Supabase (clé anon)
3. Workflow reprocess.yml (toutes les 15 min OU « Run workflow » manuel) :
     reprocess.py -> get_posts_to_regenerate()
        -> analyzer.enrich_with_transcript() : DIGEST (8b) + ENRICHISSEMENT (70b)
        -> dataviz + captions régénérés -> update_post_content(status='pending')
4. Le post repasse en 'pending' (à approuver), needs_transcript=false. Notif ntfy.
```
- **Repo public** → minutes GitHub Actions gratuites/illimitées → planning 15 min OK.
- Le site (statique) ne peut PAS lancer Groq ni déclencher GitHub directement (ça
  exposerait un token) : il met en **file d'attente** ; le workflow fait le travail.
- L'utilisateur peut aussi **approuver tel quel** (version description) sans coller de script.
- Pour un traitement instantané : « Run workflow » sur l'onglet Actions du repo.

---

## 10. Variables d'environnement / secrets

Modèle : `.env.example` (committé, vide). Réel : `.env` (ignoré par git) + secrets GitHub.

```
GROQ_API_KEY
SUPABASE_URL
SUPABASE_KEY              # clé service_role (JWT legacy)
NTFY_TOPIC
NEWSLETTER_EMAIL         # boîte Gmail dédiée (ex: hugo1actualite@gmail.com)
NEWSLETTER_PASSWORD      # mot de passe d'application (16 car.), PAS le mdp du compte
NEWSLETTER_IMAP          # optionnel : déduit du domaine si absent
API_SPORTS_KEY           # résultats sportifs (§7.3) — 1 clé pour tous les sports api-sports.io.
                         #   OPTIONNEL : sans elle, seules les compétitions ESPN (CdM/Euro/Copa) tournent.
TWITTER_API_KEY / TWITTER_API_SECRET / TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET
INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ID
LINKEDIN_ACCESS_TOKEN / LINKEDIN_PERSON_ID
```

> ⚠️ Ne JAMAIS mettre un vrai secret dans `.env.example` (il est committé sur un repo
> public). Les secrets réels vont dans `.env` (gitignored) et dans les secrets GitHub.

**Réseaux sociaux (phase 2)** : X (OAuth 1.0a Read+Write, 1500 tweets/mois free),
Instagram (Graph API, compte Business + Page FB, token 60 j), LinkedIn (Share API,
token 60 j). Détails de création dans `poster/` quand on y arrivera.

---

## 11. Tests locaux

```bash
pip install -r requirements.txt        # feedparser, groq, supabase, matplotlib, Pillow, youtube-transcript-api…
cp .env.example .env                   # puis remplir .env

# Charger le .env (PowerShell) :
Get-Content .env | ForEach-Object { $k,$v=$_.Split('=',2); [Environment]::SetEnvironmentVariable($k,$v) }

cd pipeline
python validate_sources.py     # teste tous les flux RSS + YouTube en réel
python dataviz.py              # génère test_*.png (rendu des 5 types)
python gallery.py             # planche-contact de toutes les variantes
python _test_dedup.py          # logique dédup (offline, 6 cas)
python _test_analyzer.py       # split 2 modèles + digest vidéo (offline, mock)
python _test_email.py          # filtres email + détection serveur (offline)
python _test_email_live.py     # connexion IMAP réelle (lit la vraie boîte)
python _test_youtube.py        # résolution chaîne YouTube → flux
python main.py                 # PIPELINE COMPLET (nécessite toutes les clés)
python reprocess.py            # retraite les transcriptions collées (file Supabase)
```

> Note Windows : préfixer d'`$env:PYTHONIOENCODING="utf-8"` pour les scripts à emojis.

---

## 12. Ordre de mise en place

1. [x] Compte Groq → `GROQ_API_KEY`
2. [x] Projet Supabase → table `posts` (colonnes dédup + transcription, voir §8) + bucket `post-images`
3. [x] Repo GitHub `media-auto` → push
4. [x] Secrets GitHub : Groq + Supabase + ntfy
5. [x] Boîte newsletters Gmail + 2FA + mot de passe d'application → secrets
6. [x] **Architecture 2 modèles** (8b triage / 70b génération) — voir §4
7. [x] `validate_sources.py` → **30/30 sources OK** (flux morts remplacés par Google News)
8. [ ] Premier vrai run (`workflow_dispatch`) → vérifier quotas Groq
9. [ ] `docs/app.js` creds Supabase + activer GitHub Pages sur `/docs`
10. [ ] Réseaux sociaux X / Instagram / LinkedIn (en dernier)

---

## 13. Roadmap / Phase 2

| # | Chantier | Détail |
|---|----------|--------|
| ✅ | **Split 2 modèles Groq** | triage `8b-instant` + génération `70b` (quota-safe, §4) — FAIT |
| ✅ | **Copier-coller transcription sur le site** | post « transcription manquante » → collage → workflow `reprocess.yml` (digest + 70b + image + caption) — FAIT (§9.1) |
| ⏳ | **Transcription YouTube par Whisper** | télécharger l'audio (`yt-dlp`) → Groq `whisper-large-v3` (28 800 s/jour gratuits). Risque : téléchargement audio bloqué sur IP cloud. Automatiserait ce que le collage fait à la main |
| ⏳ | **Déclencheur instantané du retraitement** | Edge Function Supabase : le bouton « Générer » lancerait `reprocess.yml` en quelques secondes (au lieu d'attendre le cron 15 min). Reporté — voir décision ci-dessous |
| ✅ | **Posts Breaking News** | photo plein cadre 1080×1080, titre ALL CAPS, chiffres jaunes auto, Wikimedia → Unsplash → Pexels — FAIT (§7.1 / §7.2) |
| ✅ | **Module résultats sportifs** | 1 post/championnat/jour quand tout est fini ; ESPN (CdM/Euro, sans clé) + API-Sports (ligues nat.) ; design scores + podium F1 avec portrait du vainqueur ; traduction FR clubs/pays — FAIT (§7.3) |
| ✅ | **Post clôture des marchés** | 1 post/jour (lun-ven) : indices US/Europe/Asie + BTC + Or via Yahoo Finance (sans clé) ; valeurs FR + variation vert/rouge — FAIT (§7.4) |
| ✅ | **Top/Flop actions + sentiment** | Top/Flop actions mondiales du jour (lun-ven) et de la semaine (sam) ; sentiment VIX + Fear & Greed crypto (dim) — univers curaté fiable — FAIT (§7.5) |
| ⏳ | **Portraits F1 : rotation complète** | curer 2-3 visages vérifiés par vainqueur récurrent (mécanisme `_PORTRAIT_FILES` déjà en place) + override Stroll/Bearman/Albon. Faible priorité (l'infobox couvre déjà les favoris) |
| ⏳ | **Publication réseaux** (`poster/`) | X (tweepy), Instagram (Graph API), LinkedIn (Share API) après « Approuver » |
| ⏳ | **Déduplication par URL exacte** | renfort du dédup sémantique existant |
| ⏳ | **Formats portrait/paysage** | layouts dédiés (story 9:16) en plus du carré |

> **Décisions actées :**
> - Split 2 modèles + copier-coller transcription = **faits**.
> - Retraitement transcription : on **reste sur le cron 15 min** + bouton « Run workflow »
>   manuel pour l'instant (pas instantané, ~1-2 min de traitement incompressible). Le
>   déclencheur instantané (Edge Function) est **reporté** à plus tard, quand tout tournera.
> - Audio/Whisper et publication réseaux = phase 2.
> - Prochaine priorité : **commit** du bloc + `validate_sources.py` + **premier vrai run**.
