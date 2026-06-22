"""
Sauvegarde les posts et images dans Supabase.
Table : posts | Bucket : post-images
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# Colonnes ajoutées au fil de l'eau (voir CLAUDE.md pour la migration SQL).
# Si elles n'existent pas encore côté Supabase, l'insert retombe sans ces champs.
_DEDUP_COLS = ("topic_key", "data_sig", "is_update", "update_of")
_VIDEO_COLS = ("needs_transcript", "pending_transcript")
_CAROUSEL_COLS = ("slides",)      # text[] : URLs des slides du carrousel (étude data)
_QA_COLS = ("attempts",)          # jsonb : essais ratés à la barrière QA (image+raison+score)
_OPTIONAL_COLS = _DEDUP_COLS + _VIDEO_COLS + _CAROUSEL_COLS + _QA_COLS

# .strip() défensif : un secret collé avec un retour à la ligne casse les en-têtes HTTP.
SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
BUCKET = "post-images"

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def __getattr__(name: str):
    """Permet d'écrire `storage.supabase` (alias paresseux du client Supabase)."""
    if name == "supabase":
        return get_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def upload_image(image_bytes: bytes, filename: str) -> str:
    """Upload une image dans le bucket et retourne son URL publique."""
    sb = get_client()
    path = f"{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/{filename}"
    sb.storage.from_(BUCKET).upload(
        path, image_bytes,
        file_options={"content-type": "image/png", "upsert": "true"}
    )
    public_url = sb.storage.from_(BUCKET).get_public_url(path)
    return public_url


def save_post(article: dict, captions: dict, image_urls: dict, slides: list = None,
              attempts: list = None) -> str:
    """Insère un post dans la table posts. Retourne l'id.
    `slides`   : URLs des slides du carrousel (étude data) — optionnel.
    `attempts` : essais ratés à la barrière QA [{image, raison, score, type}] — optionnel."""
    sb = get_client()
    post_id = str(uuid.uuid4())

    row = {
        "id": post_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "article_url": article.get("url", ""),
        "article_title": article.get("title", ""),
        "source": article.get("source", ""),
        "category": article.get("category", ""),
        "relevance_score": article.get("score", 0),
        "verified": article.get("verified", False),
        "key_data": article.get("key_points", []),
        "chart_type": article.get("chart_type", "infographic"),
        "slides": slides or None,
        "attempts": attempts or None,
        "caption_twitter": captions.get("twitter", ""),
        "caption_instagram": captions.get("instagram", ""),
        "caption_linkedin": captions.get("linkedin", ""),
        "image_twitter": image_urls.get("twitter", ""),
        "image_instagram": image_urls.get("instagram", ""),
        "image_linkedin": image_urls.get("linkedin", ""),
        # needs_transcript -> flag « transcription manquante » (vidéo sans script)
        "status": "needs_transcript" if article.get("needs_transcript") else "pending",
        # Dédup intelligent
        "topic_key": article.get("topic_key", ""),
        "data_sig": article.get("data_sig", ""),
        "is_update": bool(article.get("is_update", False)),
        "update_of": article.get("update_of") or None,
        # Transcription vidéo manuelle
        "needs_transcript": bool(article.get("needs_transcript", False)),
        "pending_transcript": None,
    }

    try:
        sb.table("posts").insert(row).execute()
    except Exception as e:
        # Schéma pas encore migré (colonnes absentes) -> insert sans ces champs
        if any(col in str(e) for col in _OPTIONAL_COLS):
            for col in _OPTIONAL_COLS:
                row.pop(col, None)
            if row.get("status") == "needs_transcript":
                row["status"] = "pending"
            sb.table("posts").insert(row).execute()
            print("[STORAGE] (colonnes optionnelles absentes — insert en mode compatible)")
        else:
            raise
    print(f"[STORAGE] Post sauvegardé : {post_id}")
    return post_id


def get_recent_history(days: int = 14) -> list[dict]:
    """Historique récent pour le dédup : empreintes des posts des N derniers jours.
    Résilient : si les colonnes dédup n'existent pas, retombe sur les colonnes de base."""
    sb = get_client()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    full = "id,article_url,article_title,category,topic_key,data_sig,created_at"
    try:
        res = sb.table("posts").select(full).gte("created_at", since).execute()
        return res.data or []
    except Exception as e:
        if any(col in str(e) for col in _DEDUP_COLS):
            res = sb.table("posts").select(
                "id,article_url,article_title,category,created_at"
            ).gte("created_at", since).execute()
            # Pas d'empreintes stockées : on les reconstruit depuis le titre au vol
            import dedup
            rows = res.data or []
            for r in rows:
                r["topic_key"] = dedup.topic_key({"title_fr": r.get("article_title", "")})
                r["data_sig"] = ""
            return rows
        raise


def get_pending_posts() -> list[dict]:
    """Retourne les posts en attente d'approbation."""
    sb = get_client()
    result = sb.table("posts").select("*").eq("status", "pending").order("relevance_score", desc=True).execute()
    return result.data


def approve_post(post_id: str, network: str) -> None:
    """Marque un post comme approuvé pour un réseau."""
    sb = get_client()
    sb.table("posts").update({
        "status": "approved",
        "network": network,
    }).eq("id", post_id).execute()


def mark_posted(post_id: str) -> None:
    """Marque un post comme publié."""
    sb = get_client()
    sb.table("posts").update({
        "status": "posted",
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", post_id).execute()


# ── Retraitement après collage manuel d'une transcription ─────────────────────
def get_posts_to_regenerate() -> list[dict]:
    """Posts dont l'utilisateur a collé une transcription et cliqué « Générer »
    (status='to_regenerate' avec pending_transcript non vide)."""
    sb = get_client()
    res = (sb.table("posts").select("*")
           .eq("status", "to_regenerate")
           .order("created_at", desc=True).execute())
    return [p for p in (res.data or []) if (p.get("pending_transcript") or "").strip()]


def update_post_content(post_id: str, article: dict, captions: dict,
                        image_urls: dict, status: str = "pending") -> None:
    """Met à jour un post existant après regénération (transcription collée)."""
    sb = get_client()
    sb.table("posts").update({
        "article_title": article.get("title", ""),
        "category": article.get("category", ""),
        "relevance_score": article.get("score", 0),
        "key_data": article.get("key_points", []),
        "chart_type": article.get("chart_type", "infographic"),
        "caption_twitter": captions.get("twitter", ""),
        "caption_instagram": captions.get("instagram", ""),
        "caption_linkedin": captions.get("linkedin", ""),
        "image_twitter": image_urls.get("twitter", ""),
        "image_instagram": image_urls.get("instagram", ""),
        "image_linkedin": image_urls.get("linkedin", ""),
        "status": status,
        "needs_transcript": False,
        "pending_transcript": None,
    }).eq("id", post_id).execute()
