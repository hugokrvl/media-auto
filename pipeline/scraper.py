"""
Scrape les sources et retourne les articles des dernières 24h.
Trois types de sources (voir sources.py) : rss, youtube, email.
"""

import os
import re
import time
import feedparser
from datetime import datetime, timedelta, timezone

import youtube
from sources import SOURCES
from email_sources import fetch_newsletters

# Plafond d'articles gardés PAR source (les flux Google News renvoient jusqu'à 100).
# Évite qu'une source noie les autres dans les 60 analysés par l'analyzer.
MAX_PER_SOURCE = int(os.environ.get("SCRAPER_MAX_PER_SOURCE", "12"))


def fetch_articles(hours_back: int = 24) -> list[dict]:
    """Articles des dernières `hours_back` h, ENTRELACÉS (round-robin) entre sources
    pour que les 60 premiers analysés couvrent toutes les catégories."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    per_source = []  # une liste d'articles par source (plafonnée)

    for source in SOURCES:
        stype = source.get("type", "rss")
        try:
            if stype == "email":
                items = fetch_newsletters(hours_back, source.get("category", "general"))
            elif stype == "youtube":
                items = _fetch_youtube(source, cutoff)
            else:
                items = _fetch_rss(source, cutoff)
            if items:
                per_source.append(items[:MAX_PER_SOURCE])
            time.sleep(0.3)  # respecte les serveurs
        except Exception as e:
            print(f"[SCRAPER] Erreur sur {source['name']}: {e}")

    # Entrelacement round-robin : 1er de chaque source, puis 2e de chaque, etc.
    articles = []
    depth = 0
    while True:
        added = False
        for items in per_source:
            if depth < len(items):
                articles.append(items[depth])
                added = True
        if not added:
            break
        depth += 1

    print(f"[SCRAPER] {len(articles)} articles récupérés ({hours_back}h, "
          f"{len(per_source)} sources, max {MAX_PER_SOURCE}/source)")
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
