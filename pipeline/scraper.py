"""
Scrape les flux RSS et retourne les articles des dernières 24h.
"""

import feedparser
import time
from datetime import datetime, timedelta, timezone
from sources import SOURCES


def fetch_articles(hours_back: int = 24) -> list[dict]:
    """Retourne tous les articles publiés dans les dernières `hours_back` heures."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []

    for source in SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                pub_date = _parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue

                articles.append({
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "summary": _clean_summary(entry.get("summary", entry.get("description", ""))),
                    "published": pub_date.isoformat() if pub_date else None,
                    "source": source["name"],
                    "category": source["category"],
                })
            time.sleep(0.3)  # respecte les serveurs
        except Exception as e:
            print(f"[SCRAPER] Erreur sur {source['name']}: {e}")

    print(f"[SCRAPER] {len(articles)} articles récupérés ({hours_back}h)")
    return articles


def _parse_date(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_summary(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]


if __name__ == "__main__":
    articles = fetch_articles()
    for a in articles[:5]:
        print(f"[{a['category']}] {a['source']} — {a['title'][:80]}")
