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
import carousel
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


def _materialize_post(pd: dict, base: dict, existing_id: str = None) -> None:
    """Rend UN post (décryptage ou brève) → upload slides + captions → Supabase.
    existing_id : met à jour la ligne d'origine (1er post) ; sinon insère un NOUVEAU post."""
    import decrypt_light
    article = {
        "title": pd.get("title_fr") or "Post",
        "title_fr": pd.get("title_fr") or "Post",
        "url": base.get("url", ""),
        "source": pd.get("source") or base.get("source", ""),
        "category": pd.get("category") or base.get("category", "general"),
        "score": 8, "verified": True,
        "chart_type": pd.get("chart_type", "decryptage"),
        "insight": pd.get("insight", ""),
        "key_points": pd.get("key_points", []),
        "decrypt_data": pd.get("decrypt_data"),
    }
    slug = _slugify(article["title"])
    if pd.get("format") == "breve":
        imgs = decrypt_light.render_breve(pd["breve_data"])
        kind = "breve"
    else:
        imgs = carousel.generate_decryptage(article)
        kind = "decr"
    slide_urls = [storage.upload_image(png, f"{slug}_{kind}{n + 1}.png")
                  for n, png in enumerate(imgs)]
    cover = slide_urls[0] if slide_urls else None
    image_urls = {net: cover for net in ("instagram", "twitter", "linkedin")}
    captions = generator.generate_captions(article)
    if existing_id:
        storage.update_post_content(existing_id, article, captions, image_urls,
                                    status="pending", slides=slide_urls)
    else:
        storage.save_post(article, captions, image_urls, slides=slide_urls)
    print(f"[GENERATE] ✓ {pd.get('format')} {len(slide_urls)} slide(s) : {article['title'][:50]}")


def run_generate():
    """Crée des posts depuis un texte collé (status='to_generate'). DÉCOUPE PAR SUJET :
    1 sujet = 1 post (décryptage clair si assez de matière, sinon brève photo+titre).
    Digest token-safe (8b) → découpe/structuration (70b) → carrousels/brèves → 'pending'."""
    posts = storage.get_posts_to_generate()
    if not posts:
        print("[GENERATE] Aucun texte collé à transformer.")
        return 0
    print(f"[GENERATE] {len(posts)} texte(s) collé(s) à transformer")
    done = errors = 0
    for post in posts:
        rid = post.get("id", "")
        try:
            base = {
                "title": post.get("article_title") or "Décryptage",
                "url": post.get("article_url", ""),
                "source": post.get("source") or "Texte collé",
                "category": post.get("category") or "general",
                "pending_transcript": post.get("pending_transcript", ""),
            }
            subposts = analyzer.split_into_posts(base)
            if not subposts:
                errors += 1
                print(f"[GENERATE] ⊘ Rien d'exploitable : {rid}")
                continue
            for i, pd in enumerate(subposts):
                try:
                    _materialize_post(pd, base, existing_id=(rid if i == 0 else None))
                    done += 1
                except Exception as e:
                    errors += 1
                    print(f"[GENERATE] ✗ rendu post {i} ({rid}): {type(e).__name__}: {e}")
        except Exception as e:
            errors += 1
            print(f"[GENERATE] ✗ {type(e).__name__} sur '{rid}': {e}")
    print(f"=== Génération terminée : {done} post(s) créé(s) / {errors} erreur(s) ===")
    if done:
        try:
            from notifier import notify
            notify("Posts prêts ✓", f"{done} post(s) généré(s) depuis ton texte (1 sujet = 1 post), à valider.")
        except Exception:
            pass
    return done


if __name__ == "__main__":
    run()
    run_generate()
