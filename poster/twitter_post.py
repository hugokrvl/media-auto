"""
Publication sur X (Twitter) via tweepy v2.
Déclenché après approbation humaine depuis le site planning.
"""

import os
import requests
import tweepy


def post_to_twitter(caption: str, image_url: str) -> str:
    """Publie un tweet avec image. Retourne l'URL du tweet."""
    client = tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
    )

    # Upload image via API v1.1 (seul moyen pour les médias)
    auth = tweepy.OAuth1UserHandler(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"],
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_SECRET"],
    )
    api_v1 = tweepy.API(auth)

    img_data = requests.get(image_url, timeout=15).content
    media = api_v1.media_upload(filename="post.png", file=__import__("io").BytesIO(img_data))
    media_id = media.media_id

    response = client.create_tweet(text=caption, media_ids=[media_id])
    tweet_id = response.data["id"]
    return f"https://x.com/i/web/status/{tweet_id}"
