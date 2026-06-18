"""
Support YouTube pour le scraper.

1. resolve_feed(url)   : page de chaîne (@handle, /c/..., /channel/UC...) -> flux RSS
2. get_transcript(vid) : transcription auto (fr puis en) -> texte, "" si indispo

⚠️  La transcription échoue souvent depuis les serveurs cloud (GitHub Actions) car
    YouTube bloque les IP de datacenter. Le scraper retombe alors sur la description
    de la vidéo (toujours présente dans le flux RSS). Aucune intervention manuelle
    n'est possible : le pipeline tourne sans humain à 1h du matin.
"""

import re
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_feed_cache: dict[str, str] = {}


def _fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def resolve_feed(channel_url: str) -> str | None:
    """Transforme une URL de chaîne en URL de flux RSS YouTube.
    Le flux RSS n'accepte que channel_id (UC...) : on le résout depuis la page."""
    if channel_url in _feed_cache:
        return _feed_cache[channel_url]

    # Cas direct : /channel/UCxxxx
    m = re.search(r"/channel/(UC[\w-]{20,})", channel_url)
    if m:
        feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
        _feed_cache[channel_url] = feed
        return feed

    # Sinon (@handle ou /c/Nom) : on lit la page et on extrait le channelId
    try:
        html = _fetch(channel_url)
    except Exception as e:
        print(f"[YOUTUBE] Résolution échouée pour {channel_url}: {e}")
        return None

    for pat in (r'"channelId":"(UC[\w-]{20,})"',
                r'"externalId":"(UC[\w-]{20,})"',
                r'channel_id=(UC[\w-]{20,})',
                r'<meta itemprop="identifier" content="(UC[\w-]{20,})">'):
        m = re.search(pat, html)
        if m:
            feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
            _feed_cache[channel_url] = feed
            return feed

    print(f"[YOUTUBE] channelId introuvable dans {channel_url}")
    return None


def video_id(entry) -> str | None:
    """Extrait l'id vidéo d'une entrée de flux YouTube."""
    vid = entry.get("yt_videoid")
    if vid:
        return vid
    link = entry.get("link", "")
    m = re.search(r"(?:v=|/watch\?v=|youtu\.be/)([\w-]{11})", link)
    return m.group(1) if m else None


def _snippet_text(s) -> str:
    """Texte d'un segment de transcription (dict en API 0.x, objet .text en 1.x)."""
    if isinstance(s, dict):
        return s.get("text", "")
    return getattr(s, "text", "")


def get_transcript(vid: str, max_chars: int = 20000) -> str:
    """Transcription auto (fr -> en). '' si indisponible. Compatible
    youtube-transcript-api 0.x (classmethod) ET 1.x (instance). Repli silencieux."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return ""  # lib non installée -> on s'appuiera sur la description
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            # API 0.x
            chunks = YouTubeTranscriptApi.get_transcript(vid, languages=["fr", "en"])
        else:
            # API 1.x : instance + fetch()
            chunks = YouTubeTranscriptApi().fetch(vid, languages=["fr", "en"])
        text = " ".join(_snippet_text(c) for c in chunks if _snippet_text(c))
        return re.sub(r"\s+", " ", text).strip()[:max_chars]
    except Exception as e:
        print(f"[YOUTUBE] Transcription indispo ({vid}): {type(e).__name__}")
        return ""
