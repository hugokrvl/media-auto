"""
Génère des images PNG pour chaque post.
4 types : KPI cards, Donut chart, Bar/Line chart, Infographie.
Identité visuelle : fond noir #0D0D0D, accent jaune #FFD700, texte blanc.
"""

import io
import re
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Palette
BG = "#0D0D0D"
YELLOW = "#FFD700"
WHITE = "#F0F0F0"
GRAY = "#888888"
DARK_GRAY = "#1A1A1A"

# Tailles par réseau (px)
SIZES = {
    "instagram": (1080, 1080),
    "twitter": (1200, 675),
    "linkedin": (1200, 627),
}


def generate_image(article: dict, network: str = "instagram") -> bytes:
    """Génère et retourne l'image PNG en bytes selon le type de chart."""
    chart_type = article.get("chart_type", "infographic")
    size = SIZES.get(network, SIZES["instagram"])

    if chart_type == "kpi":
        return _make_kpi(article, size)
    elif chart_type == "donut":
        return _make_donut(article, size)
    elif chart_type == "bar":
        return _make_bar(article, size)
    else:
        return _make_infographic(article, size)


# ── KPI Cards ──────────────────────────────────────────────────────────────

def _make_kpi(article: dict, size: tuple) -> bytes:
    w, h = size
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    key_data = article.get("key_data", []) or ["Données non disponibles"]

    # Titre
    title = _truncate(article["title"], 60)
    ax.text(0.5, 0.92, title, transform=ax.transAxes,
            fontsize=16, fontweight="bold", color=WHITE,
            ha="center", va="top", wrap=True,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=DARK_GRAY, edgecolor=YELLOW, linewidth=1.5))

    # KPI cards
    n = min(len(key_data), 3)
    positions = np.linspace(0.15, 0.85, n)
    for i, (pos, kpi) in enumerate(zip(positions, key_data[:3])):
        # Cadre
        rect = FancyBboxPatch((pos - 0.13, 0.35), 0.26, 0.35,
                               boxstyle="round,pad=0.02",
                               facecolor=DARK_GRAY, edgecolor=YELLOW, linewidth=2,
                               transform=ax.transAxes)
        ax.add_patch(rect)
        # Valeur extraite
        value, label = _split_kpi(kpi)
        ax.text(pos, 0.60, value, transform=ax.transAxes,
                fontsize=22, fontweight="bold", color=YELLOW,
                ha="center", va="center")
        ax.text(pos, 0.42, label, transform=ax.transAxes,
                fontsize=10, color=GRAY, ha="center", va="center",
                wrap=True)

    _add_footer(ax, article)
    return _fig_to_bytes(fig)


# ── Donut Chart ─────────────────────────────────────────────────────────────

def _make_donut(article: dict, size: tuple) -> bytes:
    w, h = size
    dpi = 100
    fig, (ax_title, ax_chart) = plt.subplots(
        2, 1, figsize=(w / dpi, h / dpi), dpi=dpi,
        gridspec_kw={"height_ratios": [1, 4]}
    )
    fig.patch.set_facecolor(BG)

    # Titre
    ax_title.set_facecolor(BG)
    ax_title.axis("off")
    ax_title.text(0.5, 0.5, _truncate(article["title"], 70),
                  transform=ax_title.transAxes,
                  fontsize=14, fontweight="bold", color=WHITE,
                  ha="center", va="center", wrap=True)

    # Donut avec données simulées à partir des key_data
    key_data = article.get("key_data", [])
    labels, values = _extract_donut_data(key_data)
    colors = [YELLOW, "#FF8C00", "#FFA500", "#FFD700CC", "#888888"][:len(labels)]

    ax_chart.set_facecolor(BG)
    wedges, texts, autotexts = ax_chart.pie(
        values, labels=None, colors=colors,
        autopct="%1.1f%%", startangle=90,
        wedgeprops=dict(width=0.5, edgecolor=BG, linewidth=2),
        pctdistance=0.75,
    )
    for t in autotexts:
        t.set_color(BG)
        t.set_fontsize(10)
        t.set_fontweight("bold")

    ax_chart.legend(wedges, labels, loc="lower center", ncol=2,
                    facecolor=DARK_GRAY, edgecolor=YELLOW,
                    labelcolor=WHITE, fontsize=9,
                    bbox_to_anchor=(0.5, -0.05))

    _add_footer(ax_chart, article, transform=ax_chart.transAxes if False else None)
    plt.tight_layout(pad=1.5)
    return _fig_to_bytes(fig)


# ── Bar / Line Chart ─────────────────────────────────────────────────────────

