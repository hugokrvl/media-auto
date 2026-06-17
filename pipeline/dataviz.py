"""
Moteur d'infographies HK Média.
Style "Data punch" éditorial : cadre encadré, tag catégorie, monogramme HK,
gros chiffres Anton, titres serif DM Serif Display, fond crème.

Types : kpi, donut, bar, courbe, infographic (fallback).
Données structurées fournies par l'analyzer (chart_data / key_points).
"""

import io
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

import brand as B

SIZES = {
    "instagram": (1080, 1080),
    "twitter": (1200, 675),
    "linkedin": (1200, 627),
}


# ── Figure + chrome (cadre, tag, monogramme, footer) ─────────────────────────
def _new_fig(size):
    w, h = size
    dpi = 120
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_facecolor(B.CREAM)
    return fig


def _draw_frame(fig):
    """Cadre éditorial épais (encre) + double filet moutarde intérieur."""
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_zorder(0)
    m = 0.035
    # Cadre principal encre
    ax.add_patch(Rectangle((m, m), 1 - 2 * m, 1 - 2 * m, fill=False,
                 edgecolor=B.INK, linewidth=6, zorder=1))
    # Filet moutarde intérieur fin
    mi = m + 0.012
    ax.add_patch(Rectangle((mi, mi), 1 - 2 * mi, 1 - 2 * mi, fill=False,
                 edgecolor=B.MUSTARD, linewidth=1.4, zorder=1))
    return ax


def _draw_tag(ax, fig, category):
    """Pastille catégorie en haut à gauche."""
    F = fig._hk_fonts
    label = B.CATEGORY_LABELS.get(category, (category or "").upper())
    asp = fig.get_size_inches()[0] / fig.get_size_inches()[1]
    x, y = 0.075, 0.885
    w = 0.018 + 0.0135 * len(label)
    h = 0.044
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                 mutation_aspect=asp, facecolor=B.INK, edgecolor="none", zorder=4))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            color=B.MUSTARD, fontproperties=F["body_sb"], fontsize=13.5, zorder=5)


def _draw_monogram(fig):
    """Monogramme HK épuré en haut à droite : disque moutarde + 'HK' serif."""
    F = fig._hk_fonts
    figW, figH = fig.get_size_inches()
    w = 0.10
    h = w * (figW / figH)
    bax = fig.add_axes([0.83, 0.905 - h, w, h])
    bax.set_xlim(0, 1); bax.set_ylim(0, 1); bax.set_aspect("equal"); bax.axis("off")
    bax.set_zorder(6)
    bax.add_patch(Circle((0.5, 0.5), 0.5, facecolor=B.MUSTARD, edgecolor=B.INK,
                  linewidth=2.5, zorder=6))
    bax.text(0.5, 0.47, "HK", ha="center", va="center", color=B.INK,
             fontproperties=F["title"], fontsize=30, zorder=7)


def _draw_header(fig, ax, title, subtitle):
    """Titre serif éditorial COMPACT + sous-titre. Renvoie le y bas du header.
    Header volontairement resserré pour laisser un maximum de place à la data."""
    F = fig._hk_fonts
    figH = fig.get_size_inches()[1]
    # Titre limité à 2 lignes pour maximiser l'espace data
    lines = textwrap.wrap(title, 32)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][:30].rstrip() + "…"
    t_fs = 30 if len(lines) <= 1 else 27
    y = 0.835
    for line in lines:
        ax.text(0.075, y, line, ha="left", va="top", color=B.INK,
                fontproperties=F["title"], fontsize=t_fs, zorder=5)
        y -= (t_fs + 6) / (figH * 72)
    if subtitle:
        ax.text(0.075, y - 0.002, subtitle.upper(), ha="left", va="top", color=B.MUSTARD_DK,
                fontproperties=F["body_sb"], fontsize=12, zorder=5)
        y -= 0.028
    # Filet moutarde sous le header
    ax.plot([0.075, 0.27], [y - 0.008, y - 0.008], color=B.MUSTARD, linewidth=2.5, zorder=5)
    return y - 0.025


