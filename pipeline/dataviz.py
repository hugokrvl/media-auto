"""
Génère des infographies PNG haute qualité pour chaque post.
Style : thème CLAIR, accent jaune, badge "HK" en haut à droite, source en bas.
Inspiré du Studio Infographie (SAE DATA VIZ).

Types : kpi, donut, bar, courbe, infographic (fallback).
Données structurées fournies par l'analyzer (chart_data).
"""

import colorsys
import io
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

# ── Identité visuelle ────────────────────────────────────────────────────────
BG = "#FBFAF5"        # blanc chaud
INK = "#1A1A2E"       # texte principal
MUTED = "#8A8A9A"     # texte secondaire
ACCENT = "#F2B705"    # jaune/or HK
CARD = "#F2F1EA"      # fond des cartes KPI
GREEN = "#16A34A"
RED = "#DC2626"

# Palette dérivée (variations de l'accent + complémentaires chaudes)
PALETTE = ["#F2B705", "#E8920C", "#F4C430", "#D97706", "#FBD24E", "#B45309", "#FCE38A", "#92400E"]

SIZES = {
    "instagram": (1080, 1080),
    "twitter": (1200, 675),
    "linkedin": (1200, 627),
}

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.unicode_minus"] = False


# ── Helpers ──────────────────────────────────────────────────────────────────
def _fr(x, dec=None):
    """Format français : 12 345 / 1,2 M / 1,7."""
    try:
        v = float(str(x).replace(",", ".").replace(" ", ""))
    except Exception:
        return str(x)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        return sign + f"{a/1e9:.1f} Md".replace(".", ",")
    if a >= 1e6:
        return sign + f"{a/1e6:.1f} M".replace(".", ",")
    if a >= 1e4:
        return sign + f"{a:,.0f}".replace(",", " ")
    if dec is None:
        dec = 0 if float(a).is_integer() else 1
    return sign + f"{a:,.{dec}f}".replace(",", " ").replace(".", ",")


def _hex2rgb(hx):
    h = str(hx).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb2hex(r, g, b):
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _lum(hx):
    r, g, b = _hex2rgb(hx)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _variations(base, n):
    """n couleurs dans la même teinte (dégradé de luminosité)."""
    r, g, b = _hex2rgb(base)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if n <= 1:
        return [base]
    lo, hi = max(0.34, l - 0.22), min(0.78, l + 0.18)
    out = []
    for i in range(n):
        li = hi - (hi - lo) * i / (n - 1)
        rr, gg, bb = colorsys.hls_to_rgb(h, li, max(0.32, min(0.95, s)))
        out.append(_rgb2hex(rr, gg, bb))
    return out


def _cols(n):
    return [PALETTE[i % len(PALETTE)] for i in range(n)]


def _wrap(text, width):
    import textwrap
    return textwrap.wrap(text, width)


# ── Habillage commun (titre, badge HK, source) ───────────────────────────────
def _new_fig(size):
    w, h = size
    dpi = 120
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_facecolor(BG)
    return fig


def _draw_header(fig, title, subtitle):
    """Titre (français) en haut à gauche + barre accent. Renvoie le y bas du header."""
    figW, figH = fig.get_size_inches()
    # Barre accent verticale à gauche
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(Rectangle((0.055, 0.865), 0.006, 0.075, color=ACCENT, linewidth=0, zorder=5))

    lines = _wrap(title, 38)[:3]
    t_fs = 25 if len(lines) <= 2 else 21
    y = 0.935
    for line in lines:
        fig.text(0.08, y, line, ha="left", va="top", fontsize=t_fs,
                 fontweight="bold", color=INK)
        y -= (t_fs + 6) / (figH * 72)
    if subtitle:
        fig.text(0.08, y - 0.005, subtitle, ha="left", va="top",
                 fontsize=12.5, color=MUTED)
        y -= 0.03
    return y - 0.02


def _draw_badge(fig):
    """Badge rond 'HK' jaune en haut à droite (axes dédié à aspect égal)."""
    from matplotlib.patches import Circle
    figW, figH = fig.get_size_inches()
    # Axes carré ancré en haut à droite — largeur en fraction figure, hauteur ajustée à l'aspect
    w = 0.10
    h = w * (figW / figH)
    bax = fig.add_axes([0.865, 0.945 - h, w, h])
    bax.set_xlim(0, 1); bax.set_ylim(0, 1); bax.set_aspect("equal"); bax.axis("off")
    bax.add_patch(Circle((0.5, 0.5), 0.5, facecolor=ACCENT, edgecolor="none", zorder=6))
    bax.text(0.5, 0.5, "HK", ha="center", va="center", fontsize=17,
             fontweight="bold", color="#1A1A2E", zorder=7)


