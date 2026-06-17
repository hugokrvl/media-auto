"""
Publication sur Instagram via Meta Graph API.
Nécessite un compte Business/Creator et une Page Facebook liée.
"""

import os
import requests


GRAPH_URL = "https://graph.facebook.com/v19.0"


def post_to_instagram(caption: str, image_url: str) -> str:
    """Publie un post Instagram. Retourne l'URL du post."""
    token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
    ig_id = os.environ["INSTAGRAM_BUSINESS_ID"]

    # Étape 1 : création du container média
    container_resp = requests.post(
        f"{GRAPH_URL}/{ig_id}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": token,
        },
        timeout=30,
    )
    container_resp.raise_for_status()
    container_id = container_resp.json()["id"]

    # Étape 2 : publication
    publish_resp = requests.post(
        f"{GRAPH_URL}/{ig_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": token,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    post_id = publish_resp.json()["id"]
    return f"https://www.instagram.com/p/{post_id}/"
