"""
Rendu des posts "Breaking News" : photo plein cadre 1080x1080 + overlay titre.

Style : photo de fond, gradient sombre bas, badge BREAKING rouge,
titre blanc gras (DM Serif Display), source + @HK.MÉDIA en bas.
"""

import io
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

import brand

FONT_DIR = brand.FONT_DIR
SIZE = 1080  # carré universel

# Couleurs overlay
_BLACK     = (0, 0, 0)
_WHITE     = (255, 255, 255)
_MUSTARD   = (226, 165, 15)
_RED_BADGE = (204, 40, 40)
_CAT_COLORS = {
    "finance":   (226, 165, 15),
    "tech":      (129, 140, 248),
    "general":   (74, 222, 128),
    "sport":     (251, 146, 60),
    "factcheck": (248, 113, 113),
}


def _pil_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, filename)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient_overlay(draw: ImageDraw.ImageDraw, w: int, h: int):
    """Gradient noir transparent : opaque en bas, invisible en haut."""
    for y in range(h):
        # Commence à s'assombrir à mi-hauteur, opaque à 90 % de la hauteur
        t = max(0.0, (y - h * 0.35) / (h * 0.65))
        alpha = int(min(235, 255 * t ** 1.4))
        draw.line([(0, y), (w - 1, y)], fill=(*_BLACK, alpha))


def _draw_badge(draw: ImageDraw.ImageDraw, label: str, x: int, y: int,
                bg: tuple, font: ImageFont.FreeTypeFont):
    """Badge pill coloré avec label majuscule."""
    bbox = font.getbbox(label)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 22, 10
    rx, ry = x + tw + pad_x * 2, y + th + pad_y * 2
    draw.rounded_rectangle([x, y, rx, ry], radius=6, fill=bg)
    draw.text((x + pad_x, y + pad_y - bbox[1]), label, font=font, fill=_WHITE)
    return ry + 20  # retourne le bas du badge + marge


def make_breaking_image(article: dict, photo_bytes: bytes) -> bytes:
    """
    Génère un post Breaking News 1080x1080 à partir de photo_bytes (JPEG/PNG).
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

    # ── Overlay gradient ────────────────────────────────────────────────────────
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    _gradient_overlay(ImageDraw.Draw(overlay), SIZE, SIZE)
    photo = Image.alpha_composite(photo.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(photo)

    # ── Polices ─────────────────────────────────────────────────────────────────
    f_badge   = _pil_font("Barlow-SemiBold.ttf", 28)
    f_title   = _pil_font("DMSerifDisplay-Regular.ttf", 72)
    f_source  = _pil_font("Barlow-Medium.ttf", 28)

    # ── Cadre jaune (signature HK) ───────────────────────────────────────────────
    border = 18
    draw.rectangle([border // 2, border // 2,
                    SIZE - border // 2, SIZE - border // 2],
                   outline=_MUSTARD, width=border)

    # ── Badges en haut à gauche ──────────────────────────────────────────────────
    cat = article.get("category", "general")
    cat_label = brand.CATEGORY_LABELS.get(cat, cat.upper())
    cat_color = _CAT_COLORS.get(cat, _MUSTARD)
    badge_x, badge_y = 52, 52
    badge_bottom = _draw_badge(draw, cat_label, badge_x, badge_y, cat_color, f_badge)
    _draw_badge(draw, "BREAKING", badge_x, badge_bottom, _RED_BADGE, f_badge)

    # ── Monogramme HK (haut droite) ──────────────────────────────────────────────
    f_hk = _pil_font("Anton-Regular.ttf", 38)
    hk_r = 44
    hk_cx, hk_cy = SIZE - 72, 80
    draw.ellipse([hk_cx - hk_r, hk_cy - hk_r, hk_cx + hk_r, hk_cy + hk_r],
                 fill=_MUSTARD)
    hk_bbox = f_hk.getbbox("HK")
    draw.text((hk_cx - (hk_bbox[2] - hk_bbox[0]) // 2,
               hk_cy - (hk_bbox[3] - hk_bbox[1]) // 2 - hk_bbox[1]),
              "HK", font=f_hk, fill=_BLACK)

    # ── Titre (zone basse, blanc) ─────────────────────────────────────────────────
    title = article.get("title_fr") or article.get("title", "")
    lines = textwrap.wrap(title, width=24)[:4]  # max 4 lignes

    line_h = 82
    total_h = len(lines) * line_h
    title_y = SIZE - 160 - total_h
    for line in lines:
        # Ombre portée légère
        draw.text((52 + 3, title_y + 3), line, font=f_title, fill=(0, 0, 0, 180))
        draw.text((52, title_y), line, font=f_title, fill=_WHITE)
        title_y += line_h

    # ── Footer ────────────────────────────────────────────────────────────────────
    source = (article.get("source") or "").upper()
    footer_y = SIZE - 72
    draw.text((52, footer_y), f"SOURCE — {source}", font=f_source, fill=(*_MUSTARD, 220))
    handle = "@HK.MÉDIA"
    hb = f_source.getbbox(handle)
    draw.text((SIZE - 52 - (hb[2] - hb[0]), footer_y),
              handle, font=f_source, fill=(*_WHITE, 180))

    # ── Export PNG ────────────────────────────────────────────────────────────────
    out = io.BytesIO()
    photo.save(out, format="PNG", optimize=True)
    return out.getvalue()
