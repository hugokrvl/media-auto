"""
Test d'INTÉGRATION offline du pipeline nocturne (main.run()).

On STUBE uniquement les frontières réseau / IA / Supabase (scraper, analyzer, storage,
generator, notifier) ; tout le reste tourne POUR DE VRAI : fusion open data + articles,
filtre _has_data, dédup intelligent, et rendu carrousel (matplotlib). Aucune clé ni réseau,
aucune dépendance tierce (groq/supabase/feedparser non requis).

Vérifie : open data EN TÊTE, articles ensuite, article SANS données écarté, chaque post =
un carrousel (≥ 2 slides), vignette = couverture.

    PYTHONIOENCODING=utf-8 python _test_pipeline.py
"""

import sys
import types

saved = []


def _article(**kw):
    base = {
        "title": "Sujet de test", "title_fr": "Titre FR de test",
        "subtitle_fr": "Contexte · 2026", "source": "Test", "category": "tech",
        "score": 8, "verified": True, "chart_type": "kpi",
        "chart_data": [{"label": "Valeur", "value": "42", "unit": "%"}],
        "key_points": ["Point clé chiffré : 42 %"], "insight": "Un verdict de test.",
        "url": "https://example.org/a",
    }
    base.update(kw)
    return base


study = _article(title="PIB Europe", title_fr="Les plus grandes économies d'Europe",
                 source="Eurostat", category="finance", chart_type="bar",
                 chart_data=[{"label": "Allemagne", "value": 4200},
                             {"label": "France", "value": 2900},
                             {"label": "Italie", "value": 2000}],
                 key_points=["1. Allemagne — 4 200 Md€"], is_opendata=True,
                 url="https://data.worldbank.org/x")
art_data = _article(title="Nvidia 4000 Md", title_fr="Nvidia franchit 4 000 Md$",
                    url="https://example.org/nvidia")
art_nodata = _article(title="Édito sans chiffres", title_fr="Une tribune qualitative",
                      chart_type="infographic", chart_data=[], url="https://example.org/edito")


def _save(article, captions, image_urls, slides=None):
    saved.append({
        "titre": article.get("title_fr") or article.get("title"),
        "type": article.get("chart_type"),
        "slides": len(slides or []),
        "opendata": bool(article.get("is_opendata")),
        "cover_ok": image_urls.get("instagram") == (slides or [None])[0],
    })
    return "fake-id"


def _stub(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m


# Frontières stubées AVANT l'import de main (évite groq/supabase/feedparser).
_stub("scraper", fetch_articles=lambda hours_back=24: [{"raw": 1}])
_stub("analyzer", analyze_articles=lambda arts: [art_data, art_nodata])
_stub("storage", upload_image=lambda png, name: f"https://cdn/{name}",
      save_post=_save, get_recent_history=lambda days=14: [])
_stub("generator", generate_captions=lambda a: {"twitter": "t", "instagram": "i", "linkedin": "l"})
_stub("notifier", notify_pipeline_done=lambda *a, **k: None)

import main  # noqa: E402  (carousel, dataviz, opendata, dedup restent RÉELS)

main.opendata.fetch_studies = lambda max_n=2: [study]


def run():
    main.run()
    assert saved, "aucun post sauvegardé"
    assert saved[0]["opendata"], f"l'open data doit être EN TÊTE : {saved}"
    assert any(s["type"] == "kpi" for s in saved), "l'article data n'est pas passé"
    assert all(s["slides"] >= 2 for s in saved), f"carrousels non générés : {saved}"
    assert all(s["cover_ok"] for s in saved), "la vignette n'est pas la couverture (slide 0)"
    assert not any("qualitative" in s["titre"] for s in saved), \
        "l'article SANS données aurait dû être écarté"
    print(f"OK — {len(saved)} post(s) carrousel (1 écarté, sans données) :")
    for s in saved:
        print(f"   • {s['titre'][:42]:42} | {s['type']:5} | {s['slides']} slides | open_data={s['opendata']}")


if __name__ == "__main__":
    run()