def _draw_source(fig, source):
    fig.text(0.08, 0.045, f"Source : {source}", ha="left", va="bottom",
             fontsize=10, color=MUTED)
    fig.text(0.92, 0.045, "@HK · données du jour", ha="right", va="bottom",
             fontsize=9.5, color=MUTED, alpha=0.8)


def _finish(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Extraction des données structurées ───────────────────────────────────────
def _series(chart_data):
    """chart_data = [{'label':..,'value':..}, ...] -> (labels, values)."""
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


# ── Graphiques ───────────────────────────────────────────────────────────────
def _chart_axes(fig, top):
    """Axes central pour le graphique, sous le header."""
    return fig.add_axes([0.09, 0.13, 0.82, max(0.3, top - 0.15)])


def _make_donut(fig, article, top):
    labels, vals = _series(article.get("chart_data"))
    if not vals or sum(vals) == 0:
        return _make_infographic(fig, article, top)
    ax = _chart_axes(fig, top)
    ax.set_facecolor(BG)
    cols = _variations(ACCENT, len(vals))
    total = sum(vals)

    def autop(p):
        return f"{p:.0f}%" if p >= 5 else ""

    wedges, _t, autotxt = ax.pie(
        vals, colors=cols, startangle=90, counterclock=False,
        autopct=autop, pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor=BG, linewidth=3),
        textprops=dict(fontsize=12, fontweight="bold"))
    for t, c in zip(autotxt, cols):
        t.set_color("#1A1A2E" if _lum(c) > 0.6 else "white")
    ax.set(aspect="equal")
    # Total au centre
    ax.text(0, 0.08, _fr(total), ha="center", va="center",
            fontsize=26, fontweight="bold", color=INK)
    ax.text(0, -0.16, "Total", ha="center", va="center", fontsize=12, color=MUTED)
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.14),
              ncol=min(3, len(labels)), frameon=False, fontsize=11,
              labelcolor=INK, handlelength=1.0, columnspacing=1.2)
    return fig


def _make_bar(fig, article, top):
    labels, vals = _series(article.get("chart_data"))
    if not vals:
        return _make_infographic(fig, article, top)
    ax = _chart_axes(fig, top)
    ax.set_facecolor(BG)
    # Barres horizontales, plus grande en haut
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    cols = _variations(ACCENT, len(vals))[::-1]
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.barh(range(len(vals)), vals, color=cols, height=0.62, zorder=3)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labels, color=INK, fontsize=12)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="x", color=MUTED, alpha=0.15, zorder=0)
    mx = max(vals) or 1
    for i, v in enumerate(vals):
        ax.text(v + mx * 0.015, i, _fr(v), va="center", ha="left",
                color=INK, fontsize=11, fontweight="bold")
    ax.margins(x=0.16)
    return fig


def _make_courbe(fig, article, top):
    labels, vals = _series(article.get("chart_data"))
    if not vals:
        return _make_infographic(fig, article, top)
    ax = _chart_axes(fig, top)
    ax.set_facecolor(BG)
    xs = list(range(len(vals)))
    ax.plot(xs, vals, color=ACCENT, lw=3.2, zorder=3,
            marker="o", ms=8, mfc="white", mec=ACCENT, mew=2.4)
    ax.fill_between(xs, vals, min(vals + [0]), color=ACCENT, alpha=0.14, zorder=1)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, color=INK, fontsize=11)
    ax.tick_params(axis="y", colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=MUTED, alpha=0.15)
    for x, v in zip(xs, vals):
        ax.annotate(_fr(v), (x, v), textcoords="offset points", xytext=(0, 12),
                    ha="center", color=INK, fontsize=10, fontweight="bold")
    ax.margins(y=0.22)
    return fig


def _make_kpi(fig, article, top):
    data = article.get("chart_data") or []
    items = [d for d in data if isinstance(d, dict)][:3]
    if not items:
        return _make_infographic(fig, article, top)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    figW, figH = fig.get_size_inches()
    asp = figW / figH
    cols = _variations(ACCENT, len(items))
    n = len(items)
    gap = 0.04
    cw = (0.84 - gap * (n - 1)) / n
    ch = min(0.34, cw * asp * 1.05)
    y = 0.30
    x0 = 0.08
    for i, r in enumerate(items):
        x = x0 + i * (cw + gap)
        col = cols[i]
        ax.add_patch(FancyBboxPatch((x, y), cw, ch,
                     boxstyle="round,pad=0,rounding_size=0.025",
                     mutation_aspect=asp, linewidth=0, facecolor=CARD, zorder=2))
        # Accent en haut de la carte
        ax.add_patch(Rectangle((x, y + ch - 0.012), cw, 0.012, color=col, zorder=3))
        cx = x + cw / 2
        val = _fr(r.get("value", 0))
        unit = str(r.get("unit", "")).strip()
        txt = val + ((" " + unit) if unit else "")
        fs = max(20, min(34, 320 / max(1, len(txt))))
        ax.text(cx, y + ch * 0.60, txt, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=col, zorder=4)
        ax.text(cx, y + ch * 0.30, str(r.get("label", ""))[:24], ha="center", va="center",
                fontsize=11.5, color=INK, zorder=4)
        ev = str(r.get("evolution", "")).replace("%", "").replace(",", ".").strip()
        try:
            evf = float(ev)
            up = evf >= 0
            ax.text(cx, y + ch * 0.12, f"{'▲' if up else '▼'} {abs(evf):.1f} %".replace(".", ","),
                    ha="center", va="center", fontsize=11,
                    color=GREEN if up else RED, fontweight="bold", zorder=4)
        except Exception:
            pass
    return fig


