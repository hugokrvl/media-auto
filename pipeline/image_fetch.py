"""
Récupération d'images libres de droits pour les posts Breaking News.

Ordre de priorité :
1. Wikimedia Commons  — sans clé, photos éditoriales réelles (chefs d'État, villes,
                        événements) sous licence libre (CC-BY-SA / domaine public)
2. Unsplash           — clé UNSPLASH_ACCESS_KEY, photos créatives haute qualité
3. Pexels             — clé PEXELS_API_KEY, fallback final
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

# Mots français/anglais souvent EN MAJUSCULE en début de titre mais qui NE SONT PAS
# des noms propres (sinon on cherche "Comment portrait" → peinture aléatoire).
# Comparés sans accents/casse.
_NOT_PROPER = {
    "comment", "pourquoi", "quand", "selon", "voici", "voila", "ainsi", "alors",
    "depuis", "cependant", "toutefois", "neanmoins", "malgre", "apres", "avant",
    "contre", "entre", "vers", "chez", "quel", "quelle", "quels", "quelles",
    "combien", "faut", "faire", "cette", "cet", "ces", "leur", "leurs", "notre",
    "votre", "nos", "vos", "donc", "car", "plus", "moins", "tout", "tous", "toute",
    "toutes", "grand", "grande", "nouveau", "nouvelle", "encore", "enfin", "bientot",
    "this", "that", "these", "those", "what", "why", "when", "which", "their",
    "there", "here", "with", "from", "into", "over", "under", "about", "how",
    # Pays / régions / gentilés : mauvais ancrages d'image (donnent une place, un
    # drapeau ou un lieu hors-sujet). Restent utiles comme contexte Unsplash, pas
    # comme sujet Wikimedia. + marques ambiguës (mot commun ET société).
    "france", "etats", "unis", "etatsunis", "iran", "chine", "japon", "allemagne",
    "espagne", "italie", "russie", "ukraine", "royaume", "europe", "afrique",
    "asie", "amerique", "americain", "americaine", "francais", "francaise",
    "chinois", "chinoise", "japonais", "russe", "allemand", "espagnol", "italien",
    "britannique", "europeen", "europeenne", "occident", "occidental",
    "visa", "total", "orange", "free",
}


def _norm_word(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _is_proper(w: str) -> bool:
    """Vrai si le mot est un vrai nom propre candidat (pas un mot-outil capitalisé).
    Exige une vraie MAJUSCULE en tête : la regex À-Ÿ capture aussi les minuscules
    accentuées (é, è, à…), qu'on rejette ici."""
    if len(w) <= 2 or not w[:1].isupper():
        return False
    wn = _norm_word(w)
    return wn not in _STOP and wn not in _NOT_PROPER

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


_WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
# Extensions photo acceptées (exclut SVG, diagrammes, icônes)
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
# Mots à éviter dans les noms de fichiers Wikimedia (cartes, drapeaux, logos…)
_WIKI_SKIP = {"map", "flag", "logo", "icon", "diagram", "chart", "coat",
              "arms", "seal", "emblem", "banner", "template", "svg",
              "screenshot", "screen", "aufmacher", "capture", "scherm",
              "example", "sample", "interface", "demo", "chatgpt", "openai",
              "wikipedia", "wikimedia", "commons"}