def _draw_footer(fig, ax, source):
    F = fig._hk_fonts
    ax.plot([0.075, 0.925], [0.105, 0.105], color=B.INK, linewidth=0.8, alpha=0.25, zorder=4)
    ax.text(0.075, 0.07, f"SOURCE — {source}".upper(), ha="left", va="center",
            color=B.INK_SOFT, fontproperties=F["body_md"], fontsize=10.5, zorder=5)
    ax.text(0.925, 0.07, "@HK.MÉDIA", ha="right", va="center",
            color=B.INK, fontproperties=F["body_sb"], fontsize=10.5, zorder=5)


def _draw_legend(ax, fig, labels, cols, y):
    """Légende manuelle centrée (pastille + label), max 3 par ligne.
    Placée dans une bande dédiée pour éviter tout chevauchement."""
    F = fig._hk_fonts
    asp = fig.get_size_inches()[0] / fig.get_size_inches()[1]
    per_row = min(3, len(labels))
    cellw = 0.255
    sq = 0.020
    rows = [labels[i:i + per_row] for i in range(0, len(labels), per_row)]
    rows_c = [cols[i:i + per_row] for i in range(0, len(cols), per_row)]
    for ri, (rlabels, rcols) in enumerate(zip(rows, rows_c)):
        total_w = len(rlabels) * cellw
        x0 = (1 - total_w) / 2
        yy = y - ri * 0.045
        for ci, (lab, col) in enumerate(zip(rlabels, rcols)):
            cx = x0 + ci * cellw
            ax.add_patch(FancyBboxPatch((cx, yy - sq * asp / 2), sq, sq * asp,
                         boxstyle="round,pad=0,rounding_size=0.004", mutation_aspect=asp,
                         facecolor=col, edgecolor=B.INK, linewidth=0.8, zorder=5))
            ax.text(cx + sq + 0.012, yy, str(lab)[:16], ha="left", va="center",
                    color=B.INK, fontproperties=F["body_md"], fontsize=12, zorder=5)


def _finish(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=B.CREAM)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Données ──────────────────────────────────────────────────────────────────
def _series(chart_data):
    labels, values = [], []
    for item in chart_data or []:
        if not isinstance(item, dict):
            continue
        labels.append(str(item.get("label", "")))
        try:
            values.append(float(str(item.get("value", 0)).replace(",", ".").replace(" ", "")))
        except Exception:
            values.append(0.0)
    return labels, values


def _content_axes(fig, top, bottom=0.14):
    return fig.add_axes([0.085, bottom, 0.83, max(0.3, top - bottom)])