def _make_infographic(fig, article, top):
    """Fallback : titre + points clés à puces."""
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    points = article.get("key_points") or []
    if not points:
        labels, _ = _series(article.get("chart_data"))
        points = labels
    y = top - 0.04
    for pt in points[:4]:
        ax.add_patch(FancyBboxPatch((0.08, y - 0.07), 0.84, 0.075,
                     boxstyle="round,pad=0,rounding_size=0.02",
                     mutation_aspect=fig.get_size_inches()[0] / fig.get_size_inches()[1],
                     facecolor=CARD, linewidth=0, zorder=2))
        ax.text(0.105, y - 0.033, "▸", fontsize=15, color=ACCENT, va="center", zorder=3)
        wrapped = _wrap(str(pt), 60)
        ax.text(0.14, y - 0.033, wrapped[0] if wrapped else "", fontsize=12.5,
                color=INK, va="center", zorder=3)
        y -= 0.105
    return fig


# ── Point d'entrée ───────────────────────────────────────────────────────────
RENDERERS = {
    "kpi": _make_kpi,
    "donut": _make_donut,
    "bar": _make_bar,
    "courbe": _make_courbe,
    "line": _make_courbe,
    "infographic": _make_infographic,
}


def generate_image(article: dict, network: str = "instagram") -> bytes:
    size = SIZES.get(network, SIZES["instagram"])
    fig = _new_fig(size)

    title = article.get("title_fr") or article.get("title", "")
    subtitle = article.get("subtitle_fr", "") or article.get("category", "").capitalize()
    source = article.get("source", "")

    top = _draw_header(fig, title, subtitle)
    _draw_badge(fig)

    renderer = RENDERERS.get(article.get("chart_type", "infographic"), _make_infographic)
    renderer(fig, article, top)

    _draw_source(fig, source)
    return _finish(fig)


if __name__ == "__main__":
    tests = [
        {"title_fr": "L'inflation ralentit à 3,2 % en zone euro", "subtitle_fr": "Données mensuelles · BCE",
         "source": "Reuters", "chart_type": "kpi",
         "chart_data": [{"label": "Inflation", "value": "3.2", "unit": "%", "evolution": "-0.4"},
                        {"label": "Taux directeur", "value": "4.0", "unit": "%", "evolution": "0"},
                        {"label": "Chômage", "value": "6.5", "unit": "%", "evolution": "-0.1"}]},
        {"title_fr": "Répartition du marché des smartphones", "subtitle_fr": "Parts de marché T2 2026",
         "source": "Counterpoint", "chart_type": "donut",
         "chart_data": [{"label": "Apple", "value": 28}, {"label": "Samsung", "value": 22},
                        {"label": "Xiaomi", "value": 14}, {"label": "Autres", "value": 36}]},
        {"title_fr": "Les 5 plus grosses levées de fonds tech", "subtitle_fr": "En milliards de dollars",
         "source": "Crunchbase", "chart_type": "bar",
         "chart_data": [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25},
                        {"label": "xAI", "value": 18}, {"label": "Mistral", "value": 6}]},
        {"title_fr": "Évolution du Bitcoin sur 6 mois", "subtitle_fr": "Prix en milliers de dollars",
         "source": "CoinDesk", "chart_type": "courbe",
         "chart_data": [{"label": "Jan", "value": 92}, {"label": "Fév", "value": 88},
                        {"label": "Mar", "value": 95}, {"label": "Avr", "value": 102},
                        {"label": "Mai", "value": 98}, {"label": "Juin", "value": 105}]},
    ]
    for t in tests:
        img = generate_image(t, "instagram")
        with open(f"test_{t['chart_type']}.png", "wb") as f:
            f.write(img)
        print(f"Généré test_{t['chart_type']}.png ({len(img)//1024} KB)")
