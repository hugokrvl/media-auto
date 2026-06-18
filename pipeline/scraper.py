"""
Scrape les sources et retourne les articles des dernières 24h.
Trois types de sources (voir sources.py) : rss, youtube, email.
"""

import re
import time
import feedparser
from datetime import datetime, timedelta, timezone

import youtube
from sources import SOURCES
from email_sources import fetch_newsletters


def fetch_articles(hours_back: int = 24) -> list[dict]:
    """Retourne tous les articles publiés dans les dernières `hours_back` heures."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []

    for source in SOURCES:
        stype = source.get("type", "rss")
        try:
            if stype == "email":
                articles += fetch_newsletters(hours_back, source.get("category", "general"))
            elif stype == "youtube":
                articles += _fetch_youtube(source, cutoff)
            else:
                articles += _fetch_rss(source, cutoff)
            time.sleep(0.3)  # respecte les serveurs
        except Exception as e:
            print(f"[SCRAPER] Erreur sur {source['name']}: {e}")

    print(f"[SCRAPER] {len(articles)} articles récupérés ({hours_back}h)")
    return articles


def _fetch_rss(source: dict, cutoff: datetime) -> list[dict]:
    out = []
    feed = feedparser.parse(source["url"])
    for entry in feed.entries:
        pub_date = _parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue
        out.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "summary": _clean_summary(entry.get("summary", entry.get("description", ""))),
            "published": pub_date.isoformat() if pub_date else None,
            "source": source["name"],
            "category": source["category"],
        })
    return out


def _fetch_youtube(source: dict, cutoff: datetime) -> list[dict]:
    """Résout le flux de la chaîne, puis pour chaque vidéo récente tente la
    transcription (repli sur la description si YouTube bloque l'IP)."""
    feed_url = youtube.resolve_feed(source["url"])
    if not feed_url:
        return []
    out = []
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        pub_date = _parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue
        description = _clean_summary(
            entry.get("summary", entry.get("media_description", "")))
        vid = youtube.video_id(entry)
        transcript = youtube.get_transcript(vid) if vid else ""
        # Le TRIAGE (8b) n'a besoin que d'un résumé court (description ou début de
        # transcription). La transcription COMPLÈTE est gardée à part : elle ne sera
        # "digérée" (extraction des données) qu'au cas où la vidéo passe le triage.
        art = {
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "summary": (description or transcript[:600] or "")[:800],
            "published": pub_date.isoformat() if pub_date else None,
            "source": source["name"],
            "category": source["category"],
        }
        if transcript:
            art["transcript"] = transcript   # complète -> digest en passe 2
            art["is_video"] = True
        out.append(art)
    return out


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
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]


if __name__ == "__main__":
    articles = fetch_articles()
    for a in articles[:8]:
        print(f"[{a['category']}] {a['source']} — {a['title'][:80]}")
