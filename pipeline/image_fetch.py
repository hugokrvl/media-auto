"""
Récupération d'images libres de droits via l'API Pexels.

Utilisé pour les posts "breaking news" : photo pertinente + overlay titre.
Nécessite la variable d'environnement PEXELS_API_KEY (clé gratuite sur pexels.com).
Sans clé → retourne None (pipeline non bloqué).
"""

import os
import re
import urllib.request
import urllib.parse
import json

PEXELS_API_KEY    = os.environ.get("PEXELS_API_KEY", "")
PEXELS_SEARCH     = "https://api.pexels.com/v1/search"
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
UNSPLASH_SEARCH   = "https://api.unsplash.com/search/photos"

# Mots inutiles pour la recherche (stopwords FR + EN)
_STOP = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "en", "à", "au",
    "aux", "est", "son", "sa", "ses", "sur", "par", "pour", "que", "qui", "ce",
    "se", "il", "elle", "ils", "elles", "nous", "vous", "on", "mais", "ou",
    "the", "a", "an", "of", "in", "to", "for", "on", "at", "is", "are", "with",
    "its", "by", "from", "that", "this", "as", "be", "was", "were",
}

# Traductions FR→EN (longues en premier pour éviter les remplacements partiels)
_TRANSLATE = {
    # Finance
    "intelligence artificielle": "artificial intelligence",
    "taux d'intérêt": "interest rate", "taux directeur": "key interest rate",
    "bourse": "stock market", "marché financier": "financial market",
    "banque centrale": "central bank", "réserve fédérale": "federal reserve",
    "inflation": "inflation", "récession": "recession", "croissance": "economic growth",
    "chômage": "unemployment", "emploi": "employment",
    "cryptomonnaie": "cryptocurrency", "bitcoin": "bitcoin",
    "entreprise": "business", "marché": "market", "banque": "bank",
    "économie": "economy", "finance": "finance", "taux": "interest rate",
    # Actualité / politique
    "guerre": "war", "conflit armé": "armed conflict", "conflit": "conflict",
    "attaque": "attack", "drone": "drone", "missile": "missile",
    "ukraine": "ukraine", "russie": "russia", "moscou": "moscow",
    "élection": "election", "président": "president", "gouvernement": "government",
    "politique": "politics", "parlement": "parliament",
    # Météo / environnement
    "canicule": "heatwave", "vague de chaleur": "heat wave", "chaleur": "heat",
    "inondation": "flood", "incendie": "wildfire", "tempête": "storm",
    "sécheresse": "drought", "climat": "climate", "environnement": "environment",
    "énergie": "energy", "nucléaire": "nuclear",
    # Tech
    "technologie": "technology", "intelligence": "artificial intelligence",
    "robot": "robot", "données": "data",
    # Sport
    "football": "football", "tennis": "tennis", "cyclisme": "cycling",
    "sport": "sport", "coupe du monde": "world cup", "jeux olympiques": "olympic games",
    # Santé
    "santé": "health", "hôpital": "hospital", "médecin": "doctor",
    "épidémie": "epidemic", "vaccin": "vaccine",
}

# Mots-clés de contexte par catégorie (REMPLACE "news" trop générique)
_CAT_CONTEXT = {
    "finance":   "finance economy",
    "tech":      "technology digital",
    "sport":     "sport athlete",
    "general":   "",          # pas d'ancrage générique → on laisse les mots du titre
    "factcheck": "journalism media",
}


def _keywords(article: dict) -> str:
    """Extrait 3-5 mots-clés EN pour la recherche d'image."""
    raw = (article.get("title_fr") or article.get("title", "")).lower()
    # Normalise les accents pour la correspondance
    import unicodedata
    raw_norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()

    # Appliquer les traductions (longues d'abord)
    for fr, en in sorted(_TRANSLATE.items(), key=lambda x: -len(x[0])):
        fr_norm = unicodedata.normalize("NFKD", fr).encode("ascii", "ignore").decode()
        raw_norm = raw_norm.replace(fr_norm, en)

    # Nettoyer ponctuation + stopwords
    raw_norm = re.sub(r"[^\w\s]", " ", raw_norm)
    words = [w for w in raw_norm.split() if len(w) > 3 and w not in _STOP]

    # Ajouter contexte catégorie si pertinent
    cat = article.get("category", "")
    ctx = _CAT_CONTEXT.get(cat, "")
    if ctx:
        words = ctx.split() + words

    query = " ".join(words[:5])
    print(f"[IMAGE] Requête photo : {query!r} (article: {(article.get('title_fr') or '')[:40]})")
    return query


def _fetch_unsplash(query: str) -> str | None:
    """Recherche Unsplash (prioritaire — licence libre commerciale)."""
    if not UNSPLASH_ACCESS_KEY:
        return None
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": 5,
        "orientation": "squarish",
        "content_filter": "high",
    })
    req = urllib.request.Request(
        f"{UNSPLASH_SEARCH}?{params}",
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        if not results:
            return None
        urls = results[0].get("urls", {})
        return urls.get("regular") or urls.get("full")
    except Exception as e:
        print(f"[UNSPLASH] Erreur ({query!r}): {type(e).__name__}: {e}")
        return None


def _fetch_pexels(query: str) -> str | None:
    """Recherche Pexels (fallback)."""
    if not PEXELS_API_KEY:
        return None
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": 5,
        "orientation": "square",
    })
    req = urllib.request.Request(
        f"{PEXELS_SEARCH}?{params}",
        headers={"Authorization": PEXELS_API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        photos = data.get("photos", [])
        if not photos:
            return None
        src = photos[0].get("src", {})
        return src.get("large2x") or src.get("large") or src.get("original")
    except Exception as e:
        print(f"[PEXELS] Erreur ({query!r}): {type(e).__name__}: {e}")
        return None


def fetch_photo_url(article: dict, orientation: str = "square") -> str | None:
    """Cherche une photo libre de droits (Unsplash en priorité, Pexels en fallback)."""
    query = _keywords(article)
    if not query:
        return None
    url = _fetch_unsplash(query) or _fetch_pexels(query)
    if not url:
        print(f"[IMAGE] Aucune photo trouvée pour : {query!r}")
    return url


def download_image(url: str) -> bytes | None:
    """Télécharge une image depuis une URL. Retourne les bytes ou None."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as e:
        print(f"[PEXELS] Erreur téléchargement: {type(e).__name__}: {e}")
        return None