def _fetch_wikimedia(query: str, prefer_name: str | None = None) -> str | None:
    """
    Cherche une photo sur Wikimedia Commons (sans clé API).
    prefer_name : mot-clé à prioriser dans le nom de fichier (ex: "mbappe", "macron")
                  → les fichiers dont le nom contient ce mot passent en tête,
                    ce qui favorise un portrait individuel plutôt qu'une photo de groupe.
    """
    import unicodedata
    def _norm(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    search_params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",
        "srlimit": "25",
        "format": "json",
    })
    req = urllib.request.Request(
        f"{_WIKIMEDIA_API}?{search_params}",
        headers={"User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = data.get("query", {}).get("search", [])
        if not results:
            return None

        prefer_norm = _norm(prefer_name) if prefer_name else None

        # Sépare les candidats en deux listes : portrait individuel vs groupe/autre
        candidates_prio = []
        candidates_rest = []
        for item in results:
            title = item.get("title", "")
            tl = title.lower()
            tl_norm = _norm(title)
            ext = next((e for e in _PHOTO_EXT if tl.endswith(e)), None)
            if not ext:
                continue
            if any(skip in tl for skip in _WIKI_SKIP):
                continue
            if prefer_norm and prefer_norm in tl_norm:
                candidates_prio.append(title)
            else:
                candidates_rest.append(title)
            if len(candidates_prio) + len(candidates_rest) >= 8:
                break

        # Si on cherche un nom propre précis (personne/marque), on est STRICT :
        # on n'accepte QUE les fichiers dont le nom contient ce nom propre.
        # Sinon on renverrait une image hors-sujet (peinture, photo random).
        # → quand rien ne matche, on renvoie None et la cascade bascule sur Unsplash.
        if prefer_norm:
            candidates = candidates_prio[:3]
            if not candidates:
                return None
        else:
            candidates = candidates_rest[:3]
        if not candidates:
            return None

        info_params = urllib.parse.urlencode({
            "action": "query",
            "titles": "|".join(candidates),
            "prop": "imageinfo",
            "iiprop": "url|mime|size",
            "iiurlwidth": "1080",
            "format": "json",
        })
        req2 = urllib.request.Request(
            f"{_WIKIMEDIA_API}?{info_params}",
            headers={"User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)"},
        )
        with urllib.request.urlopen(req2, timeout=10) as r:
            info = json.loads(r.read())

        # Trier les pages : portraits nommés en premier
        pages = list(info.get("query", {}).get("pages", {}).values())
        if prefer_norm:
            pages.sort(key=lambda p: 0 if prefer_norm in _norm(p.get("title", "")) else 1)

        for page in pages:
            ii = page.get("imageinfo", [{}])[0]
            mime = ii.get("mime", "")
            if not mime.startswith("image/") or mime == "image/svg+xml":
                continue
            if ii.get("width", 0) < 400:
                continue
            url = ii.get("thumburl") or ii.get("url")
            if url:
                print(f"[WIKIMEDIA] Photo trouvée : {page.get('title','')[:60]}")
                return url

        return None
    except Exception as e:
        print(f"[WIKIMEDIA] Erreur ({query!r}): {type(e).__name__}: {e}")
        return None


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


def _wikimedia_cascade(article: dict) -> str | None:
    """
    Wikimedia UNIQUEMENT pour les noms propres (personnes, lieux, marques précises).
    On exige que le nom propre figure dans le nom du fichier (strict) → on évite les
    images hors-sujet. Si aucun nom propre exploitable, on renvoie None et l'appelant
    bascule sur Unsplash (photo de concept, bien plus pertinente pour un sujet abstrait).
    """
    title_orig = (article.get("title_fr") or article.get("title", ""))
    proper = [w for w in re.findall(r'\b[A-ZÀ-Ÿ][a-zà-ÿA-ZÀ-Ÿ]{2,}\b', title_orig)
              if _is_proper(w)]
    if not proper:
        return None   # sujet sans nom propre → Wikimedia inadapté, Unsplash s'en charge

    # Requêtes du plus spécifique au plus large, TOUTES filtrées sur le nom propre.
    # 1) Si 2 noms propres (prénom + nom) : on tente d'abord le NOM COMPLET filtré sur
    #    le NOM DE FAMILLE → évite de matcher un homonyme par le seul prénom
    #    (ex : "Christine" seul trouvait la cantatrice Christine Nilsson, pas Lagarde).
    # 2) Puis CHAQUE nom propre individuellement → si "Windcoop"/"Sailcoop" ne donnent
    #    rien, on tente "Marseille", "Madagascar"… avant de basculer sur Unsplash.
    queries: list[tuple[str, str]] = []
    if len(proper) >= 2:
        full = " ".join(proper[:2])
        last = _norm_word(proper[1])
        queries += [(f"{full} portrait", last), (full, last)]
    for p in proper[:4]:
        queries.append((f"{p} portrait", _norm_word(p)))
        queries.append((p, _norm_word(p)))
    seen = set()
    queries = [(q, pr) for q, pr in queries if not (q in seen or seen.add(q))]

    for q, prefer in queries:
        if not q or len(q) < 3:
            continue
        url = _fetch_wikimedia(q, prefer_name=prefer)
        if url:
            return url
    return None


def fetch_photo_url(article: dict, orientation: str = "square") -> str | None:
    """
    Cherche une photo libre de droits.
    Priorité : Wikimedia (cascade noms propres → sujet) → Unsplash → Pexels.
    """
    query = _keywords(article)

    # Wikimedia : cascade de requêtes du plus spécifique au plus large
    url = _wikimedia_cascade(article)

    # Fallback créatif : Unsplash puis Pexels
    if not url:
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
