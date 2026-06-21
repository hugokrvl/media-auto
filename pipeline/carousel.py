"""
Carrousels HK Média — format « étude data » multi-slides du pipeline nocturne.

Chaque post de nuit devient une petite ÉTUDE visuelle de 3-4 slides 1080x1080 :
  1. Couverture  : accroche éditoriale (titre serif + chiffre héros + catégorie)
  2. Graphique   : la dataviz principale (kpi/bar/donut/courbe) — réutilise dataviz.py
  3. À retenir   : 2-4 points clés chiffrés (si disponibles)
  4. Le verdict  : la conclusion en une phrase (champ `insight`) + source + CTA

Toute la charte vient de dataviz.py (cadre, tag, monogramme, footer, polices) → look
100 % cohérent avec les infographies simples. Chaque slide est protégé : si l'un échoue,
generate_carousel renvoie au moins la dataviz principale (jamais de post cassé).
"""

import textwrap

import brand as B
import dataviz as D

SIZE = (1080, 1080)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _base_fig(category):
    """Fig + chrome commun (cadre, tag catégorie, monogramme). Renvoie (fig, ax)."""
    fig = D._new_fig(SIZE)
    fig._hk_fonts = B.fonts()
    ax = D._draw_frame(fig)
    D._draw_tag(ax, fig, category)
    D._draw_monogram(fig)
    return fig, ax


def _num(d):
    try:
        return float(str(d.get("value", 0)).replace(",", ".").replace(" ", ""))
    except Exception:
        return 0.0


def _hero_stat(article):
    """(valeur formatée, libellé) du chiffre phare pour la couverture, ou None."""
    data = [d for d in (article.get("chart_data") or []) if isinstance(d, dict)]
    if not data:
        return None
    ct = article.get("chart_type", "")
    best = max(data, key=_num) if ct in ("bar", "donut", "courbe") else data[0]
    val = B.fr(best.get("value", 0))
    unit = str(best.get("unit", "")).strip()
    if unit and not any(m in val.lower() for m in ("md", " m", "k")):
        val = f"{val} {unit}"
    return val, str(best.get("label", ""))[:34]


# ── Slides ───────────────────────────────────────────────────────────────────
def _slide_cover(article):
    """Slide 1 — couverture éditoriale : eyebrow + titre serif + chiffre héros + hint."""
    fig, ax = _base_fig(article.get("category", ""))
    F = fig._hk_fonts
    figH = fig.get_size_inches()[1]

    ax.text(0.075, 0.80, "ÉTUDE DATA · HK MÉDIA", ha="left", va="top", color=B.MUSTARD_DK,
            fontproperties=F["body_sb"], fontsize=14, zorder=5)

    title = (article.get("title_fr") or article.get("title", "")).strip()
    lines = textwrap.wrap(title, 24)[:4]
    t_fs = 47 if len(lines) <= 2 else 39
    y = 0.745
    for ln in lines:
        ax.text(0.075, y, ln, ha="left", va="top", color=B.INK,
                fontproperties=F["title"], fontsize=t_fs, zorder=5)
        y -= (t_fs + 9) / (figH * 72)

    ax.plot([0.075, 0.30], [y - 0.004, y - 0.004], color=B.MUSTARD, linewidth=3, zorder=5)
    y -= 0.05

    hero = _hero_stat(article)
    if hero:
        val, lab = hero
        val_fs = D._fit_fontsize(fig, val, F["num"], 0.70, 128, 44)
        ax.text(0.075, y, val, ha="left", va="top", color=B.MUSTARD_DK,
                fontproperties=F["num"], fontsize=val_fs, zorder=5)
        y -= (val_fs + 4) / (figH * 72)
        if lab:
            ax.text(0.078, y, lab.upper(), ha="left", va="top", color=B.INK_SOFT,
                    fontproperties=F["body_sb"], fontsize=15, zorder=5)

    D._draw_footer(fig, ax, article.get("source", ""))
    # « GLISSEZ ▸ » : triangle dessiné (la flèche Unicode n'existe pas dans Barlow)
    ax.text(0.905, 0.137, "GLISSEZ", ha="right", va="center", color=B.MUSTARD_DK,
            fontproperties=F["body_sb"], fontsize=13, zorder=5)
    ax.plot([0.918], [0.136], marker=">", markersize=9, color=B.MUSTARD_DK,
            markeredgecolor=B.MUSTARD_DK, zorder=5)
    return D._finish(fig)


