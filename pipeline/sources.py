"""
Liste centralisée des sources.

Chaque source a un `type` :
  • "rss"     (défaut) — flux RSS/Atom classique, champ `url`
  • "youtube"           — chaîne YouTube, champ `url` = page de la chaîne
                          (le scraper résout le flux + récupère la transcription)
  • "email"             — newsletters reçues sur la boîte dédiée (voir email_sources.py)

Sources NON ajoutables (volontairement exclues) :
  • Profils X / Twitter  → aucun flux RSS, scraping bloqué (API payante 100$/mois)
  • Profils Instagram    → aucun flux public, nécessite l'API Graph d'un compte business
  → Pour ces créateurs (Baccino, Hasheur, Chéron), on récupère à la place leur
    YouTube + site web + newsletter, qui sont accessibles gratuitement.

⚠️  Certaines URLs RSS ci-dessous sont des "meilleures hypothèses" non vérifiables
    depuis l'environnement de dev. Lancer `python validate_sources.py` pour tester
    chaque flux en réel et retirer/corriger ceux qui ne répondent pas.
"""

SOURCES = [
    # ── Finance / Économie (presse) ───────────────────────────────────────────
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "category": "finance"},
    {"name": "Les Échos", "url": "https://syndication.lesechos.fr/rss/rss_une.xml", "category": "finance"},
    {"name": "Les Échos Investir", "url": "https://investir.lesechos.fr/feed/", "category": "finance"},  # ? à valider
    {"name": "Boursorama", "url": "https://www.boursorama.com/rss/actualites/", "category": "finance"},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "finance"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "finance"},
    {"name": "Zone Bourse", "url": "https://www.zonebourse.com/rss/", "category": "finance"},  # ? à valider
    {"name": "Aktionnaire", "url": "https://www.aktionnaire.com/feed/", "category": "finance"},  # ? à valider

    # ── Finance internationale (premium, titres en accès libre) ────────────────
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home", "category": "finance"},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "category": "finance"},
    {"name": "WSJ World", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "category": "finance"},

    # ── Statistiques / Sondages (data brute, idéale pour la dataviz) ───────────
    {"name": "INSEE Conjoncture", "url": "https://www.insee.fr/fr/information/rss", "category": "finance"},  # ? à valider
    {"name": "Ipsos France", "url": "https://www.ipsos.com/fr-fr/rss.xml", "category": "general"},  # ? à valider

    # ── Tech ──────────────────────────────────────────────────────────────────
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tech"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tech"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech"},
    {"name": "01net", "url": "https://www.01net.com/rss/feed/news/", "category": "tech"},
    {"name": "Numerama", "url": "https://www.numerama.com/feed/", "category": "tech"},

    # ── Actu générale (nationale + régionale) ─────────────────────────────────
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "category": "general"},
    {"name": "Le Monde", "url": "https://www.lemonde.fr/rss/une.xml", "category": "general"},
    {"name": "France Info", "url": "https://www.francetvinfo.fr/titres.rss", "category": "general"},
    {"name": "Le Parisien", "url": "https://feeds.leparisien.fr/leparisien/rss", "category": "general"},
    {"name": "Ouest-France", "url": "https://www.ouest-france.fr/rss-en-continu.xml", "category": "general"},
    {"name": "Le Télégramme", "url": "https://www.letelegramme.fr/rss.xml", "category": "general"},  # ? à valider

    # ── Sport ─────────────────────────────────────────────────────────────────
    {"name": "L'Équipe", "url": "https://www.lequipe.fr/rss/actu_rss.xml", "category": "sport"},
    {"name": "RMC Sport", "url": "https://rmcsport.bfmtv.com/rss/", "category": "sport"},

    # ── Fact-check ────────────────────────────────────────────────────────────
    {"name": "AFP Factuel", "url": "https://factuel.afp.com/feed", "category": "factcheck"},
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

    # ── Sites créateurs (RSS WordPress si dispo) ──────────────────────────────
    {"name": "Hasheur", "url": "https://hasheur.com/feed/", "category": "finance"},  # ? à valider
    {"name": "Nicolas Chéron", "url": "https://www.nicolascheron.fr/feed/", "category": "finance"},  # ? à valider

    # ── Newsletters (lues sur la boîte mail dédiée — voir email_sources.py) ────
    {"name": "Newsletters (email)", "type": "email", "category": "general"},
]

CATEGORIES = ["finance", "tech", "general", "sport", "factcheck"]
