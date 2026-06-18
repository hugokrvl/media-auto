"""
Rendu des posts "Breaking News" : photo plein cadre 1080x1080 + overlay titre.

Style inspiré des grandes pages médias :
- Photo pleine frame libre de droits (Unsplash / Pexels)
- Gradient sombre concentré en bas
- Badge BREAKING rouge + badge catégorie
- Titre ALL CAPS Anton blanc, chiffres/stats automatiquement en JAUNE
- Footer « DÉCRYPTAGE EN DESCRIPTION »
- Monogramme HK haut droite
"""

import io
import os
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import brand

FONT_DIR = brand.FONT_DIR
SIZE = 1080

_BLACK   = (0, 0, 0)
_WHITE   = (255, 255, 255)
_MUSTARD = (226, 165, 15)
_RED     = (210, 35, 35)
_CAT_COLORS = {
    "finance":   (226, 165, 15),
    "tech":      (129, 140, 248),
    "general":   (74, 222, 128),
    "sport":     (251, 146, 60),
    "factcheck": (248, 113, 113),
}

# Regex : détecte chiffres, %, €, M, Md, k — à surligner en jaune
_NUM_RE = re.compile(
    r"(\d[\d\s]*"
    r"(?:[\.,]\d+)?"
    r"(?:\s*(?:€|\$|%|M(?:DS?|ILLIARDS?|ILLIONS?)?|K|k))?)",
    re.IGNORECASE,
)