def _slide_chart(article):
    """Slide 2 — la dataviz principale (réutilise tel quel le moteur dataviz)."""
    return D.generate_image(article, "instagram")


def _slide_points(article):
    """Slide 3 — « À retenir » : 2-4 points clés. None si aucun point exploitable."""
    pts = [p for p in (article.get("key_points") or []) if str(p).strip()][:4]
    if not pts:
        return None
    fig, ax = _base_fig(article.get("category", ""))
    top = D._draw_header(fig, ax, "À retenir", article.get("subtitle_fr", ""))
    D._make_infographic(fig, ax, {"key_points": pts,
                                  "subtitle_fr": article.get("subtitle_fr", "")}, top)
    D._draw_footer(fig, ax, article.get("source", ""))
    return D._finish(fig)


def _slide_takeaway(article):
    """Slide 4 — « Le verdict » : la conclusion (insight) en une phrase + CTA."""
    fig, ax = _base_fig(article.get("category", ""))
    F = fig._hk_fonts
    figH = fig.get_size_inches()[1]

    ax.text(0.075, 0.80, "LE VERDICT", ha="left", va="top", color=B.MUSTARD_DK,
            fontproperties=F["body_sb"], fontsize=15, zorder=5)

    insight = (article.get("insight") or article.get("subtitle_fr")
               or article.get("title_fr") or article.get("title", "")).strip()
    lines = textwrap.wrap(insight, 26)[:6]
    fs = 35 if len(lines) <= 4 else 28
    y = 0.70
    for ln in lines:
        ax.text(0.075, y, ln, ha="left", va="top", color=B.INK,
                fontproperties=F["title"], fontsize=fs, zorder=5)
        y -= (fs + 11) / (figH * 72)

    ax.plot([0.075, 0.30], [y - 0.004, y - 0.004], color=B.MUSTARD, linewidth=3, zorder=5)

    D._draw_footer(fig, ax, article.get("source", ""))
    ax.text(0.075, 0.135, "SUIVEZ @HK.MÉDIA POUR VOS DÉCRYPTAGES DATA", ha="left",
            va="center", color=B.MUSTARD_DK, fontproperties=F["body_sb"], fontsize=12.5, zorder=5)
    return D._finish(fig)


# ── Point d'entrée ───────────────────────────────────────────────────────────
def generate_carousel(article: dict) -> list[bytes]:
    """Renvoie la liste des PNG (slides) du carrousel. Chaque slide est protégé ;
    en dernier recours on renvoie au moins la dataviz principale."""
    slides = []
    for fn in (_slide_cover, _slide_chart, _slide_points, _slide_takeaway):
        try:
            png = fn(article)
            if png:
                slides.append(png)
        except Exception as e:
            print(f"[CAROUSEL] slide {fn.__name__} KO ({type(e).__name__}: {e})")
    if not slides:
        slides = [D.generate_image(article, "instagram")]
    return slides


if __name__ == "__main__":
    sample = {
        "title_fr": "OpenAI lève 40 milliards et atteint 300 Md$ de valorisation",
        "subtitle_fr": "Tour de financement record · 2026",
        "source": "Crunchbase", "category": "ia", "chart_type": "bar",
        "insight": "En un an, OpenAI a triplé sa valorisation : le capital parie "
                   "désormais sur l'IA générative comme sur aucune techno avant elle.",
        "chart_data": [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25},
                       {"label": "xAI", "value": 18}, {"label": "Mistral", "value": 6}],
        "key_points": ["Valorisation portée à 300 Md$, +200 % en un an",
                       "40 Md$ levés, plus gros tour privé de l'histoire tech",
                       "Microsoft et SoftBank en tête de table",
                       "Objectif : financer le calcul (data centers, puces)"],
    }
    slides = generate_carousel(sample)
    for i, png in enumerate(slides, 1):
        with open(f"test_carousel_{i}.png", "wb") as f:
            f.write(png)
        print(f"Slide {i} : {len(png) // 1024} KB")
    print(f"{len(slides)} slides générés.")