# ── Graphiques ───────────────────────────────────────────────────────────────
def _make_kpi(fig, ax, article, top):
    F = fig._hk_fonts
    data = [d for d in (article.get("chart_data") or []) if isinstance(d, dict)][:3]
    if not data:
        return _make_infographic(fig, ax, article, top)
    asp = fig.get_size_inches()[0] / fig.get_size_inches()[1]
    cols = B.variations(B.MUSTARD, len(data))
    n = len(data)
    gap = 0.028
    x0, x1 = 0.075, 0.925
    cw = (x1 - x0 - gap * (n - 1)) / n
    # Cartes XXL : on remplit toute la zone data disponible
    avail = top - 0.155
    ch = min(avail, cw * asp * 1.25)
    y = 0.155 + (avail - ch) / 2
    # Chiffre dimensionné selon la largeur de carte (gros = data héros)
    num_fs = max(48, min(96, cw * 220))
    for i, r in enumerate(data):
        x = x0 + i * (cw + gap)
        col = cols[i]
        ax.add_patch(FancyBboxPatch((x, y), cw, ch, boxstyle="round,pad=0,rounding_size=0.022",
                     mutation_aspect=asp, facecolor=B.CREAM_2, edgecolor=B.INK,
                     linewidth=2.0, zorder=2))
        ax.add_patch(Rectangle((x, y + ch - 0.018), cw, 0.018, color=col, zorder=3))
        cx = x + cw / 2
        val = B.fr(r.get("value", 0))
        unit = str(r.get("unit", "")).strip()
        # CHIFFRE ÉNORME Anton (le héros du post)
        ax.text(cx, y + ch * 0.60, val, ha="center", va="center", color=B.INK,
                fontproperties=F["num"], fontsize=num_fs, zorder=4)
        if unit:
            ax.text(cx, y + ch * 0.40, unit, ha="center", va="center", color=B.MUSTARD_DK,
                    fontproperties=F["num"], fontsize=max(18, num_fs * 0.34), zorder=4)
        ax.text(cx, y + ch * 0.25, str(r.get("label", ""))[:26].upper(), ha="center", va="center",
                color=B.INK_SOFT, fontproperties=F["body_sb"], fontsize=13, zorder=4)
        ev = str(r.get("evolution", "")).replace("%", "").replace(",", ".").strip()
        try:
            evf = float(ev)
            up = evf >= 0
            sign = "+" if up else "−"
            ax.text(cx, y + ch * 0.105, f"{sign}{abs(evf):.1f} %".replace(".", ","),
                    ha="center", va="center", color=B.GREEN if up else B.RED,
                    fontproperties=F["body_sb"], fontsize=15, zorder=4)
        except Exception:
            pass
    return fig


def _make_donut(fig, ax, article, top):
    F = fig._hk_fonts
    labels, vals = _series(article.get("chart_data"))
    if not vals or sum(vals) == 0:
        return _make_infographic(fig, ax, article, top)
    # Bande légende réservée en bas (2 lignes possibles) -> le donut occupe le reste
    n_rows = (len(labels) + 2) // 3
    legend_top = 0.20 + (n_rows - 1) * 0.045
    chart_bottom = legend_top + 0.06
    cax = fig.add_axes([0.18, chart_bottom, 0.64, max(0.28, top - chart_bottom - 0.02)])
    cax.set_facecolor(B.CREAM)
    cols = B.variations(B.MUSTARD, len(vals))
    total = sum(vals)

    def autop(p):
        return f"{p:.0f}%" if p >= 4 else ""

    wedges, _t, autotxt = cax.pie(
        vals, colors=cols, startangle=90, counterclock=False,
        autopct=autop, pctdistance=0.80,
        wedgeprops=dict(width=0.40, edgecolor=B.CREAM, linewidth=4),
        textprops=dict(fontproperties=F["num"], fontsize=17))
    for t, c in zip(autotxt, cols):
        t.set_color(B.INK if B.lum(c) > 0.58 else B.CREAM)
    cax.set(aspect="equal")
    # Gros total central
    cax.text(0, 0.10, B.fr(total), ha="center", va="center", color=B.INK,
             fontproperties=F["num"], fontsize=48)
    cax.text(0, -0.20, "TOTAL", ha="center", va="center", color=B.MUTED,
             fontproperties=F["body_sb"], fontsize=12)
    # Légende manuelle (sans chevauchement)
    _draw_legend(ax, fig, labels, cols, y=legend_top)
    return fig


