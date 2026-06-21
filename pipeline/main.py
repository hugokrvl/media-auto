"""
Point d'entrée du pipeline nocturne (1h du matin).

Flux 100 % DATAVIZ : chaque post est une PETITE ÉTUDE en carrousel
(couverture → graphique → à retenir → verdict). L'actualité « chaude » est
gérée séparément, en quasi temps réel, par le moteur breaking (breaking_scan.py).
"""

import os
import re
import unicodedata
import dedup
import carousel
import opendata
from scraper import fetch_articles
from analyzer import analyze_articles
from generator import generate_captions
from storage import upload_image, save_post, get_recent_history
from notifier import notify_pipeline_done

# Types qui portent de vraies données chiffrées (le reste est écarté du flux data).
DATA_TYPES = {"kpi", "bar", "donut", "courbe", "line"}
MAX_POSTS = int(os.environ.get("NIGHTLY_MAX_POSTS", "7"))
OPENDATA_MAX = int(os.environ.get("OPENDATA_MAX", "2"))   # études open data/nuit (en + des articles)


def _slugify(text: str) -> str:
    """Transforme un titre en nom de fichier ASCII sûr pour Supabase Storage."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return text[:40].lower()


def _has_data(article: dict) -> bool:
    """True si l'article porte de vraies données chiffrées exploitables."""
    ct = article.get("chart_type", "infographic")
    return ct in DATA_TYPES and any(
        isinstance(d, dict) for d in (article.get("chart_data") or []))


def run():
    errors = 0
    saved = 0

    print("=== MediaAuto Pipeline (études data) démarré ===")

    # 1. Scraping articles (RSS / YouTube / email)
    articles = fetch_articles(hours_back=24)

    # 2. Analyse + tri (triage 8b → enrichissement 70b ; n'enrichit que le chiffrable)
    selected = analyze_articles(articles) if articles else []

    # 2bis. Études OPEN DATA (Banque mondiale…) — en COMPLÉMENT des articles : chiffres
    # officiels déjà prêts (zéro token IA). Le dédup en aval évite de reposter l'inchangé.
    studies = []
    try:
        studies = opendata.fetch_studies(max_n=OPENDATA_MAX)
        if studies:
            print(f"[MAIN] {len(studies)} étude(s) open data récupérée(s)")
    except Exception as e:
        print(f"[MAIN] open data indisponible : {e}")

    if not selected and not studies:
        notify_pipeline_done(0)
        print("[MAIN] Rien à publier.")
        return

    # 2ter. Dédup intelligent — charge l'historique récent (résilient si indispo)
    try:
        history = get_recent_history(days=14)
        print(f"[MAIN] Historique dédup : {len(history)} posts des 14 derniers jours")
    except Exception as e:
        history = []
        print(f"[MAIN] Historique dédup indisponible ({e}) — tout en 'new'")

    # 3. Un CARROUSEL « étude data » par article retenu (max MAX_POSTS).
    # Priorité aux graphiques les plus parlants ; les articles sans données sont écartés.
    _CHART_PRIORITY = {"kpi": 0, "bar": 1, "donut": 2, "courbe": 3, "line": 3, "infographic": 10}
    selected.sort(key=lambda a: _CHART_PRIORITY.get(a.get("chart_type", "infographic"), 10))
    # Études open data en TÊTE (données officielles = les plus fiables), puis les articles.
    selected = studies + selected

    dups = updates = skipped = 0
    for i, article in enumerate(selected):
        if saved >= MAX_POSTS:
            break

        # Flux DATA : on écarte tout article sans données chiffrables (→ moteur breaking).
        if not _has_data(article):
            skipped += 1
            print(f"[MAIN] ⊘ Sans données chiffrées, écarté : {article['title'][:55]}")
            continue

        # Verdict dédup (historique + posts déjà retenus cette nuit)
        dedup.annotate(article)
        status, matched = dedup.classify(article, history)
        if status == "duplicate":
            dups += 1
            print(f"[MAIN] ⊘ Doublon ignoré : {article['title'][:55]}")
            continue
        if status == "update":
            updates += 1
            article["is_update"] = True
            article["update_of"] = (matched or {}).get("id")
            sub = article.get("subtitle_fr", "")
            article["subtitle_fr"] = ("MISE À JOUR · " + sub)[:50] if sub else "MISE À JOUR"
            print(f"[MAIN] ↻ Mise à jour détectée : {article['title'][:50]}")

        # Vidéo sans transcription auto -> post créé quand même, mais flagué (collage site)
        article["needs_transcript"] = bool(
            article.get("is_video") and not article.get("transcript"))

        try:
            title_slug = _slugify(article["title"]) or f"post_{i}"

            # Carrousel : couverture → graphique → à retenir → verdict.
            slides = carousel.generate_carousel(article)
            slide_urls = [upload_image(png, f"{title_slug}_slide{n + 1}.png")
                          for n, png in enumerate(slides)]
            # Image principale (vignette + repli réseaux) = la couverture du carrousel.
            cover = slide_urls[0]
            image_urls = {net: cover for net in ("instagram", "twitter", "linkedin")}

            captions = generate_captions(article)
            save_post(article, captions, image_urls, slides=slide_urls)
            saved += 1
            history.append(dedup.as_history_row(article))
            tag = " [MAJ]" if article.get("is_update") else ""
            print(f"[MAIN] ✓ Carrousel {len(slide_urls)} slides{tag} : {article['title'][:55]}")

        except Exception as e:
            errors += 1
            print(f"[MAIN] ✗ Erreur sur '{article['title'][:50]}': {e}")

    print(f"[MAIN] Dédup : {dups} doublon(s), {updates} MAJ, {skipped} sans-données écarté(s)")

    # 4. Notification
    notify_pipeline_done(saved, errors)
    print(f"=== Pipeline terminé : {saved} carrousels data / {errors} erreurs ===")


if __name__ == "__main__":
    run()
