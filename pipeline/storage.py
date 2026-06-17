"""
Sauvegarde les posts et images dans Supabase.
Table : posts | Bucket : post-images
"""

import os
import uuid
from datetime import datetime, timezone
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BUCKET = "post-images"

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


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


def save_post(article: dict, captions: dict, image_urls: dict) -> str:
    """Insère un post dans la table posts. Retourne l'id."""
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
        "caption_twitter": captions.get("twitter", ""),
        "caption_instagram": captions.get("instagram", ""),
        "caption_linkedin": captions.get("linkedin", ""),
        "image_twitter": image_urls.get("twitter", ""),
        "image_instagram": image_urls.get("instagram", ""),
        "image_linkedin": image_urls.get("linkedin", ""),
        "status": "pending",
    }

    sb.table("posts").insert(row).execute()
    print(f"[STORAGE] Post sauvegardé : {post_id}")
    return post_id


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
