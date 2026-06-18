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
7. [Identité visuelle HK Média](#7-identité-visuelle--charte-hk-média)
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
```

Le pipeline **génère et stocke** les posts en statut `pending`. Rien n'est publié
automatiquement : l'utilisateur approuve chaque post sur le site avant mise en ligne.

---

## 2. Structure du dépôt

```
media-auto/
├── .github/workflows/
│   ├── daily_scan.yml     # cron nocturne (pipeline complet) + workflow_dispatch
│   └── reprocess.yml      # retraitement transcriptions collées (toutes les 15 min)
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
│   └── _test_*.py         # tests offline (dedup, email, youtube) — voir §11
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
| **2. Enrichissement** des ≤12 retenus | `llama-3.3-70b-versatile` | titre FR, sous-titre, type de graphique + données |

Les **captions** (`generator.py`) restent sur le 70b. Le gros volume passe ainsi sur
le modèle à 500k tokens/jour, le 70b n'est sollicité que sur les posts retenus.

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
  - 5 types : `kpi`, `donut`, `bar`, `courbe`, `infographic` (fallback).
  - **Actu sans chiffres** : type `infographic` (titre + 2-4 points clés, sans graphique).
    Le triage ne pénalise PAS l'absence de données — l'impact prime, la dataviz est un
    bonus (voir prompt `TRIAGE_PROMPT` dans `analyzer.py`).
  - Format **carré 1080×1080** universel (3 réseaux). Portrait/paysage = layouts dédiés (plus tard).
- Tester le rendu : `python dataviz.py` (→ `test_*.png`). Planche-contact : `python gallery.py`.

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
