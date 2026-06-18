"""
Point d'entrée du pipeline nocturne.
Exécuté par GitHub Actions à 1h du matin.
"""

import re
import unicodedata
import dedup
from scraper import fetch_articles
from analyzer import analyze_articles
from dataviz import generate_image
from generator import generate_captions
from storage import upload_image, save_post, get_recent_history
from notifier import notify_pipeline_done
import image_fetch
import breaking as breaking_renderer


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

    # 2bis. Dédup intelligent — charge l'historique récent (résilient si indispo)
    try:
        history = get_recent_history(days=14)
        print(f"[MAIN] Historique dédup : {len(history)} posts des 14 derniers jours")
    except Exception as e:
        history = []
        print(f"[MAIN] Historique dédup indisponible ({e}) — tout en 'new'")

    # 3. Génération par article (max 7 posts/jour)
    # Prioriser les articles avec graphique (kpi/bar/donut/courbe) sur les infographics
    _CHART_PRIORITY = {"kpi": 0, "bar": 1, "donut": 2, "courbe": 3, "line": 3, "infographic": 10}
    selected.sort(key=lambda a: _CHART_PRIORITY.get(a.get("chart_type", "infographic"), 10))
    MAX_INFOGRAPHIC = 2  # au plus 2 posts "liste de points" sur 7

    dups = updates = infographic_count = 0
    for i, article in enumerate(selected):
        if saved >= 7:
            break

        # Verdict dédup (compare à l'historique + aux posts déjà retenus cette nuit)
        dedup.annotate(article)
        status, matched = dedup.classify(article, history)
        if status == "duplicate":
            dups += 1
            print(f"[MAIN] ⊘ Doublon ignoré : {article['title'][:55]}")
            continue

        # Cap infographic : si déjà 2 listes de points ce soir, passer au suivant
        if article.get("chart_type", "infographic") == "infographic":
            if infographic_count >= MAX_INFOGRAPHIC:
                print(f"[MAIN] ⊘ Trop d'infographics ({MAX_INFOGRAPHIC} max), ignoré : {article['title'][:50]}")
                continue
            infographic_count += 1
        if status == "update":
            updates += 1
            article["is_update"] = True
            article["update_of"] = (matched or {}).get("id")
            sub = article.get("subtitle_fr", "")
            article["subtitle_fr"] = ("MISE À JOUR · " + sub)[:50] if sub else "MISE À JOUR"
            print(f"[MAIN] ↻ Mise à jour détectée : {article['title'][:50]}")

        # Vidéo dont la transcription a échoué -> post créé quand même (depuis la
        # description) mais FLAGUÉ : l'utilisateur pourra coller le script sur le site.
        article["needs_transcript"] = bool(
            article.get("is_video") and not article.get("transcript"))

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
            # Empile dans l'historique du run -> les articles suivants se dédupliquent aussi
            history.append(dedup.as_history_row(article))
            tag = " [MAJ]" if article.get("is_update") else ""
            print(f"[MAIN] ✓ Post créé{tag} : {article['title'][:60]}")

        except Exception as e:
            errors += 1
            print(f"[MAIN] ✗ Erreur sur '{article['title'][:50]}': {e}")

    print(f"[MAIN] Dédup : {dups} doublon(s) ignoré(s), {updates} mise(s) à jour")

    # 4. Posts "Breaking News" (photo libre de droits + overlay titre)
    # Déclenchés pour les articles score >= 9 + verified, max 2/nuit
    _breaking_candidates = [
        a for a in selected
        if a.get("score", 0) >= 8 and a.get("verified") and not a.get("_breaking_done")
    ][:2]

    breaking_saved = 0
    if _breaking_candidates and (image_fetch.UNSPLASH_ACCESS_KEY or image_fetch.PEXELS_API_KEY):
        print(f"[MAIN] Breaking news : {len(_breaking_candidates)} candidat(s)")
        for article in _breaking_candidates:
            try:
                photo_url = image_fetch.fetch_photo_url(article)
                if not photo_url:
                    print(f"[MAIN] Breaking : pas de photo pour «{article['title'][:45]}»")
                    continue
                photo_bytes = image_fetch.download_image(photo_url)
                if not photo_bytes:
                    continue
                img_bytes = breaking_renderer.make_breaking_image(article, photo_bytes)
                title_slug = _slugify(article.get("title_fr") or article["title"]) or "breaking"
                image_urls = {}
                for network in ["instagram", "twitter", "linkedin"]:
                    url = upload_image(img_bytes, f"{title_slug}_breaking_{network}.png")
                    image_urls[network] = url
                captions = generate_captions(article)
                # Marque le type comme breaking pour le site
                article_br = {**article, "chart_type": "breaking"}
                save_post(article_br, captions, image_urls)
                breaking_saved += 1
                print(f"[MAIN] ✓ Breaking créé : {article['title'][:60]}")
            except Exception as e:
                errors += 1
                print(f"[MAIN] ✗ Breaking KO «{article['title'][:45]}»: {e}")
    elif _breaking_candidates and not (image_fetch.UNSPLASH_ACCESS_KEY or image_fetch.PEXELS_API_KEY):
        print("[MAIN] Breaking news : UNSPLASH_ACCESS_KEY et PEXELS_API_KEY absents, posts photo ignorés")

    total_saved = saved + breaking_saved

    # 5. Notification
    notify_pipeline_done(total_saved, errors)
    print(f"=== Pipeline terminé : {total_saved} posts ({saved} dataviz + {breaking_saved} breaking) / {errors} erreurs ===")


if __name__ == "__main__":
    run()