def _make_bar(fig, ax, article, top):
    F = fig._hk_fonts
    labels, vals = _series(article.get("chart_data"))
    if not vals:
        return _make_infographic(fig, ax, article, top)
    # Label AU-DESSUS de chaque barre (pas de marge gauche perdue, look éditorial)
    cax = fig.add_axes([0.075, 0.155, 0.85, max(0.3, top - 0.165)])
    cax.set_facecolor(B.CREAM)
    order = sorted(range(len(vals)), key=lambda i: vals[i], reverse=True)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    cols = B.variations(B.MUSTARD, len(vals))
    ypos = list(range(len(vals)))[::-1]  # plus grand en haut
    for sp in cax.spines.values():
        sp.set_visible(False)
    cax.barh(ypos, vals, color=cols, height=0.52, zorder=3,
             edgecolor=B.INK, linewidth=1.6)
    cax.set_yticks([])
    cax.set_xticks([])
    mx = max(vals) or 1
    for yp, lab, v in zip(ypos, labels, vals):
        # Nom au-dessus de la barre, aligné à gauche
        cax.text(0, yp + 0.42, lab.upper(), va="bottom", ha="left", color=B.INK_SOFT,
                 fontproperties=F["body_sb"], fontsize=14)
        # Valeur au bout de la barre
        cax.text(v + mx * 0.02, yp, B.fr(v), va="center", ha="left", color=B.INK,
                 fontproperties=F["num"], fontsize=28)
    cax.set_xlim(0, mx * 1.22)
    cax.set_ylim(-0.7, len(vals) - 0.3)
    return fig


def _make_courbe(fig, ax, article, top):
    F = fig._hk_fonts
    labels, vals = _series(article.get("chart_data"))
    if not vals:
        return _make_infographic(fig, ax, article, top)
    cax = _content_axes(fig, top, bottom=0.155)
    cax.set_facecolor(B.CREAM)
    xs = list(range(len(vals)))
    cax.plot(xs, vals, color=B.INK, lw=4.2, zorder=3,
             marker="o", ms=14, mfc=B.MUSTARD, mec=B.INK, mew=2.6)
    cax.fill_between(xs, vals, min(vals + [0]), color=B.MUSTARD, alpha=0.25, zorder=1)
    for sp in ("top", "right"):
        cax.spines[sp].set_visible(False)
    cax.spines["left"].set_color(B.INK_SOFT)
    cax.spines["bottom"].set_color(B.INK_SOFT)
    cax.set_xticks(xs)
    cax.set_xticklabels([l.upper() for l in labels], color=B.INK, fontsize=13)
    for lab in cax.get_xticklabels():
        lab.set_fontproperties(F["body_sb"])
    cax.tick_params(axis="y", colors=B.MUTED, labelsize=10)
    cax.grid(axis="y", color=B.MUTED, alpha=0.18)
    for x, v in zip(xs, vals):
        cax.annotate(B.fr(v), (x, v), textcoords="offset points", xytext=(0, 18),
                     ha="center", color=B.INK, fontproperties=F["num"], fontsize=22)
    cax.margins(y=0.30)
    # plancher de l'axe juste sous le min pour éviter le vide
    lo = min(vals); hi = max(vals)
    pad = (hi - lo) * 0.25 or hi * 0.1 or 1
    cax.set_ylim(lo - pad, hi + pad * 1.4)
    return fig


def _make_infographic(fig, ax, article, top):
    F = fig._hk_fonts
    asp = fig.get_size_inches()[0] / fig.get_size_inches()[1]
    points = article.get("key_points") or []
    if not points:
        labels, _ = _series(article.get("chart_data"))
        points = labels
    points = [p for p in points if str(p).strip()][:4]
    if not points:
        points = [article.get("subtitle_fr", "") or "Information du jour"]
    y = top - 0.02
    for i, pt in enumerate(points):
        col = B.variations(B.MUSTARD, max(2, len(points)))[i % max(2, len(points))]
        ax.add_patch(FancyBboxPatch((0.085, y - 0.085), 0.83, 0.078,
                     boxstyle="round,pad=0,rounding_size=0.018", mutation_aspect=asp,
                     facecolor=B.CREAM_2, edgecolor=B.INK, linewidth=1.4, zorder=2))
        # Pastille numéro
        ax.add_patch(Circle((0.125, y - 0.046), 0.022, facecolor=col, edgecolor=B.INK,
                     linewidth=1.2, zorder=3))
        ax.text(0.125, y - 0.046, str(i + 1), ha="center", va="center", color=B.INK,
                fontproperties=F["num"], fontsize=15, zorder=4)
        wrapped = textwrap.wrap(str(pt), 52)
        ax.text(0.17, y - 0.046, wrapped[0] if wrapped else "", ha="left", va="center",
                color=B.INK, fontproperties=F["body_md"], fontsize=13, zorder=4)
        y -= 0.105
    return fig


