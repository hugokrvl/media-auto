"""
Point d'entrée du pipeline nocturne.
Exécuté par GitHub Actions à 1h du matin.
"""

import re
import unicodedata
from scraper import fetch_articles
from analyzer import analyze_articles
from dataviz import generate_image
from generator import generate_captions
from storage import upload_image, save_post
from notifier import notify_pipeline_done


def _slugify(text: str) -> str:
    """Transforme un titre en nom de fichier ASCII sûr pour Supabase Storage."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return text[:40].lower()


def run():
    errors = 0
    saved = 0

    print("=== MediaAuto Pipeline démarré ===")

    # 1. Scraping
    articles = fetch_articles(hours_back=24)
    if not articles:
        notify_pipeline_done(0)
        print("[MAIN] Aucun article trouvé.")
        return

    # 2. Analyse + tri
    selected = analyze_articles(articles)
    if not selected:
        notify_pipeline_done(0)
        print("[MAIN] Aucun article retenu après analyse.")
        return

    # 3. Génération par article (max 7 posts/jour)
    for i, article in enumerate(selected[:7]):
        try:
            title_slug = _slugify(article["title"]) or f"post_{i}"

            # Dataviz pour chaque réseau
            image_urls = {}
            for network in ["instagram", "twitter", "linkedin"]:
                img_bytes = generate_image(article, network)
                filename = f"{title_slug}_{network}.png"
                url = upload_image(img_bytes, filename)
                image_urls[network] = url

            # Captions
            captions = generate_captions(article)

            # Sauvegarde
            save_post(article, captions, image_urls)
            saved += 1
            print(f"[MAIN] ✓ Post créé : {article['title'][:60]}")

        except Exception as e:
            errors += 1
            print(f"[MAIN] ✗ Erreur sur '{article['title'][:50]}': {e}")

    # 4. Notification
    notify_pipeline_done(saved, errors)
    print(f"=== Pipeline terminé : {saved} posts / {errors} erreurs ===")


if __name__ == "__main__":
    run()
