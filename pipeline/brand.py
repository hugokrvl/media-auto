"""
Charte graphique HK Média — identité visuelle unique.

Direction : "Data punch" éditorial · serif fort · jaune moutarde + crème.
Polices custom (DM Serif Display, Anton, Barlow) téléchargées et mises en cache.
Tout le reste du projet importe les constantes et helpers d'ici.
"""

import os
import urllib.request
import matplotlib.font_manager as fm

# ── Palette signature ────────────────────────────────────────────────────────
CREAM = "#F5EDDA"      # fond papier chaud
CREAM_2 = "#EFE4C9"    # panneaux / cartes
INK = "#1C1A15"        # encre (texte, cadre)
INK_SOFT = "#4A4536"   # encre adoucie
MUSTARD = "#E2A50F"    # jaune moutarde (primaire)
MUSTARD_DK = "#B07E07" # moutarde foncée (profondeur)
MUTED = "#9A9077"      # gris chaud
GREEN = "#2F7D4E"      # évolution positive
RED = "#C0392B"        # évolution négative

# Dégradé moutarde pour graphiques multi-segments (chaud, cohérent)
PALETTE = ["#E2A50F", "#C98A0A", "#F0C04B", "#A66E06", "#F7D886", "#7E5304", "#D9A53A", "#5C3D08"]

# ── Polices custom (Google Fonts, statiques, licence OFL) ─────────────────────
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fonts")
_BASE = "https://github.com/google/fonts/raw/main/ofl"
FONTS = {
    "DMSerifDisplay-Regular.ttf": f"{_BASE}/dmserifdisplay/DMSerifDisplay-Regular.ttf",
    "DMSerifDisplay-Italic.ttf": f"{_BASE}/dmserifdisplay/DMSerifDisplay-Italic.ttf",
    "Anton-Regular.ttf": f"{_BASE}/anton/Anton-Regular.ttf",
    "Barlow-Regular.ttf": f"{_BASE}/barlow/Barlow-Regular.ttf",
    "Barlow-Medium.ttf": f"{_BASE}/barlow/Barlow-Medium.ttf",
    "Barlow-SemiBold.ttf": f"{_BASE}/barlow/Barlow-SemiBold.ttf",
}

_loaded = False


def ensure_fonts():
    """Télécharge (une fois) et enregistre les polices dans matplotlib."""
    global _loaded
    if _loaded:
        return
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, url in FONTS.items():
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
                    f.write(r.read())
            except Exception as e:
                print(f"[BRAND] Téléchargement police échoué {name}: {e}")
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
            except Exception:
                pass
    _loaded = True


def _fp(filename, fallback_family, fallback_weight="normal"):
    path = os.path.join(FONT_DIR, filename)
    if os.path.exists(path):
        return fm.FontProperties(fname=path)
    return fm.FontProperties(family=fallback_family, weight=fallback_weight)


def fonts():
    """Renvoie un dict de FontProperties prêts à l'emploi."""
    ensure_fonts()
    return {
        "title": _fp("DMSerifDisplay-Regular.ttf", "DejaVu Serif", "bold"),
        "title_it": _fp("DMSerifDisplay-Italic.ttf", "DejaVu Serif"),
        "num": _fp("Anton-Regular.ttf", "DejaVu Sans", "bold"),
        "body": _fp("Barlow-Regular.ttf", "DejaVu Sans"),
        "body_md": _fp("Barlow-Medium.ttf", "DejaVu Sans"),
        "body_sb": _fp("Barlow-SemiBold.ttf", "DejaVu Sans", "bold"),
    }


def fr(x, dec=None):
    """Format français : 12 345 / 1,2 M / 1,7."""
    try:
        v = float(str(x).replace(",", ".").replace(" ", ""))
    except Exception:
        return str(x)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        txt = f"{a/1e9:.1f}".rstrip("0").rstrip(".")
        return sign + txt.replace(".", ",") + " Md"
    if a >= 1e6:
        txt = f"{a/1e6:.1f}".rstrip("0").rstrip(".")
        return sign + txt.replace(".", ",") + " M"
    if a >= 1e4:
        return sign + f"{a:,.0f}".replace(",", " ")
    if dec is None:
        dec = 0 if float(a).is_integer() else 1
    return sign + f"{a:,.{dec}f}".replace(",", " ").replace(".", ",")


# ── Helpers couleur ──────────────────────────────────────────────────────────
def hex2rgb(hx):
    h = str(hx).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb2hex(r, g, b):
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def lum(hx):
    r, g, b = hex2rgb(hx)
    return 0.299 * r + 0.587 * g + 0.114 * b


def variations(base, n):
    """n teintes dérivées de `base` (dégradé de luminosité)."""
    import colorsys
    r, g, b = hex2rgb(base)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if n <= 1:
        return [base]
    lo, hi = max(0.32, l - 0.22), min(0.80, l + 0.20)
    out = []
    for i in range(n):
        li = hi - (hi - lo) * i / (n - 1)
        rr, gg, bb = colorsys.hls_to_rgb(h, li, max(0.30, min(0.95, s)))
        out.append(rgb2hex(rr, gg, bb))
    return out


CATEGORY_LABELS = {
    "finance": "FINANCE",
    "tech": "TECH",
    "ia": "IA",
    "crypto": "CRYPTO",
    "quantique": "QUANTIQUE",
    "general": "ACTUALITÉ",
    "sport": "SPORT",
    "factcheck": "VÉRIF",
}
