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

# Traductions simples FR→EN pour de meilleurs résultats Pexels
_TRANSLATE = {
    "bourse": "stock market", "marché": "market", "économie": "economy",
    "finance": "finance", "banque": "bank", "taux": "interest rate",
    "inflation": "inflation", "croissance": "growth", "récession": "recession",
    "entreprise": "company", "intelligence artificielle": "artificial intelligence",
    "technologie": "technology", "crypto": "cryptocurrency", "bitcoin": "bitcoin",
    "politique": "politics", "président": "president", "gouvernement": "government",
    "élection": "election", "guerre": "war", "conflit": "conflict",
    "sport": "sport", "football": "football", "tennis": "tennis",
    "santé": "health", "énergie": "energy", "climat": "climate",
    "emploi": "employment", "chômage": "unemployment",
}


def _keywords(article: dict) -> str:
    """Extrait 3-5 mots-clés EN pour la recherche Pexels."""
    raw = (article.get("title_fr") or article.get("title", "")).lower()
    # Traductions longues d'abord
    for fr, en in sorted(_TRANSLATE.items(), key=lambda x: -len(x[0])):
        raw = raw.replace(fr, en)
    # Nettoyer ponctuation
    raw = re.sub(r"[^\w\s]", " ", raw)
    words = [w for w in raw.split() if len(w) > 3 and w not in _STOP]
    # Ajouter la catégorie pour ancrer le contexte
    cat_map = {"finance": "economy", "tech": "technology",
               "sport": "sports", "general": "news", "factcheck": "journalism"}
    cat = cat_map.get(article.get("category", ""), "")
    if cat and cat not in words:
        words.insert(0, cat)
    return " ".join(words[:5])


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
