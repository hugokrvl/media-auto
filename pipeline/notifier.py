"""
Envoie une notification push via ntfy.sh.
"""

import os
import requests


def notify(title: str, message: str, priority: str = "default") -> None:
    """Envoie une notification ntfy."""
    topic = os.environ["NTFY_TOPIC"]
    url = f"https://ntfy.sh/{topic}"

    try:
        requests.post(url, data=message.encode("utf-8"), headers={
            "Title": title,
            "Priority": priority,
            "Tags": "newspaper,robot",
        }, timeout=10)
        print(f"[NTFY] Notif envoyée : {title}")
    except Exception as e:
        print(f"[NTFY] Erreur : {e}")


def notify_pipeline_done(n_posts: int, errors: int = 0) -> None:
    title = f"MediaAuto — {n_posts} posts générés ✓"
    body = f"{n_posts} posts prêts à valider."
    if errors:
        body += f" ({errors} erreurs)"
    body += "\nOuvre le site planning pour approuver."
    notify(title, body, priority="high" if errors == 0 else "urgent")
