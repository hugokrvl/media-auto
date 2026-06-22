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
4. [Limites Groq & architecture 2 modèles](#4-limites-groq--architecture-2-modèles) (+ **stack IA qualité Mistral/Gemini §4.1**)
5. [Sources (RSS · YouTube · Email)](#5-sources--pipelinesourcespy)
6. [Dédup intelligent](#6-dédup-intelligent--pipelinededuppy)
7. [Identité visuelle HK Média](#7-identité-visuelle--charte-hk-média) (dataviz · Breaking · images · sport §7.3 · marchés §7.4-5 · **moteur breaking §7.6** · **portraits/rotation §7.7**)
8. [Base de données Supabase](#8-base-de-données-supabase)
9. [Site de planning](#9-site-de-planning-docs--github-pages)
10. [Variables d'environnement / secrets](#10-variables-denvironnement--secrets)
11. [Tests locaux](#11-tests-locaux)
12. [Ordre de mise en place](#12-ordre-de-mise-en-place)
13. [Roadmap / Phase 2](#13-roadmap--phase-2)

---

## 1. Architecture & flux

```
GitHub Actions (cron 23:00 UTC = 1h Paris)  ← rubrique « ÉTUDES DATA » (100% dataviz)
  → pipeline/main.py  (orchestrateur)
      1. scraper.py        RSS + YouTube + Email → articles des dernières 24h
         (+ article_fetch.py : texte COMPLET des articles ouverts → plus de chiffres — §4/§5)
      2. analyzer.py       Groq → score, vérif, tri ; n'enrichit QUE le chiffrable (+ insight)
      2bis. opendata.py    + études DONNÉES OUVERTES (Banque mondiale, sans clé) en tête — §5.4
      2ter. dedup.py       new / duplicate / update (vs historique 14 j)
      3. carousel.py       CARROUSEL 1080×1080 par post : couverture → graphe → à retenir → verdict
                           (réutilise dataviz.py ; articles sans données = ÉCARTÉS → §7.8)
      4. generator.py      captions FR par réseau (Mistral/Gemini, repli Groq)
      5. storage.py        Supabase (table posts + colonne slides + bucket post-images)
      6. notifier.py       ntfy → notification push téléphone
  → docs/ (GitHub Pages)   ← VALIDATION HUMAINE (carrousel + boutons « Approuver » / « Supprimer »)
  → poster/                ← publication après approbation (X/IG/LinkedIn)

  ⚠️ Le nocturne ne fait PLUS de posts photo/news : l'actu « chaude » passe par le
     moteur breaking temps réel (breaking_scan.py, §7.6). Nocturne = DATA, breaking = NEWS.

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

cron-job.org (gratuit, toutes les ~30 min)  ← 6e entrée : BREAKING temps réel
  → déclenche breaking_scan.yml via l'API GitHub (workflow_dispatch, fiable)
  → pipeline/breaking_scan.py  RSS verticales → jugement IA (Mistral) → titre qui colle →
       figure emblématique / MONTAGE détouré / photo concept → vérif vision → post — §7.6 / §7.7
```

**IA de qualité (rigueur, titres, légendes)** : `llm.py` choisit le 1er fournisseur
dispo — **Mistral** (`mistral.py`) → **Gemini** (`gemini.py`) → repli **Groq**. Clés
gratuites (Mistral La Plateforme / Google AI Studio). Tout repli proprement sur Groq.

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
│   ├── markets_extra.yml  # Top/Flop actions + sentiment (lun-ven/sam/dim) — voir §7.5
│   ├── breaking_scan.yml  # BREAKING temps réel (déclenché par cron-job.org /30min) — voir §7.6
│   ├── opendata_check.yml # OUTIL manuel : teste EN LIVE les 4 fournisseurs open data — §5.4
│   └── reset_planning.yml # OUTIL manuel : vider la table posts (saisie "RESET")
├── pipeline/
│   ├── main.py            # orchestrateur (boucle, dédup, max 7 posts/nuit)
│   ├── reprocess.py       # regénère un post depuis une transcription collée
│   ├── sources.py         # liste centralisée des sources (rss/youtube/email)
│   ├── scraper.py         # récupération + dispatch par type de source
│   ├── article_fetch.py   # lecture best-effort du TEXTE COMPLET d'un article (repli résumé) — §4/§5
│   ├── youtube.py         # résolution chaîne→flux + transcription (+ repli desc.)
│   ├── email_sources.py   # lecture newsletters IMAP + cascade de filtres
│   ├── analyzer.py        # Groq : score / tri / données chart structurées
│   ├── dedup.py           # doublon vs mise à jour (empreintes sujet + données)
│   ├── dataviz.py         # moteur d'infographies HK (5 types)
│   ├── carousel.py        # CARROUSEL « étude data » (couverture→graphe→à retenir→verdict) — §7.8
│   ├── opendata.py        # études issues de données ouvertes (Banque mondiale, sans clé) — §5.4
│   ├── brand.py           # charte : couleurs, polices, helpers (fr(), variations())
│   ├── breaking.py        # rendu post photo plein cadre (titre + chiffres jaunes) — §7.1
│   ├── montage.py         # MONTAGE PRO : silhouettes détourées (rembg) sur fond design — §7.6
│   ├── image_fetch.py     # recherche d'images + pool/rotation de portraits — §7.2 / §7.7
│   ├── figures.py         # 66 figures récurrentes (name→org) pour rotation/montage — §7.7
│   ├── llm.py             # sélecteur IA qualité : Mistral → Gemini → (repli Groq) — §4
│   ├── mistral.py         # client REST Mistral (free tier) — §4
│   ├── gemini.py          # client REST Gemini (free tier) — §4
│   ├── breaking_scan.py   # MOTEUR breaking temps réel (RSS→IA→photo/montage) — §7.6
│   ├── reset_posts.py     # OUTIL : vide la table posts (garde-fou RESET_CONFIRM)
│   ├── generator.py       # captions FR par réseau (Mistral/Gemini, repli Groq)
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
│       ├── world_universe.py   # univers ~547 actions (S&P 500 + ADR monde, USD)
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

> ✅ **Captions — qualité** : le chemin NORMAL des captions passe par **Mistral/Gemini**
> (`generate_captions` → `llm.generate_json`), PAS par Groq. Le `GROQ_CAPTION_MODEL` n'est
> qu'un **repli** activé seulement si Mistral ET Gemini sont indisponibles ; il est désormais
> sur **`llama-3.3-70b-versatile`** (au lieu du 8b) → copy de secours bien meilleure.
> Quota-safe : 1 run/nuit ≈ ~48k/100k tokens 70b même en repli. Pour économiser lors de tests
> répétés le même jour, mettre `GROQ_CAPTION_MODEL=llama-3.1-8b-instant`.

**Digest map-reduce — vidéos ET articles complets** (`analyzer._digest_text`) — un texte
long (transcription d'1h ≈ 13k tokens, ou article complet) est trop gros pour le 70b
(100k/jour). On le « digère » d'abord avec le modèle pas cher (500k/jour) : découpe en
morceaux → extraction des seules DONNÉES (chiffres, %, montants, dates) → résumé condensé
(~1200 car.). Le 70b ne voit que ce digest → **toutes les données captées, tokens du 70b
préservés**. Deux sources :
- **vidéos** retenues → digest de la transcription (plafond `GROQ_MAX_DIGEST`, défaut 5).
- **articles** retenus (non-vidéo) → on récupère le **TEXTE COMPLET** (`article_fetch.py`,
  §5) puis on le digère (plafond `FULLTEXT_MAX`, défaut 10). Repli auto sur le résumé RSS si
  l'article est bloqué (paywall, Google News, anti-bot). **La récupération a lieu APRÈS le
  triage → aucun avantage de score pour les articles lus en entier (équité de sélection).**

Pour des textes très longs, un modèle à plus haut TPM (ex.
`meta-llama/llama-4-scout-17b-16e-instruct`, 30k TPM) via `GROQ_DIGEST_MODEL`.

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

### 4.1 Stack IA QUALITÉ : Mistral → Gemini → Groq (`llm.py`)

Pour les tâches où la **rigueur et le style comptent** (jugement breaking, titres qui
collent à l'image, légendes), on n'utilise plus le 8b mais le **meilleur fournisseur
gratuit disponible**, via `llm.py` :

```
llm.provider()  →  Mistral (mistral.py)  →  Gemini (gemini.py)  →  None
                                                                    ↓ (l'appelant retombe sur Groq)
```

- **Mistral** (`mistral.py`) — **fournisseur principal**. Clé gratuite « Experiment »
  (console.mistral.ai). Modèle par défaut **`mistral-medium-latest`** (meilleur
  qualité/débit gratuit : 25k tpm / 0,83 rps, surchargeable via `MISTRAL_MODEL`).
- **Gemini** (`gemini.py`) — alternative. Clé gratuite Google AI Studio. ⚠️ nécessite un
  **projet Google non restreint** (sinon 403/429). Défaut `gemini-2.0-flash`.
- **Repli Groq** : si aucune clé Mistral/Gemini ou erreur → `llm.*` renvoie `None` et
  l'appelant (`generator.py`) bascule proprement sur Groq. **Rien ne casse.**

Les deux clients sont en **REST pur (urllib)**, zéro dépendance, interface identique
(`available()`, `generate_json()`, `generate_text()`), retry/back-off sur 429/503.
Le client Groq de `generator.py` est **paresseux** → le moteur breaking tourne sur
Mistral **sans même exiger `GROQ_API_KEY`**.

> Test connexion réelle : charger la clé du `.env` puis `python mistral.py` (ou `gemini.py`)
> → doit afficher `{'ok': True, ...}`.

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
**État validé : 48 sources** (12 finance · 9 tech · **7 IA · 5 crypto · 2 quantique** ·
9 général · 2 sport · 2 fact-check). Verticales dédiées IA/blockchain/quantique via flux
directs (OpenAI, DeepMind, Hugging Face, The Decoder, Cointelegraph, Decrypt, The Block,
Quanta Magazine, The Quantum Insider…) + catégories de badge dédiées (IA violet, CRYPTO
orange, QUANTIQUE cyan). Beaucoup de médias FR (Reuters, Les Échos,
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

**Lecture du TEXTE COMPLET (`article_fetch.py`)** — le résumé RSS est court (~600 car.) et
les chiffres sont souvent dans le corps. Pour les articles **retenus au triage** (donc après,
pas avant → pas de biais de score), on récupère le texte complet (stdlib, zéro dépendance :
parse les `<p>`, ignore script/nav/footer) puis on le **digère** (§4). Bascule automatique et
robuste : Google News / paywall / page trop maigre / non-HTML → `None` → **repli sur le résumé
RSS** (méthode d'avant). Bénéficie surtout aux sources ouvertes (The Verge, TechCrunch, OpenAI,
CoinDesk, Numerama…) ; les liens `news.google.com` ne sont pas tentés (URL opaque).
Réglages : `FULLTEXT_FETCH` (1/0), `FULLTEXT_MAX` (10), `FULLTEXT_MIN_CHARS`, `FULLTEXT_TIMEOUT`.

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

> ⚠️ **Bases de presse payantes (Europresse via ezproxy universitaire, etc.) = NON.**
> Accès lié à un login étudiant perso (mettre des identifiants d'université dans la CI =
> interdit + bannissement du compte), licence d'usage personnel/pédagogique, et republier
> le texte d'articles protégés = problème de droits. Pour des chiffres fiables, on utilise
> les **données ouvertes** (§5.4), pas la presse payante.

### 5.4 Données ouvertes — études « data » (`pipeline/opendata.py`)

**Source COMPLÉMENTAIRE des articles** (le flux RSS/YouTube/email continue normalement).
Ici les chiffres sont DÉJÀ propres et vérifiés : on les récupère d'une API publique et on
construit directement une étude prête (chart_data + titre + sous-titre + **verdict** + points
clés, **100 % templatés, ZÉRO token IA**). L'étude entre dans le même moteur que les articles :
dédup → carrousel (§7.8) → captions → Supabase. Marquées `source="Banque mondiale"`,
`score=9`, `verified=true`, `is_opendata=true`.

- **Banque mondiale** (`api.worldbank.org`, JSON, **sans clé**) — registre `STUDIES` :
  classements de pays (`compare` → barres : PIB, PIB/hab., croissance, inflation, chômage,
  population, internet, R&D) et séries France (`series` → courbe : PIB 15 ans, inflation 12 ans).
  Valeurs en `Md$` / `%` / `hab.` selon l'indicateur.
- **FRED · Fed de St. Louis** (`api.stlouisfed.org`, JSON) — séries éco US en fréquence
  annuelle (`series` → courbe : taux directeur Fed, chômage US, taux à 10 ans). **Nécessite
  `FRED_API_KEY`** (gratuit sur fred.stlouisfed.org) ; **sans clé, ces études sont ignorées**
  (la Banque mondiale tourne seule). Démontre le pattern multi-fournisseurs (champ `provider`).
- **Eurostat** (`ec.europa.eu/eurostat`, **sans clé**, format **JSON-stat 2.0**) — classements
  de pays UE plus frais que la Banque mondiale (`compare` → barres : PIB, inflation IPCH,
  chômage). Parseur JSON-stat maison (`_js_latest_by_geo` : indice plat row-major + repli sur
  la dernière période dispo PAR pays ; `filters` fixe les dimensions unit/na_item/…). Les codes
  de dataset/dimension sont confirmés au 1er run réel — en cas de souci, l'étude est ignorée.
- **INSEE · BDM** (`bdm.insee.fr/series/sdmx`, **SANS clé** — service ouvert depuis 2015,
  format **XML SDMX-ML 2.1**) — séries FRANÇAISES par **idBank** (`series` → courbe).
  v1 : inflation France (idBank `001761313`, glissement annuel) + chômage (`001688370`).
  Parseur XML (`_insee_obs` : `<Obs TIME_PERIOD OBS_VALUE/>`) + **agrégation annuelle**
  (`period[:4]`) qui gère mensuel/trimestriel. Ajouter une série = un idBank dans `STUDIES`.
- **Variation intelligente** (`_build_series`) : un TAUX (%) → variation en **points** (un taux
  0,1 → 5,3 affiche « +5,2 pt », pas « +5200 % ») ; un NIVEAU (PIB…) → variation en **%**.
- **Rotation quotidienne** (`fetch_studies`) : un sous-ensemble différent chaque jour ;
  plafond `OPENDATA_MAX` (défaut 2/nuit). Le **dédup** écarte une donnée inchangée → pas de
  répétition (les stats officielles bougent ~1×/an).
- **Placées EN TÊTE** du flux nocturne (données les plus fiables), puis les articles.
- **Robuste** : toute erreur réseau/API → l'étude est ignorée, le flux articles continue seul.
- **Extensible** : **4 fournisseurs** branchés (Banque mondiale, FRED, Eurostat, INSEE) via le
  champ `provider`. Ajouter une source = écrire un fetcher + l'ajouter au registre `STUDIES`.
- Réglages env : `OPENDATA_ENABLED` (1/0), `OPENDATA_MAX` (2), `OPENDATA_TIMEOUT`, `FRED_API_KEY`.
- Test offline (builders + rendu, sans réseau) : `python opendata.py` (→ `test_od_*.png`).
- **Vérif LIVE des 4 fournisseurs** (`opendata.diagnose()`) : tente de construire les 16 études
  et rapporte OK/vide/erreur par fournisseur (confirme codes Eurostat + idBanks INSEE + clé
  FRED). Via le workflow manuel **`opendata_check.yml`** (Actions → « Vérif Open Data » → Run).
  Ne publie rien. Indispensable car la rotation (`OPENDATA_MAX`/jour) ne teste que 2 études/run.

---

## 6. Dédup intelligent (`pipeline/dedup.py`)

Évite de reposter la même info **tout en suivant l'actu quand elle bouge**. Pour chaque
article, deux empreintes comparées à l'historique 14 j (table `posts`) :
- **`topic_key`** — de QUOI on parle : tokens du titre FR (sans accents/mots-outils, triés). Similarité = Jaccard.
- **`data_sig`** — ce que DIT l'info : `label=valeur` des chiffres (ou points clés).
- **Ancres entités/nombres** (`_anchors`) — noms propres (AbbVie, Apogee…) + nombres (10.9),
  **invariants à la langue et à la reformulation**. Si deux articles partagent **≥2 ancres
  dont ≥1 nom propre** → même info → **doublon**, même quand le Jaccard du titre échoue
  (cas réel : une même news venue de sources différentes, titres tout autrement formulés —
  le breaking dédoublonne d'ailleurs sur le titre anglais brut vs l'historique FR).

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

> ⚠️ **Plus utilisé par le pipeline nocturne** : depuis le recentrage « études data » (§7.8),
> `main.py` ne génère plus de posts photo/breaking. `breaking.py` reste utilisé par le
> **moteur breaking temps réel** (`breaking_scan.py`, §7.6) et `montage.py`. Section conservée
> pour référence du rendu photo plein cadre.

Posts photo plein cadre pour les articles **score ≥ 8 + vérifiés**, maximum **2/nuit**.
Stockés avec `chart_type="breaking"`.

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

1. **Wikipédia (image d'infobox)** — source PRINCIPALE pour les entités nommées, via
   `_wikipedia_pageimage()` (API `pageimages`, fr puis en). C'est la **photo canonique**
   de l'entité → ultra fiable (même méthode que les portraits pilotes F1). Résout les
   redirections : « Zelensky » → page « Volodymyr Zelensky » → portrait officiel 2022.
   - **Extraction stricte des noms propres** (`_is_proper`) : exige une vraie MAJUSCULE
     initiale (la regex `À-Ÿ` capture aussi é/è/à minuscules → rejetés) et exclut
     (`_NOT_PROPER`) : mots-outils (Comment, Selon…), **mots de format/live-blog**
     (DIRECT, LIVE, VIDÉO, ANALYSE…), **pays/gentilés** (France, Iran… → place/drapeau
     hors-sujet) et **marques ambiguës** (Visa, Total…).
   - **Entités candidates** : PAIRES adjacentes d'abord (`Eric Schmidt`, pas `NASA Eric`),
     puis noms isolés — **jamais un prénom seul** (`_FIRST_NAMES`) qui matcherait un
     homonyme (« Eric » → l'astronaute Eric Boe).
2. **Wikimedia Commons** (repli, sans clé) — recherche STRICTE, seulement pour les entités
   **multi-mots** (un nom de famille isolé matche trop d'homonymes → on s'abstient).
   - Match par **MOT ENTIER** (`_token_in` : `direct` ne matche plus `directeur`).
   - **Filtres** : peintures/gravures anciennes (`_looks_like_painting` : bildnis, litho,
     huile sur toile…), **personnages historiques** (`_is_historical` : année ≤ 1965 dans
     le nom → « Herman Schwab (1861-1951) » écarté), + `.svg`/cartes/logos (`_WIKI_SKIP`).
   - Si rien de fiable → `None` → bascule sur Unsplash (photo de concept, bien plus pro
     qu'un mauvais visage). **Précision avant exhaustivité.**
   - Exemples validés : Lagarde→portrait BCE, Zelensky→portrait officiel, Eric Schmidt→sa
     photo, SpaceX→lancement de fusée, Mbappé→Mbappé ; Schwab/Visa/Canicule→photo concept.

3. **Unsplash** (`UNSPLASH_ACCESS_KEY`) — photos créatives haute qualité, licence libre commerciale.
   Utilise la clé **Access Key** (pas la Secret Key) avec header `Client-ID`. C'est ici qu'aboutissent
   les sujets abstraits / ambigus (finance, concepts) → photo de concept pertinente.

4. **Pexels** (`PEXELS_API_KEY`) — fallback final, photos libres de droits.

**Traduction FR→EN** : dictionnaire `_TRANSLATE` dans `image_fetch.py` (canicule→heatwave,
guerre→war, taux directeur→key interest rate, ukraine→ukraine, etc.) pour que la recherche
Wikimedia/Unsplash/Pexels trouve des résultats pertinents depuis des titres en français.

**Mots à ne pas utiliser comme contexte catégorie** (`_CAT_CONTEXT`) :
- `general` → pas d'ancrage (les mots du titre suffisent)
- `finance` → `"finance economy"`, `tech` → `"technology digital"`, `sport` → `"sport athlete"`

Tester : `python _test_wikimedia.py` (génère des Breaking News avec images Wikimedia en local).

**Actualité qualitative → post photo** (`main.py`) : un article sans données chiffrées
(`chart_type = infographic`) ne fait PLUS une liste de points souvent vide. On cherche
une photo sur le sujet (cascade ci-dessus) et, si trouvée, on génère un **post photo plein
cadre** (`breaking.make_breaking_image(..., badge=None)` — même rendu que Breaking mais
SANS la mention « BREAKING »), taggé `chart_type = "photo"`. Sinon, repli infographie.
Le **lien de l'article** est ajouté en fin de description (captions Instagram + LinkedIn).

**KPI sans chevauchement** (`dataviz._make_kpi`) : la police des grandes valeurs ET des
libellés est **auto-ajustée** à la largeur de carte (`_fit_fontsize`) → une valeur longue
(« 1,2 billion ») ou un libellé long ne déborde jamais sur la carte voisine. L'unité
redondante avec la valeur (« 1,2 billion » + « milliards ») est masquée.

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

**Vrai Top/Flop = univers LARGE scanné en entier.** Le top/flop du jour, ce sont les
plus grosses variations — quasi jamais des méga-caps (qui bougent peu). On scanne donc
**tout l'univers** `UNIVERSE` (`world_universe.py`) : **S&P 500 (503) + ~44 grandes
valeurs internationales** (ADR), soit **~547 actions**, puis on classe par variation
→ vrais top 5 hausses + top 5 baisses (souvent ±10-45 %).
- **Tous cotés en USD** (ADR US pour les étrangères : `NVO`, `ASML`, `TM`, `SHEL`…)
  → une seule devise, même séance, **aucun problème de change**.
- **Récupération concurrente** (`ThreadPoolExecutor`, 16 threads) → ~547 cours en ~6 s
  via le endpoint `v8/chart` éprouvé (sans clé). Aucun rate-limit observé.
- Garde-fous : variation `|chg| > 60 %` ignorée (anomalie de données) ; dédoublonnage
  par nom (Fox A/B, Alphabet A/C).
- `world_universe.py` est généré depuis la liste publique des constituants du S&P 500
  (datasets/s-and-p-500-companies) + un bloc d'ADR internationaux liquides.

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

### 7.6 Moteur Breaking temps réel (`pipeline/breaking_scan.py`)

Flux **quasi temps réel** dédié éco/tech/IA/blockchain/quantique. Cœur du média : le
titre **colle à l'image**, info **rigoureuse**, photos **réelles**. Posts en `pending`.

Pipeline rapide :
1. **Candidats récents** (`fetch_candidates`) : flux RSS DIRECTS des verticales
   (pas Google News → vitesse), articles publiés ≤ `BREAKING_RECENT_MIN` (45 min).
2. **Dédoublonnage** (`dedupe`) vs historique 3 j (`dedup.classify`) → jamais 2× la même info.
3. **Jugement IA EN LOT** (`judge`, 1 seul appel `llm`) : ne garde que `breaking==true`
   & `score ≥ BREAKING_SCORE_MIN` (7), cap `BREAKING_MAX_PER_SCAN` (2). Sécurité : si
   aucun fournisseur IA qualité (Mistral/Gemini), le scan s'abstient (rien posté).
4. **Enrichissement** (`enrich`) : titre FR percutant qui **colle au sujet** + `people`.
   **Règle figure STRICTE** (anti mauvais visage) : une personne seulement si elle est nommée
   OU le dirigeant emblématique de **L'ENTREPRISE précise** du sujet (OpenAI→Altman, Palantir→Karp…).
   **Jamais** une figure ajoutée juste parce qu'elle est connue du secteur ; un sujet PAYS /
   MARCHÉ / TENDANCE → `people: []` (→ photo concept). 2+ personnes **uniquement** si toutes
   protagonistes du MÊME événement. `image_query` doit coller au **TON** (pas de hausse pour
   une chute, pas de cliché générique). `companies` retiré (logos abandonnés).
5. **Image = héros** (`image_candidates`, générateur LAZY testé un à un par la barrière QA §6), par ordre :
   - **≥ 2 dirigeants** → **MONTAGE PRO** (`montage.py`) : portraits **détourés** (`rembg`,
     modèle **configurable via `REMBG_MODEL`** — défaut `isnet-general-use` ~178 Mo, bords nets
     pour un rendu pro ; `u2netp` ~4 Mo en repli léger / local) sur fond dégradé HK + glow
     couleur catégorie + ombres portées, layout adaptatif. 100% cloud (rembg dans GitHub
     Actions, **modèle mis en cache** → téléchargé une seule fois). Repli auto sur montage en
     bandes si rembg indisponible.
   - **1 dirigeant / figure de la boîte** → son **portrait** (en **rotation**, voir §7.7)
   - sinon → **photo concept** (Unsplash, sur la requête image de l'IA)
   - Filet : si le portrait n'a pas de photo Wikipédia → repli concept (jamais d'image cassée).
   - **Anti mot-ambigu** : sans dirigeant, on prend la photo CONCEPT (requête IA) AVANT la
     cascade Wikipédia par mots du titre (sinon « Codex » → manuscrit médiéval, « Visa » → document).
6. **VÉRIFICATION VISION** (`verify_coherence`, Mistral vision `generate_json_image`) — joue
   le **DIRECTEUR ARTISTIQUE** : l'IA **regarde le post final** (image + titre) et note 0-10.
   **Rejette** (coherent=false) si : la personne montrée n'est pas le vrai sujet ; l'image
   contredit le sens (hausse pour une chute) ; image **pas pro** (torse nu, meme, groupe flou,
   cosplay, capture, cassée/sombre) ; **texte incrusté illisible/coupé/glyphes manquants** ;
   cliché 100 % générique. Sous `BREAKING_COHERENCE_MIN` (défaut **6**) → l'image est **rejetée**.
   (Si Mistral indispo → on ne bloque pas.)

   **AUTO-CORRECTION** (`main`) : si un candidat est rejeté, on **refait automatiquement** avec
   le candidat suivant (`image_candidates`), jusqu'à `BREAKING_MAX_ATTEMPTS` (3). Les essais
   ratés sont **conservés** : uploadés + stockés dans `attempts` (jsonb `[{image, raison, score,
   type}]`). Si aucun candidat ne passe → post abandonné. Le site (§9) affiche un bouton **« ⚑
   Essais »** à côté de « Supprimer » : **gris** si réussi du 1er coup, **vert** s'il a fallu des
   essais → au clic, modale des versions rejetées (image + note IA + raison).
7. Légende (`generator`, Mistral) + sauvegarde Supabase (`chart_type` = `breaking`/`montage`,
   `attempts` = essais ratés).

> Logos d'entreprise : abandonnés — aucune source gratuite haute résolution (Clearbit mort,
> favicons 48px pixelisés, Wikipédia incohérent). La **figure emblématique** remplit ce rôle.

**Surlignage jaune intelligent** (`breaking._is_significant_number`, hérité par `montage`) :
un nombre n'est surligné que si c'est une **vraie stat** (unité/magnitude `1 million`,
virgule `5,7`, séparateur de milliers `30 000`, entier ≥2 chiffres hors année). **Jamais**
un label (`T1`, `5G`, `GPT-6`), un chiffre seul, ou une année (`2026`).

**Déclenchement FIABLE via cron-job.org** (pas le cron GitHub, trop peu fiable) :
- `breaking_scan.yml` a un `schedule` GitHub (filet) **+ `workflow_dispatch`**.
- Un cronjob **cron-job.org** (gratuit) appelle l'API GitHub toutes les ~30 min :
  `POST https://api.github.com/repos/hugokrvl/media-auto/actions/workflows/breaking_scan.yml/dispatches`
  body `{"ref":"main"}`, header `Authorization: Bearer <PAT fine-grained, Actions: write>`.
  Succès = **204**. C'est ça qui garantit le temps réel (le cron GitHub natif tardait/sautait).

Réglages env : `BREAKING_RECENT_MIN`, `BREAKING_MAX_PER_SCAN`, `BREAKING_SCORE_MIN`,
`BREAKING_COHERENCE_MIN` (seuil vérif vision), `REMBG_MODEL` (modèle de détourage des montages,
défaut `isnet-general-use` ; surchargeable par une *Repository variable* GitHub du même nom).
Test local (sans Supabase) : `fetch_candidates()` → `judge()` → `enrich()` → `build_image()`
→ `verify_coherence()` (charger `MISTRAL_API_KEY` depuis `.env`).

### 7.7 Portraits : figures récurrentes & rotation (`figures.py`, `image_fetch.py`)

Pour ne **jamais montrer toujours la même photo** d'une personnalité qui revient souvent.

**Liste des figures** (`figures.py`) — **66 figures récurrentes** IA / tech / crypto / finance
(Altman, Musk, Huang, Saylor, Powell, Lagarde…), `name → org`. Sert à (a) mapper une
entreprise → sa figure emblématique (fiable, vs prompt seul) et (b) définir qui a une rotation.

**Pool de portraits** (`image_fetch.portrait_pool(name)`) = image d'infobox Wikipédia
(canonique) **+ portraits solo Commons**. Famous figures → **~9 photos**, moins connues → 2-4.

**Filtres du pool** (cumulés, pour un pool 100% portraits solo VARIÉS) :
- **anti-groupe** (`_GROUP_HINT` : « and / with / et / **y** / visit / president / commission… »)
- **anti-famille** : le nom de famille apparaît **2+ fois** dans le fichier → multi-personnes
- **anti-data-viz** (`_NOT_PORTRAIT` : net worth, stock, chart, revenue, logo, tweet…)
- **anti-peinture / historique** (`_looks_like_painting`, `_is_historical`)
- **anti même-shooting** (`_context_key`) : signature de CONTEXTE (lieu/événement/année,
  en ignorant le nom, « cropped » et les longs ID Flickr) → on ne garde **qu'une photo par
  contexte**. Évite la « fausse variété » (4 photos d'IDs Flickr proches = même interview).
- normalisation propre du nom de fichier (« File: », « _ », ponctuation → espaces) pour de
  vrais bords de mots.

**Rotation** (`image_fetch.portrait_for(name, seed)`) : `seed` dérivé de l'URL de l'article
→ chaque sujet montre une **photo différente** de la même personne. Dans `breaking_scan`,
le **portrait unique** utilise `portrait_for` (variété).

> ⚠️ **Montages = portraits CANONIQUES uniquement** (`image_fetch.portrait_canonical` =
> image d'infobox Wikipédia, PAS la rotation Commons). Raison : la rotation Commons laissait
> passer des clichés ratés (photo de groupe étiquetée « Starmer », Torvalds torse nu,
> cosplayers…) ; sur un montage de 2-3 visages le risque est multiplié. `build_image`
> n'assemble un montage que si **≥2 portraits canoniques** sont trouvés, sinon portrait unique
> (rotation) ou photo concept.

**Composition du montage** (`montage._make_pro`) : figures **soudées en un seul groupe**
(chevauchement type « casting », **une seule lumière d'ambiance** couleur catégorie, ombre au
sol commune, centre devant, hauteur auto-réduite si le groupe dépasse le cadre) — au lieu de
visages isolés à halos séparés. Repli `_make_strips` (bandes) si le détourage rembg échoue.

> Photos de GROUPE : isoler **une** personne d'un groupe = reconnaissance faciale (lourde,
> ~200 Mo) → **reportée**. On filtre les groupes et on tourne sur les photos solo (suffisant :
> ~9 contextes distincts pour les figures fréquentes).
> Le mécanisme de rotation existe aussi côté F1 (`scores_renderer._PORTRAIT_FILES`).

### 7.8 Carrousels « étude data » (`pipeline/carousel.py`) — pipeline nocturne

Depuis le recentrage, **chaque post de 1h du matin est un CARROUSEL** : une petite étude
visuelle de 3-4 slides 1080×1080, au lieu d'une seule image. Format dédié à la **dataviz
fiable** ; l'actu chaude est gérée par le breaking (§7.6). **Nocturne = DATA, breaking = NEWS.**

**Structure d'un carrousel** (`generate_carousel`, chaque slide protégé par try/except) :
1. **Couverture** — eyebrow « ÉTUDE DATA », titre serif, **chiffre héros** (le plus gros point), « GLISSEZ ▸ ».
2. **Graphique** — la dataviz principale (`dataviz.generate_image`, kpi/bar/donut/courbe).
3. **À retenir** — 2-4 points clés chiffrés (slide omis s'il n'y a pas de `key_points`).
4. **Le verdict** — le champ `insight` (conclusion factuelle en 1 phrase) + source + CTA.

Toute la charte vient de `dataviz.py` (cadre, tag, monogramme, footer, polices) → look 100 %
cohérent. **Repli** : si un slide échoue, on renvoie au moins la dataviz principale (jamais
de post cassé). Tester en local : `python carousel.py` (→ `test_carousel_*.png`).

**Sélection data-only** (`main.py`) : `analyzer.py` n'enrichit que le chiffrable et ajoute un
champ **`insight`** ; tout article dont `chart_type` reste `infographic` (aucune donnée) est
**écarté** (`_has_data`). Qualité > quantité : une nuit pauvre en data fera moins de 7 posts
(plafond `NIGHTLY_MAX_POSTS`, défaut 7).

**Stockage & site** : les URLs des slides vont dans la colonne `slides` (text[], voir §8 —
**migration requise**). Le site (`docs/`) affiche un carrousel (flèches ‹ ›, compteur, badge)
sur les cartes et dans la modale ; l'`image_*` de chaque réseau pointe sur la **couverture**
(vignette + repli si `slides` absent). Publication carrousel IG/LinkedIn = phase 2 (`poster/`).

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
  pending_transcript text,                 -- script collé sur le site, en attente de retraitement
  -- Carrousel « étude data » (pipeline nocturne)
  slides text[],                           -- URLs des slides (couverture → graphe → à retenir → verdict)
  -- Barrière QA (auto-correction breaking, §7.6)
  attempts jsonb                           -- essais ratés [{image, raison, score, type}] avant la version validée
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
alter table posts add column if not exists slides text[];   -- carrousels « étude data » (§7.8)
alter table posts add column if not exists attempts jsonb;  -- essais ratés barrière QA (§7.6)
```
> Compatibilité : si la migration n'est pas faite, `storage.py` retombe sur un insert
> sans ces colonnes (le dédup perd la mémoire des chiffres entre deux nuits ; **sans
> `slides`, les posts nocturnes s'affichent avec la seule couverture, pas le carrousel**).

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

### 9.2 Créer un post DEPUIS UN TEXTE collé (`carousel.generate_decryptage`)

Bouton **« ✍️ Créer »** (header du site) → fenêtre où l'on **colle un texte** (transcription
YouTube, article, notes) + titre/catégorie optionnels → génère un **carrousel DÉCRYPTAGE**
(6-8 slides : couverture → sections → conclusion).

Flux (réutilise l'infra transcription) :
```
1. Site : insert d'un post status='to_generate' + pending_transcript=<texte> (clé anon).
2. reprocess.yml (15 min ou manuel) → reprocess.run_generate() :
     analyzer.enrich_decryptage() : DIGEST token-safe (8b, _digest_text max_chunks=6) →
       structuration en `sections` [{titre, points}] + insight (70b)
     → carousel.generate_decryptage() (slides) → update_post_content(status='pending', slides)
3. Le post arrive en 'pending' (carrousel), prêt à approuver. Notif ntfy.
```
- **Token-safe** : un long texte (transcription 1h) est digéré par le 8b (gros quota) avant le
  70b → « tri pertinent et divisé », conso minimale (le 70b ne voit que ~5000 car. de condensé).
- Le site statique ne lance pas l'IA (exposerait un token) : il met en **file** ; le workflow fait le travail.

---

## 10. Variables d'environnement / secrets

Modèle : `.env.example` (committé, vide). Réel : `.env` (ignoré par git) + secrets GitHub.

```
GROQ_API_KEY
MISTRAL_API_KEY          # IA QUALITÉ principale (§4.1) — gratuit console.mistral.ai.
                         #   Sans elle : repli Gemini puis Groq. MISTRAL_MODEL optionnel.
GEMINI_API_KEY           # alternative IA qualité (§4.1) — gratuit Google AI Studio.
                         #   ⚠️ projet Google non restreint requis. GEMINI_MODEL optionnel.
SUPABASE_URL
SUPABASE_KEY              # clé service_role (JWT legacy)
NTFY_TOPIC
UNSPLASH_ACCESS_KEY      # photos concept (breaking sans personne). PEXELS_API_KEY = fallback.
NEWSLETTER_EMAIL         # boîte Gmail dédiée (ex: hugo1actualite@gmail.com)
NEWSLETTER_PASSWORD      # mot de passe d'application (16 car.), PAS le mdp du compte
NEWSLETTER_IMAP          # optionnel : déduit du domaine si absent
API_SPORTS_KEY           # résultats sportifs (§7.3) — 1 clé pour tous les sports api-sports.io.
                         #   OPTIONNEL : sans elle, seules les compétitions ESPN (CdM/Euro/Copa) tournent.
TWITTER_API_KEY / TWITTER_API_SECRET / TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET
INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ID
LINKEDIN_ACCESS_TOKEN / LINKEDIN_PERSON_ID
```

> 🔑 **Token cron-job.org** (déclencheur breaking, §7.6) : un **PAT GitHub fine-grained**
> (repo `media-auto`, permission *Actions: Read and write*) vit **uniquement dans cron-job.org**
> (header Authorization). PAS dans `.env` ni le code. À régénérer s'il est exposé.

> ⚠️ Ne JAMAIS mettre un vrai secret dans `.env.example` (il est committé sur un repo
> public). Les secrets réels vont dans `.env` (gitignored) et dans les secrets GitHub.
> ⚠️ Tous les secrets sont lus avec `.strip()` (un `\n` collé casse les en-têtes HTTP).

**Réseaux sociaux (phase 2)** : X (OAuth 1.0a Read+Write, 1500 tweets/mois free),
Instagram (Graph API, compte Business + Page FB, token 60 j), LinkedIn (Share API,
token 60 j). Détails de création dans `poster/` quand on y arrivera.

---

## 11. Tests locaux

```bash
pip install -r requirements.txt        # feedparser, groq, supabase, matplotlib, Pillow,
                                       # youtube-transcript-api, rembg+onnxruntime (montage détouré)…
cp .env.example .env                   # puis remplir .env

# Charger le .env (PowerShell) :
Get-Content .env | ForEach-Object { $k,$v=$_.Split('=',2); [Environment]::SetEnvironmentVariable($k,$v) }

cd pipeline
python validate_sources.py     # teste tous les flux RSS + YouTube en réel
python dataviz.py              # génère test_*.png (rendu des 5 types)
python gallery.py             # planche-contact de toutes les variantes
python _test_dedup.py          # logique dédup (offline, 6 cas)
python _test_pipeline.py       # INTÉGRATION main.run() : open data + dédup + carrousel (offline, stubs)
python opendata.py             # 4 fournisseurs open data : builders + parseurs + rendus (offline)
python _test_analyzer.py       # split 2 modèles + digest vidéo (offline, mock)
python _test_email.py          # filtres email + détection serveur (offline)
python _test_email_live.py     # connexion IMAP réelle (lit la vraie boîte)
python _test_youtube.py        # résolution chaîne YouTube → flux
python mistral.py              # test connexion Mistral (→ {'ok': True, ...})
python gemini.py               # test connexion Gemini (→ {'ok': True, ...})
python breaking_scan.py        # MOTEUR breaking (RSS→IA→photo/montage→Supabase)
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
| ✅ | **Stack IA qualité (Mistral/Gemini)** | `llm.py` Mistral→Gemini→Groq ; rigueur jugement + titres + légendes ; clients REST gratuits — FAIT (§4.1) |
| ✅ | **Moteur Breaking temps réel** | scan /30 min (cron-job.org) éco/tech/IA/crypto/quantique ; jugement IA, titre qui colle, **montage** de vrais portraits, **figure emblématique** d'entreprise, surlignage chiffres intelligent — FAIT (§7.6) |
| ✅ | **Montage PRO (silhouettes détourées)** | `rembg` (u2netp) détoure les portraits → fond design HK + glow + ombres, layout adaptatif 2-4 ; repli bandes si rembg KO — FAIT (§7.6) |
| ✅ | **Vérification VISION de cohérence** | Mistral vision regarde le post final ; rejette si l'image ne colle pas au sujet (seuil `BREAKING_COHERENCE_MIN`) — FAIT (§7.6) |
| ✅ | **Portraits : figures récurrentes + rotation** | 66 figures (`figures.py`) ; pool ~9 portraits solo Commons (filtres groupe/famille/data-viz/peinture + anti même-shooting) ; rotation par article — FAIT (§7.7) |
| ⏳ | **Isoler une personne d'une photo de groupe** | nécessite reconnaissance faciale (~200 Mo) ; reporté — la rotation solo suffit pour l'instant |
| ✅ | **Verticales IA/blockchain/quantique** | +18 sources directes + catégories/badges dédiés (IA violet, CRYPTO orange, QUANTIQUE cyan) — FAIT (§5) |
| ⏳ | **Logos d'entreprise** | reporté : pas de source gratuite HD (Clearbit mort, favicons 48px). Figure emblématique remplit le rôle. Option = banque de logos payante |
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
