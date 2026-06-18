"""
Retraitement des transcriptions vidéo collées manuellement sur le site.

Déclenché par .github/workflows/reprocess.yml (toutes les ~15 min + manuel).
Flux :
  1. L'utilisateur colle un script YouTube sur le site et clique « Générer »
     -> le post passe en status='to_regenerate' avec pending_transcript rempli.
  2. Ce script récupère ces posts, digère la transcription (modèle pas cher),
     enrichit (70b), régénère les images + captions, et repasse le post en 'pending'
     (prêt à approuver), needs_transcript=false.

Idempotent : s'il n'y a rien à retraiter, il sort proprement (run quasi gratuit).
"""

import re
import unicodedata

import analyzer
import dataviz
import generator
import storage


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return text[:40].lower() or "post"


def run():
    posts = storage.get_posts_to_regenerate()
    if not posts:
        print("[REPROCESS] Rien à retraiter.")
        return

    print(f"[REPROCESS] {len(posts)} transcription(s) à traiter")
    done = errors = 0
    for post in posts:
        title = post.get("article_title", "")
        try:
            article = {
                "title": title,
                "url": post.get("article_url", ""),
                "source": post.get("source", ""),
                "category": post.get("category", "general"),
                "score": post.get("relevance_score", 7),
                "transcript": post.get("pending_transcript", ""),
                "is_video": True,
            }
            # Digest (pas cher) + enrichissement (70b)
            analyzer.enrich_with_transcript(article)

            # Régénération des 3 images
            slug = _slugify(title)
            image_urls = {}
            for network in ["instagram", "twitter", "linkedin"]:
                img = dataviz.generate_image(article, network)
                image_urls[network] = storage.upload_image(img, f"{slug}_{network}.png")

            # Captions
            captions = generator.generate_captions(article)

            # Mise à jour du post existant -> repasse en 'pending' (à approuver)
            storage.update_post_content(post["id"], article, captions, image_urls, status="pending")
            done += 1
            print(f"[REPROCESS] ✓ Régénéré : {title[:60]}")
        except Exception as e:
            errors += 1
            print(f"[REPROCESS] ✗ Erreur sur '{title[:50]}': {type(e).__name__}: {e}")

    print(f"=== Retraitement terminé : {done} régénéré(s) / {errors} erreur(s) ===")

    # Notification douce si au moins un post régénéré
    if done:
        try:
            from notifier import notify
            notify("Transcription traitée ✓",
                   f"{done} post(s) régénéré(s) depuis transcription, prêt(s) à valider.")
        except Exception:
            pass


if __name__ == "__main__":
    run()
