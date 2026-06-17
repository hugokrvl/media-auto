"""
Publication sur LinkedIn via API v2.
"""

import os
import requests


def post_to_linkedin(caption: str, image_url: str) -> str:
    """Publie un post LinkedIn avec image. Retourne l'URL du post."""
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    person_id = os.environ["LINKEDIN_PERSON_ID"]  # format : urn:li:person:XXXXXXX
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # 1. Enregistrement de l'image
    register_resp = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_id,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ],
            }
        },
        timeout=30,
    )
    register_resp.raise_for_status()
    data = register_resp.json()
    upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset = data["value"]["asset"]

    # 2. Upload de l'image
    img_data = requests.get(image_url, timeout=15).content
    requests.put(upload_url, data=img_data,
                 headers={"Authorization": f"Bearer {token}"}, timeout=30).raise_for_status()

    # 3. Création du post
    post_resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json={
            "author": person_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": asset}],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        },
        timeout=30,
    )
    post_resp.raise_for_status()
    post_id = post_resp.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{post_id}/"
