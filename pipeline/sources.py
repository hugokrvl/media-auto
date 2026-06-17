"""
Liste centralisée des sources RSS.
Ajouter/retirer des sources ici sans toucher au reste du code.
"""

SOURCES = [
    # Finance / Économie
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "category": "finance"},
    {"name": "Les Échos", "url": "https://syndication.lesechos.fr/rss/rss_une.xml", "category": "finance"},
    {"name": "Boursorama", "url": "https://www.boursorama.com/rss/actualites/", "category": "finance"},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "finance"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "finance"},

    # Tech
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tech"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tech"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech"},
    {"name": "01net", "url": "https://www.01net.com/rss/feed/news/", "category": "tech"},
    {"name": "Numerama", "url": "https://www.numerama.com/feed/", "category": "tech"},

    # Actu générale
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "category": "general"},
    {"name": "Le Monde", "url": "https://www.lemonde.fr/rss/une.xml", "category": "general"},
    {"name": "France Info", "url": "https://www.francetvinfo.fr/titres.rss", "category": "general"},
    {"name": "Reuters Top News", "url": "https://feeds.reuters.com/reuters/topNews", "category": "general"},

    # Sport
    {"name": "L'Équipe", "url": "https://www.lequipe.fr/rss/actu_rss.xml", "category": "sport"},
    {"name": "ESPN", "url": "https://www.espn.com/espn/rss/news", "category": "sport"},
    {"name": "RMC Sport", "url": "https://rmcsport.bfmtv.com/rss/", "category": "sport"},

    # Fact-check
    {"name": "AFP Factuel", "url": "https://factuel.afp.com/feed", "category": "factcheck"},
    {"name": "Les Décodeurs", "url": "https://www.lemonde.fr/les-decodeurs/rss_full.xml", "category": "factcheck"},
]

CATEGORIES = ["finance", "tech", "general", "sport", "factcheck"]
