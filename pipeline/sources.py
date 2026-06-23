"""
Liste centralisée des sources.

Chaque source a un `type` :
  • "rss"     (défaut) — flux RSS/Atom classique, champ `url`
  • "youtube"           — chaîne YouTube, champ `url` = page de la chaîne
  • "email"             — newsletters reçues sur la boîte dédiée (email_sources.py)

⚠️ TOUTES les URLs ci-dessous ont été validées en réel (python validate_sources.py).
Pour les médias dont le flux RSS natif est mort/inexistant, on passe par **Google News**
(`_gn(...)`) qui renvoie les articles récents du domaine — fiable et toujours à jour.
Les URLs des articles sont alors des liens de redirection news.google.com (sans impact
sur l'analyse ; le nom de la source affiché reste le vrai média).

Sources NON ajoutables (exclues volontairement) :
  • Profils X / Twitter  → aucun flux RSS, scraping bloqué (API payante)
  • Profils Instagram    → aucun flux public (API Graph d'un compte business requise)
  → Ces créateurs (Baccino, Hasheur, Chéron) sont couverts par leur YouTube + newsletter.
"""


def _gn(query: str) -> str:
    """Flux Google News (articles récents d'un domaine/sujet). Ex: _gn('site:lesechos.fr when:1d')."""
    from urllib.parse import quote
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=fr&gl=FR&ceid=FR:fr"


SOURCES = [
    # ── Finance / Économie (presse FR) ────────────────────────────────────────
    {"name": "Les Échos", "url": _gn("site:lesechos.fr when:1d"), "category": "finance"},
    {"name": "Les Échos Investir", "url": _gn("site:investir.lesechos.fr when:2d"), "category": "finance"},
    {"name": "Boursorama", "url": _gn("site:boursorama.com when:1d"), "category": "finance"},
    {"name": "Zone Bourse", "url": _gn("site:zonebourse.com when:1d"), "category": "finance"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "finance"},

    # ── Finance internationale (premium, titres en accès libre) ────────────────
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home", "category": "finance"},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "category": "finance"},
    {"name": "WSJ World", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "category": "finance"},

    # ── Statistiques / Sondages (data brute, idéale pour la dataviz) ───────────
    {"name": "INSEE", "url": _gn("site:insee.fr when:7d"), "category": "finance"},
    {"name": "Ipsos France", "url": "https://www.ipsos.com/fr-fr/rss.xml", "category": "general"},

    # ── Tech ──────────────────────────────────────────────────────────────────
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tech"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tech"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tech"},
    {"name": "The Register", "url": "https://www.theregister.com/headlines.atom", "category": "tech"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "tech"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage?points=150", "category": "tech"},
    {"name": "01net", "url": "https://www.01net.com/feed/", "category": "tech"},
    {"name": "Numerama", "url": "https://www.numerama.com/feed/", "category": "tech"},

    # ── Intelligence artificielle ─────────────────────────────────────────────
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "category": "ia"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "category": "ia"},
    # site:anthropic.com non indexé par Google News (0 résultat) → requête par sujet (marque).
    {"name": "Anthropic", "url": _gn("Anthropic Claude AI when:7d"), "category": "ia"},
    # site: sans le chemin /news (le path casse l'opérateur site:).
    {"name": "Mistral AI", "url": _gn("site:mistral.ai when:21d"), "category": "ia"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "category": "ia"},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/", "category": "ia"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "ia"},

    # ── Blockchain / Crypto ───────────────────────────────────────────────────
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "crypto"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "category": "crypto"},
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "category": "crypto"},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "category": "crypto"},
    {"name": "DL News", "url": "https://www.dlnews.com/arc/outboundfeeds/rss/", "category": "crypto"},

    # ── Informatique quantique ────────────────────────────────────────────────
    {"name": "Quanta Magazine", "url": "https://www.quantamagazine.org/feed/", "category": "quantique"},
    {"name": "The Quantum Insider", "url": "https://thequantuminsider.com/feed/", "category": "quantique"},

    # ── Actu générale (nationale + régionale) ─────────────────────────────────
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "category": "general"},
    {"name": "Le Monde", "url": "https://www.lemonde.fr/rss/une.xml", "category": "general"},
    {"name": "France Info", "url": "https://www.francetvinfo.fr/titres.rss", "category": "general"},
    {"name": "Le Parisien", "url": "https://feeds.leparisien.fr/leparisien/rss", "category": "general"},
    {"name": "Ouest-France", "url": "https://www.ouest-france.fr/rss-en-continu.xml", "category": "general"},
    {"name": "Le Télégramme", "url": _gn("site:letelegramme.fr when:1d"), "category": "general"},

    # ── Sport ─────────────────────────────────────────────────────────────────
    {"name": "L'Équipe", "url": "https://dwh.lequipe.fr/api/edito/rss?path=/", "category": "sport"},
    {"name": "RMC Sport", "url": _gn("site:rmcsport.bfmtv.com when:1d"), "category": "sport"},

    # ── Fact-check ────────────────────────────────────────────────────────────
    {"name": "AFP Factuel", "url": _gn("site:factuel.afp.com when:7d"), "category": "factcheck"},
    {"name": "Les Décodeurs", "url": "https://www.lemonde.fr/les-decodeurs/rss_full.xml", "category": "factcheck"},

    # ── Créateurs YouTube (transcription auto + repli description) ─────────────
    {"name": "Nicolas Chéron (YT)", "type": "youtube",
     "url": "https://www.youtube.com/@NCheron_bourse", "category": "finance"},
    {"name": "Matthias Baccino (YT)", "type": "youtube",
     "url": "https://www.youtube.com/@matthiasbaccino", "category": "finance"},
    {"name": "Matthieu Stefani (YT)", "type": "youtube",
     "url": "https://www.youtube.com/c/MatthieuStefani", "category": "general"},
    {"name": "Hasheur (YT)", "type": "youtube",
     "url": "https://www.youtube.com/@Hasheur", "category": "finance"},

    # ── Newsletters (Aktionnaire, Hasheur, Chéron… via la boîte email dédiée) ──
    {"name": "Newsletters (email)", "type": "email", "category": "general"},
]

CATEGORIES = ["finance", "tech", "ia", "crypto", "quantique", "general", "sport", "factcheck"]