RENDERERS = {
    "kpi": _make_kpi, "donut": _make_donut, "bar": _make_bar,
    "courbe": _make_courbe, "line": _make_courbe, "infographic": _make_infographic,
}


# ── Point d'entrée ───────────────────────────────────────────────────────────
def generate_image(article: dict, network: str = "instagram") -> bytes:
    size = SIZES.get(network, SIZES["instagram"])
    fig = _new_fig(size)
    fig._hk_fonts = B.fonts()

    title = article.get("title_fr") or article.get("title", "")
    subtitle = article.get("subtitle_fr", "")
    source = article.get("source", "")
    category = article.get("category", "")

    base_ax = _draw_frame(fig)
    _draw_tag(base_ax, fig, category)
    _draw_monogram(fig)
    top = _draw_header(fig, base_ax, title, subtitle)

    renderer = RENDERERS.get(article.get("chart_type", "infographic"), _make_infographic)
    renderer(fig, base_ax, article, top)

    _draw_footer(fig, base_ax, source)
    return _finish(fig)


if __name__ == "__main__":
    tests = [
        {"title_fr": "L'inflation ralentit à 3,2 % en zone euro", "subtitle_fr": "Données mensuelles · BCE",
         "source": "Reuters", "category": "finance", "chart_type": "kpi",
         "chart_data": [{"label": "Inflation", "value": "3.2", "unit": "%", "evolution": "-0.4"},
                        {"label": "Taux directeur", "value": "4.0", "unit": "%", "evolution": "0"},
                        {"label": "Chômage", "value": "6.5", "unit": "%", "evolution": "-0.1"}]},
        {"title_fr": "Répartition du marché des smartphones", "subtitle_fr": "Parts de marché T2 2026",
         "source": "Counterpoint", "category": "tech", "chart_type": "donut",
         "chart_data": [{"label": "Apple", "value": 28}, {"label": "Samsung", "value": 22},
                        {"label": "Xiaomi", "value": 14}, {"label": "Autres", "value": 36}]},
        {"title_fr": "Les plus grosses levées de fonds tech", "subtitle_fr": "En milliards de dollars",
         "source": "Crunchbase", "category": "tech", "chart_type": "bar",
         "chart_data": [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25},
                        {"label": "xAI", "value": 18}, {"label": "Mistral", "value": 6}]},
        {"title_fr": "Évolution du Bitcoin sur 6 mois", "subtitle_fr": "Prix en milliers de dollars",
         "source": "CoinDesk", "category": "finance", "chart_type": "courbe",
         "chart_data": [{"label": "Jan", "value": 92}, {"label": "Fév", "value": 88},
                        {"label": "Mar", "value": 95}, {"label": "Avr", "value": 102},
                        {"label": "Mai", "value": 98}, {"label": "Juin", "value": 105}]},
        {"title_fr": "Sommet sur le climat : les 4 annonces clés", "subtitle_fr": "COP · Décisions du jour",
         "source": "AFP", "category": "general", "chart_type": "infographic",
         "key_points": ["Fin des subventions au charbon d'ici 2030",
                        "Fonds de 100 Md$ pour les pays du Sud",
                        "Objectif -55 % d'émissions en 2035",
                        "40 pays signataires de l'accord"]},
    ]
    for t in tests:
        img = generate_image(t, "instagram")
        with open(f"test_{t['chart_type']}.png", "wb") as f:
            f.write(img)
        print(f"Généré test_{t['chart_type']}.png ({len(img)//1024} KB)")