def _pil_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, filename)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient_overlay(img: Image.Image) -> Image.Image:
    """Gradient noir : transparent en haut, très opaque en bas (60% de la hauteur)."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    grad_start = int(h * 0.30)  # commence à 30% du haut
    for y in range(h):
        if y < grad_start:
            alpha = 0
        else:
            t = (y - grad_start) / (h - grad_start)
            alpha = int(245 * (t ** 1.3))
        draw.line([(0, y), (w - 1, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _split_segments(text: str) -> list[tuple[str, bool]]:
    """Découpe le texte en segments (normal=False, chiffre/stat=True)."""
    parts = _NUM_RE.split(text)
    segments = []
    for p in parts:
        if not p:
            continue
        is_num = bool(_NUM_RE.fullmatch(p.strip()) and p.strip())
        segments.append((p, is_num))
    return segments


def _line_width(segments: list[tuple[str, bool]],
                f_normal: ImageFont.FreeTypeFont,
                f_highlight: ImageFont.FreeTypeFont) -> int:
    total = 0
    for text, hi in segments:
        f = f_highlight if hi else f_normal
        bb = f.getbbox(text)
        total += bb[2] - bb[0]
    return total


def _draw_multicolor_line(draw: ImageDraw.ImageDraw,
                           segments: list[tuple[str, bool]],
                           x: int, y: int,
                           f_normal: ImageFont.FreeTypeFont,
                           f_highlight: ImageFont.FreeTypeFont,
                           shadow_offset: int = 4):
    """Dessine une ligne avec ombre portée + surlignage jaune des chiffres."""
    cur_x = x
    # Ombre (passe 1)
    for text, hi in segments:
        f = f_highlight if hi else f_normal
        bb = f.getbbox(text)
        draw.text((cur_x + shadow_offset, y + shadow_offset), text,
                  font=f, fill=(0, 0, 0, 160))
        cur_x += bb[2] - bb[0]
    # Texte coloré (passe 2)
    cur_x = x
    for text, hi in segments:
        f = f_highlight if hi else f_normal
        color = _MUSTARD if hi else _WHITE
        bb = f.getbbox(text)
        draw.text((cur_x, y), text, font=f, fill=color)
        cur_x += bb[2] - bb[0]


def _draw_badge(draw: ImageDraw.ImageDraw, label: str, x: int, y: int,
                bg: tuple, font: ImageFont.FreeTypeFont) -> int:
    """Badge pill. Retourne le bord bas du badge."""
    bb = font.getbbox(label)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    px, py = 20, 9
    x2, y2 = x + tw + px * 2, y + th + py * 2
    draw.rounded_rectangle([x, y, x2, y2], radius=6, fill=bg)
    draw.text((x + px, y + py - bb[1]), label, font=font, fill=_WHITE)
    return y2


def make_breaking_image(article: dict, photo_bytes: bytes) -> bytes:
    """
    Génère un post Breaking News 1080x1080.
    photo_bytes : JPEG ou PNG d'une photo libre de droits.
    Retourne les bytes PNG de l'image finale.
    """
    brand.ensure_fonts()

    # ── Photo de fond ──────────────────────────────────────────────────────────
    photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    w, h = photo.size
    side = min(w, h)
    photo = photo.crop(((w - side) // 2, (h - side) // 2,
                        (w + side) // 2, (h + side) // 2))
    photo = photo.resize((SIZE, SIZE), Image.LANCZOS)

    # Légère désaturation pour que le texte ressorte mieux
    gray = photo.convert("L").convert("RGB")
    photo = Image.blend(photo, gray, alpha=0.25)

    # ── Gradient overlay ───────────────────────────────────────────────────────
    photo = _gradient_overlay(photo).convert("RGB")
    draw = ImageDraw.Draw(photo, "RGBA")

    # ── Polices ────────────────────────────────────────────────────────────────
    f_badge  = _pil_font("Barlow-SemiBold.ttf", 26)
    f_footer = _pil_font("Barlow-SemiBold.ttf", 26)
    f_hk     = _pil_font("Anton-Regular.ttf", 36)

    # ── Cadre jaune HK ─────────────────────────────────────────────────────────
    brd = 16
    draw.rectangle([brd // 2, brd // 2, SIZE - brd // 2, SIZE - brd // 2],
                   outline=(*_MUSTARD, 230), width=brd)

    # ── Badges haut gauche ─────────────────────────────────────────────────────
    cat = article.get("category", "general")
    cat_label = brand.CATEGORY_LABELS.get(cat, cat.upper())
    cat_color = _CAT_COLORS.get(cat, _MUSTARD)
    bx, by = 48, 48
    by2 = _draw_badge(draw, cat_label, bx, by, cat_color, f_badge)
    _draw_badge(draw, "BREAKING", bx, by2 + 10, _RED, f_badge)

    # ── Monogramme HK haut droite ──────────────────────────────────────────────
    hk_r = 40
    hk_cx, hk_cy = SIZE - 68, 74
    draw.ellipse([hk_cx - hk_r, hk_cy - hk_r, hk_cx + hk_r, hk_cy + hk_r],
                 fill=_MUSTARD)
    hk_bb = f_hk.getbbox("HK")
    draw.text((hk_cx - (hk_bb[2] - hk_bb[0]) // 2,
               hk_cy - (hk_bb[3] - hk_bb[1]) // 2 - hk_bb[1]),
              "HK", font=f_hk, fill=_BLACK)

    # ── Titre ALL CAPS + surlignage jaune des chiffres ─────────────────────────
    # Max 80 chars : breaking = court et percutant. On coupe au dernier mot entier.
    title_full = (article.get("title_fr") or article.get("title", ""))
    if len(title_full) > 80:
        title_full = title_full[:78].rsplit(" ", 1)[0] + "…"
    title_raw = title_full.upper()
    margin_left = 48
    title_bottom = SIZE - 110
    available_h = title_bottom - int(SIZE * 0.40)  # zone disponible (~60% bas)

    # Taille de police adaptative : commence à 88, réduit si trop de lignes
    for font_size, wrap_w in [(88, 18), (76, 20), (64, 23), (54, 26)]:
        lines_raw = textwrap.wrap(title_raw, width=wrap_w)
        line_h = int(font_size * 1.08)
        if len(lines_raw) * line_h <= available_h:
            break  # ça rentre

    f_title    = _pil_font("Anton-Regular.ttf", font_size)
    f_title_hi = _pil_font("Anton-Regular.ttf", font_size)

    total_title_h = len(lines_raw) * line_h
    title_top = title_bottom - total_title_h

    for i, line in enumerate(lines_raw):
        segs = _split_segments(line)
        y = title_top + i * line_h
        _draw_multicolor_line(draw, segs, margin_left, y, f_title, f_title_hi)

    # ── Séparateur ─────────────────────────────────────────────────────────────
    sep_y = title_bottom + 14
    draw.line([(margin_left, sep_y), (SIZE - margin_left, sep_y)],
              fill=(*_MUSTARD, 180), width=2)

    # ── Footer ─────────────────────────────────────────────────────────────────
    footer_y = sep_y + 16
    draw.text((margin_left, footer_y), "DÉCRYPTAGE EN DESCRIPTION",
              font=f_footer, fill=(*_MUSTARD, 210))
    handle = "@HK.MÉDIA"
    hb = f_footer.getbbox(handle)
    draw.text((SIZE - margin_left - (hb[2] - hb[0]), footer_y),
              handle, font=f_footer, fill=(*_WHITE, 160))

    # ── Export PNG ─────────────────────────────────────────────────────────────
    out = io.BytesIO()
    photo.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