def _make_bar(article: dict, size: tuple) -> bytes:
    w, h = size
    dpi = 100
    fig, (ax_title, ax_chart) = plt.subplots(
        2, 1, figsize=(w / dpi, h / dpi), dpi=dpi,
        gridspec_kw={"height_ratios": [1, 4]}
    )
    fig.patch.set_facecolor(BG)

    ax_title.set_facecolor(BG)
    ax_title.axis("off")
    ax_title.text(0.5, 0.5, _truncate(article["title"], 70),
                  transform=ax_title.transAxes,
                  fontsize=14, fontweight="bold", color=WHITE,
                  ha="center", va="center")

    ax_chart.set_facecolor(DARK_GRAY)
    key_data = article.get("key_data", [])
    labels, values = _extract_bar_data(key_data)

    bars = ax_chart.bar(labels, values, color=YELLOW, edgecolor=BG, linewidth=1.5, width=0.6)
    ax_chart.tick_params(colors=WHITE, labelsize=9)
    ax_chart.spines[["top", "right", "left"]].set_visible(False)
    ax_chart.spines["bottom"].set_color(GRAY)
    ax_chart.yaxis.set_visible(False)

    for bar, val in zip(bars, values):
        ax_chart.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                      f"{val:+.1f}%" if abs(val) < 200 else str(int(val)),
                      ha="center", va="bottom", color=YELLOW, fontsize=10, fontweight="bold")

    ax_chart.set_facecolor(DARK_GRAY)
    plt.tight_layout(pad=1.5)
    return _fig_to_bytes(fig)


# ── Infographie ──────────────────────────────────────────────────────────────

def _make_infographic(article: dict, size: tuple) -> bytes:
    w, h = size
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    # Barre déco gauche
    ax.axvline(x=0.03, ymin=0.1, ymax=0.9, color=YELLOW, linewidth=4,
               transform=ax.transAxes)

    # Catégorie tag
    cat = article.get("category", "").upper()
    ax.text(0.07, 0.93, f"[ {cat} ]", transform=ax.transAxes,
            fontsize=10, color=YELLOW, fontweight="bold", va="top")

    # Titre
    title_lines = textwrap.wrap(article["title"], 50)
    y = 0.85
    for line in title_lines[:3]:
        ax.text(0.07, y, line, transform=ax.transAxes,
                fontsize=18 if len(title_lines) == 1 else 15,
                fontweight="bold", color=WHITE, va="top")
        y -= 0.11

    # Points clés
    key_data = article.get("key_data", [])
    summary_points = key_data if key_data else [article.get("summary", "")[:120]]
    y -= 0.05
    for i, point in enumerate(summary_points[:3]):
        ax.text(0.07, y, f"▶  {point}", transform=ax.transAxes,
                fontsize=11, color=WHITE, va="top", alpha=0.9,
                wrap=True)
        y -= 0.12

    # Séparateur
    ax.axhline(y=0.12, xmin=0.07, xmax=0.93, color=GRAY, linewidth=0.5,
               transform=ax.transAxes)

    _add_footer(ax, article)
    return _fig_to_bytes(fig)


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _add_footer(ax, article: dict, transform=None):
    t = transform or ax.transAxes
    source = article.get("source", "")
    ax.text(0.07, 0.04, f"Source : {source}", transform=t,
            fontsize=8, color=GRAY, va="bottom")
    ax.text(0.93, 0.04, "MediaAuto", transform=t,
            fontsize=8, color=YELLOW, va="bottom", ha="right", fontweight="bold")


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1] + "…"


def _split_kpi(kpi: str) -> tuple[str, str]:
    match = re.search(r"([+\-]?\d[\d,.%€$M B]+)", kpi)
    if match:
        value = match.group(1)
        label = kpi.replace(value, "").strip(" :-")
        return value, label[:40]
    return kpi[:10], kpi[10:40]


def _extract_donut_data(key_data: list) -> tuple[list, list]:
    if not key_data:
        return ["Données", "Autres"], [60, 40]
    labels, values = [], []
    for item in key_data[:4]:
        nums = re.findall(r"\d+[.,]?\d*", item)
        val = float(nums[0].replace(",", ".")) if nums else 25.0
        label = re.sub(r"\d+[.,]?\d*[%€$]?", "", item).strip(" :-+")[:20] or "Segment"
        labels.append(label)
        values.append(val)
    if not values:
        return ["A", "B", "C"], [40, 35, 25]
    return labels, values


def _extract_bar_data(key_data: list) -> tuple[list, list]:
    if not key_data:
        return ["Jan", "Fév", "Mar"], [2.1, -1.3, 4.5]
    labels, values = [], []
    for item in key_data[:5]:
        nums = re.findall(r"[+\-]?\d+[.,]?\d*", item)
        val = float(nums[0].replace(",", ".")) if nums else 1.0
        label = re.sub(r"[+\-]?\d+[.,]?\d*[%€$]?", "", item).strip(" :-")[:10] or f"Val {len(labels)+1}"
        labels.append(label)
        values.append(val)
    if not values:
        return ["A", "B", "C"], [5, -2, 8]
    return labels, values


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


if __name__ == "__main__":
    test_article = {
        "title": "Tesla dépasse les 2 millions de véhicules vendus en 2024, un record absolu",
        "source": "Reuters Business",
        "category": "finance",
        "key_data": ["+18% vs 2023", "2.1M véhicules", "Marge nette 8.5%"],
        "chart_type": "kpi",
        "summary": "Tesla a annoncé un record de ventes en 2024...",
    }
    for ctype in ["kpi", "donut", "bar", "infographic"]:
        test_article["chart_type"] = ctype
        img_bytes = generate_image(test_article, "instagram")
        with open(f"test_{ctype}.png", "wb") as f:
            f.write(img_bytes)
        print(f"Généré test_{ctype}.png ({len(img_bytes)//1024}KB)")
