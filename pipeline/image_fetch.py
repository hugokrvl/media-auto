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
    # Mots de format / live-blog souvent EN MAJUSCULE en tête de titre (Le Monde…)
    "direct", "live", "video", "reportage", "analyse", "tribune", "edito",
    "editorial", "exclusif", "enquete", "entretien", "interview", "recit",
    "chronique", "temoignage", "decryptage", "infographie", "carte", "vrai", "faux",
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
    "ia":        "artificial intelligence technology",
    "crypto":    "cryptocurrency blockchain bitcoin",
    "quantique": "quantum computing physics laboratory",
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


# Indices d'œuvres d'art / peintures anciennes dans un nom de fichier → à écarter
# (on veut une PHOTO, pas un portrait peint d'un homonyme du 17e siècle).
_PAINTING = {
    "bildnis", "gemalde", "peinture", "ritratto", "retrato", "canvas", "fresco",
    "portrait d homme", "portrait de femme", "portrait of a", "self portrait",
    "autoportrait", "huile sur", "oil on", "tableau", "ecole francaise",
    "homme de guerre", "engraving", "gravure", "lithograph", "litho", "lithographie",
    "pfann", "daguerreotype", "etching", "woodcut", "miniatur", "portraitof",
}

# Prénoms courants : ne JAMAIS chercher une image avec un prénom SEUL (sinon on matche
# un homonyme : "Eric" → Eric Boe l'astronaute, "Christine" → Christine Nilsson).
_FIRST_NAMES = {
    "eric", "christine", "emmanuel", "donald", "jean", "pierre", "marie", "paul",
    "jacques", "francois", "nicolas", "michel", "philippe", "andre", "louis",
    "charles", "henri", "claude", "bernard", "alain", "daniel", "robert", "david",
    "john", "james", "michael", "william", "richard", "thomas", "george", "joseph",
    "kevin", "mark", "elon", "jeff", "bill", "steve", "tim", "sam", "max", "anna",
    "sophie", "julie", "laura", "sarah", "emma", "alex", "antoine", "olivier",
    "vladimir", "volodymyr", "joe", "kamala", "boris", "olaf", "giorgia", "rishi",
}


def _looks_like_painting(filename: str) -> bool:
    fn = re.sub(r"[^a-z0-9]+", " ", _norm_word(filename))
    return any(p in fn for p in _PAINTING)


def _is_historical(filename: str) -> bool:
    """Vrai si le nom de fichier référence une année ancienne (≤ 1965) → personnage
    historique / homonyme mort (ex : 'Herman Schwab (1861-1951)'), pas le sujet d'actu."""
    years = [int(y) for y in re.findall(r"1[5-9]\d\d", filename)]
    return any(y <= 1965 for y in years)


def _token_in(needle: str, haystack: str) -> bool:
    """Vrai si `needle` est un MOT ENTIER de `haystack` (évite direct⊂directeur)."""
    h = re.sub(r"[^a-z0-9]+", " ", _norm_word(haystack))
    return f" {needle} " in f" {h} "


def _wikipedia_pageimage(name: str) -> str | None:
    """Image d'infobox Wikipédia pour une entité nommée (personne, lieu, société,
    sujet). Bien plus fiable qu'une recherche Commons : c'est LA photo canonique.
    Ex : 'Volodymyr Zelensky' → son portrait officiel ; 'Canicule' → soleil/chaleur."""
    for lang in ("fr", "en"):
        params = urllib.parse.urlencode({
            "action": "query", "titles": name, "prop": "pageimages",
            "piprop": "thumbnail", "pithumbsize": "1000",
            "format": "json", "redirects": "1",
        })
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            for p in data.get("query", {}).get("pages", {}).values():
                src = p.get("thumbnail", {}).get("source", "")
                fn = src.split("/")[-1]   # filtre sur le NOM DE FICHIER, pas l'URL
                if src and not _looks_like_painting(fn) \
                        and not any(s in _norm_word(fn) for s in _WIKI_SKIP):
                    print(f"[WIKIPEDIA] Image infobox : {name} → {fn[:50]}")
                    return src
        except Exception:
            continue
    return None


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
            if _looks_like_painting(title) or _is_historical(title):  # peinture/homonyme ancien
                continue
            # Match par MOT ENTIER (direct ne doit pas matcher directeur)
            if prefer_norm and _token_in(prefer_norm, title):
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
    Image pour les entités nommées du titre, par ordre de fiabilité :
    1. Image d'INFOBOX Wikipédia (la photo canonique de l'entité — ultra fiable)
    2. Recherche Commons STRICTE (mot entier dans le fichier, sans peinture)
    Si aucun nom propre exploitable → None (l'appelant bascule sur Unsplash concept).
    """
    title_orig = (article.get("title_fr") or article.get("title", ""))
    proper = [w for w in re.findall(r'\b[A-ZÀ-Ÿ][a-zà-ÿA-ZÀ-Ÿ]{2,}\b', title_orig)
              if _is_proper(w)]
    if not proper:
        return None   # sujet sans nom propre → Unsplash concept s'en charge

    # Entités candidates :
    #  - PAIRES ADJACENTES d'abord (un nom de personne = prénom + nom CONSÉCUTIFS,
    #    ex "Eric Schmidt" et non "NASA Eric")
    #  - puis noms propres SEULS, mais JAMAIS un prénom isolé (→ homonymes)
    pairs = [f"{proper[i]} {proper[i+1]}" for i in range(len(proper) - 1)][:3]
    singles = [p for p in proper
               if _norm_word(p) not in _FIRST_NAMES and len(p) >= 4][:3]
    seen: set[str] = set()
    entities = [e for e in (pairs + singles)
                if not (e.lower() in seen or seen.add(e.lower()))]

    # 1. Infobox Wikipédia (résout les redirections : Zelensky → Volodymyr Zelensky)
    for ent in entities:
        url = _wikipedia_pageimage(ent)
        if url:
            return url

    # 2. Repli : recherche Commons stricte, UNIQUEMENT pour les entités MULTI-MOTS
    #    (noms complets). Un nom isolé ("Schwab") matche trop d'homonymes → on s'abstient
    #    et on laisse Unsplash fournir une photo de concept pertinente.
    for ent in entities:
        if " " not in ent:
            continue
        last = _norm_word(ent.split()[-1])
        for q in (f"{ent} portrait", ent):
            url = _fetch_wikimedia(q, prefer_name=last)
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


def download_image(url: str, retries: int = 3) -> bytes | None:
    """Télécharge une image depuis une URL. Retry avec backoff sur 429 (rate-limit)."""
    import time
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"[IMAGE] Erreur téléchargement: HTTP {e.code}")
            return None
        except Exception as e:
            print(f"[IMAGE] Erreur téléchargement: {type(e).__name__}: {e}")
            return None
    return None
