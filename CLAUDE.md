# MediaAuto — Documentation complète

Pipeline automatisé de veille média → dataviz → posts réseaux sociaux.
Tourne chaque nuit à 1h via GitHub Actions.

---

## Architecture

```
GitHub Actions (cron 1h)
  → pipeline/main.py
      → scraper.py      (RSS → articles 24h)
      → analyzer.py     (Groq → score, tri, vérification)
      → dataviz.py      (matplotlib → PNG par réseau)
      → generator.py    (Groq → captions adaptées)
      → storage.py      (Supabase DB + Storage)
      → notifier.py     (ntfy push)
  → site/ (GitHub Pages)  ← validation humaine
  → poster/               ← publication après approbation
```

---

## Services & Comptes (tous gratuits)

### 1. Groq — LLM
- Site : https://console.groq.com
- Créer un compte → API Keys → New key
- Modèle utilisé : `llama-3.3-70b-versatile`
- Limite free : ~14 000 requêtes/jour
- Variable : `GROQ_API_KEY`

### 2. Supabase — Base de données + Stockage images
- Site : https://supabase.com → New project
- Nom suggéré : `mediaauto`
- Région : West EU (Ireland) pour la latence France
- Après création → Settings → API → copier URL et anon key
- Variables : `SUPABASE_URL`, `SUPABASE_KEY`

**Créer la table `posts` dans Supabase (SQL Editor) :**
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
  status text default 'pending',
  network text,
  posted_at timestamptz
);

-- Activer la lecture publique (pour le site GitHub Pages)
alter table posts enable row level security;
create policy "Public read" on posts for select using (true);
create policy "Service write" on posts for all using (true) with check (true);
```

**Créer le bucket Storage :**
- Storage → New bucket → nom : `post-images` → Public : OUI

### 3. GitHub — Repo + Actions + Pages
- Créer un repo public : `media-auto`
- Push le code dedans
- Settings → Secrets → Actions → ajouter tous les secrets du `.env.example`
- Settings → Pages → Source : `Deploy from branch` → branch `main` → folder `/site`
- Le site sera dispo sur : `https://TON_USERNAME.github.io/media-auto/`

**Ajouter ces secrets GitHub Actions :**
```
GROQ_API_KEY
SUPABASE_URL
SUPABASE_KEY
NTFY_TOPIC
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_SECRET
INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_BUSINESS_ID
LINKEDIN_ACCESS_TOKEN
LINKEDIN_PERSON_ID
```

### 4. ntfy — Notifications push
- Télécharger l'app ntfy sur ton téléphone (déjà fait)
- Choisir un topic unique, ex : `mediaauto-hugo-2024`
- Abonner l'app à ce topic
- Variable : `NTFY_TOPIC=mediaauto-hugo-2024`
- Test : `curl -d "Test" ntfy.sh/mediaauto-hugo-2024`

### 5. X / Twitter Developer
- Site : https://developer.twitter.com
- Créer une app → Free tier
- Activer OAuth 1.0a avec Read + Write
- Variables : `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`
- Limite free : 1500 tweets/mois (largement suffisant pour 5-7/jour)

### 6. Instagram (Meta for Developers)
- Site : https://developers.facebook.com
- Créer une app → Type : Business
- Ajouter le produit "Instagram Graph API"
- Le compte Instagram doit être Business ou Creator + lié à une Page Facebook
- Variables : `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID`
- Note : l'access token expire tous les 60 jours → rafraîchir manuellement ou automatiser

### 7. LinkedIn Developer
- Site : https://developer.linkedin.com
- Créer une app → Products : Share on LinkedIn + Sign In with LinkedIn
- Variables : `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_ID`
- Trouver le person ID : appel à `https://api.linkedin.com/v2/me` avec le token
- Note : token expire → rafraîchir tous les 60 jours

---

## Site planning — Configuration finale

Après création de Supabase, mettre à jour `site/app.js` lignes 2-3 :
```js
const SUPABASE_URL = "https://XXXXXXXX.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGci...";
```

---

## Test local

```bash
# Installer les dépendances
pip install -r requirements.txt

# Copier et remplir le .env
cp .env.example .env
# Éditer .env avec vos clés

# Charger le .env
set -a && source .env && set +a  # Linux/Mac
# Windows PowerShell :
Get-Content .env | ForEach-Object { $k,$v=$_.Split('=',2); [System.Environment]::SetEnvironmentVariable($k,$v) }

# Tester le scraper seul
cd pipeline && python scraper.py

# Tester la dataviz seule (génère des PNG de test)
python dataviz.py

# Tester l'analyzer seul
python analyzer.py

# Lancer le pipeline complet
python main.py
```

---

## Ordre de mise en place recommandé

1. [ ] Créer compte Groq → récupérer API key
2. [ ] Créer projet Supabase → créer table `posts` + bucket `post-images`
3. [ ] Créer repo GitHub `media-auto` → push le code
4. [ ] Ajouter Groq + Supabase dans les Secrets GitHub
5. [ ] Tester `workflow_dispatch` (déclenchement manuel) dans GitHub Actions
6. [ ] Mettre à jour `site/app.js` avec les creds Supabase
7. [ ] Activer GitHub Pages sur `/site`
8. [ ] Configurer ntfy topic + ajouter secret
9. [ ] Configurer X, Instagram, LinkedIn (en dernier — plus complexe)

---

## Ajouter des sources RSS

Éditer uniquement `pipeline/sources.py` — ajouter un dict dans la liste `SOURCES`.

## Modifier la sélection des articles

Éditer `pipeline/analyzer.py` — changer le seuil dans `keep` (actuellement score >= 6).

## Modifier l'identité visuelle

Éditer `pipeline/dataviz.py` — les constantes `BG`, `YELLOW`, `WHITE` en haut du fichier.
