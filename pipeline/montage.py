"""
Montage de plusieurs portraits réels sur un seul post 1080x1080 (charte HK).
Ex : les patrons OpenAI / Anthropic / Mistral côte à côte sur une même publication.

Photos RÉELLES uniquement (Wikipédia/Unsplash) → crédibilité. Bandeau titre fort,
chiffres surlignés en jaune, étiquette nom+rôle sous chaque visage.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFilter

import brand
from breaking import (
    _pil_font, _split_segments, _draw_multicolor_line, _draw_badge,
    _MUSTARD, _WHITE, _BLACK, _RED, _CAT_COLORS,
)

SIZE = 1080


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Recadre l'image pour remplir w×h (crop centré, léger biais haut pour le visage)."""
    src, tgt = im.width / im.height, w / h
    if src > tgt:
        nw = int(im.height * tgt)
        left = (im.width - nw) // 2
        im = im.crop((left, 0, left + nw, im.height))
    else:
        nh = int(im.width / tgt)
        top = int((im.height - nh) * 0.30)
        im = im.crop((0, top, im.width, top + nh))
    return im.resize((w, h), Image.LANCZOS)


def make_montage_image(article: dict, people: list[dict],
                       badge: str | None = None) -> bytes:
    """
    people : liste de {name, label, photo_bytes} (2 à 4 personnes).
    article : utilise title_fr/title (titre), category (badge couleur).
    badge : 2e badge rouge optionnel (ex : "EXCLU", None par défaut).
    """
    brand.ensure_fonts()
    people = [p for p in people if p.get("photo_bytes")][:4]
    n = max(1, len(people))

    canvas = Image.new("RGB", (SIZE, SIZE), (12, 13, 18))
    PHOTO_H = 620
    cell_w = SIZE // n

    f_name  = _pil_font("Anton-Regular.ttf", 30)
    f_role  = _pil_font("Barlow-SemiBold.ttf", 19)
    f_badge = _pil_font("Barlow-SemiBold.ttf", 26)
    f_foot  = _pil_font("Barlow-SemiBold.ttf", 26)
    f_hk    = _pil_font("Anton-Regular.ttf", 36)

    # ── Bande photos (haut) ────────────────────────────────────────────────────
    for i, p in enumerate(people):
        x = i * cell_w
        w = cell_w if i < n - 1 else SIZE - x   # dernière cellule comble l'arrondi
        try:
            por = Image.open(io.BytesIO(p["photo_bytes"])).convert("RGB")
            canvas.paste(_cover(por, w, PHOTO_H), (x, 0))
        except Exception:
            pass
        if i > 0:                               # séparateur moutarde entre visages
            d0 = ImageDraw.Draw(canvas)
            d0.rectangle([x - 2, 0, x + 1, PHOTO_H], fill=_MUSTARD)

    # ── Dégradé sombre (du milieu vers le bas) ─────────────────────────────────
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    g0 = int(PHOTO_H * 0.55)
    for y in range(SIZE):
        if y < g0:
            a = 0
        elif y < PHOTO_H:
            a = int(150 * ((y - g0) / (PHOTO_H - g0)))
        else:
            a = 255
        od.line([(0, y), (SIZE, y)], fill=(10, 11, 16, a))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # ── Étiquette nom + rôle sous chaque visage ────────────────────────────────
    for i, p in enumerate(people):
        cx = i * cell_w + (cell_w if i < n - 1 else SIZE - i * cell_w) // 2
        name = (p.get("name", "").split()[-1] or p.get("name", "")).upper()
        role = p.get("label", "")
        nb = f_name.getbbox(name)
        draw.text((cx - (nb[2] - nb[0]) // 2 + 2, PHOTO_H - 78 + 2), name,
                  font=f_name, fill=(0, 0, 0, 180))   # ombre
        draw.text((cx - (nb[2] - nb[0]) // 2, PHOTO_H - 78), name,
                  font=f_name, fill=_WHITE)
        if role:
            rb = f_role.getbbox(role)
            draw.text((cx - (rb[2] - rb[0]) // 2, PHOTO_H - 42), role,
                      font=f_role, fill=_MUSTARD)

    # ── Cadre jaune ────────────────────────────────────────────────────────────
    brd = 16
    draw.rectangle([brd // 2, brd // 2, SIZE - brd // 2, SIZE - brd // 2],
                   outline=(*_MUSTARD, 230), width=brd)

    # ── Badges (cat + optionnel) ───────────────────────────────────────────────
    cat = article.get("category", "tech")
    cat_label = brand.CATEGORY_LABELS.get(cat, cat.upper())
    cat_color = _CAT_COLORS.get(cat, _MUSTARD)
    by2 = _draw_badge(draw, cat_label, 48, 48, cat_color, f_badge)
    if badge:
        _draw_badge(draw, badge, 48, by2 + 10, _RED, f_badge)

    # ── Monogramme HK ──────────────────────────────────────────────────────────
    hk_r = 40
    hk_cx, hk_cy = SIZE - 68, 74
    draw.ellipse([hk_cx - hk_r, hk_cy - hk_r, hk_cx + hk_r, hk_cy + hk_r], fill=_MUSTARD)
    hb = f_hk.getbbox("HK")
    draw.text((hk_cx - (hb[2] - hb[0]) // 2, hk_cy - (hb[3] - hb[1]) // 2 - hb[1]),
              "HK", font=f_hk, fill=_BLACK)

    # ── Titre (ALL CAPS, chiffres en jaune) ────────────────────────────────────
    import textwrap
    title_full = (article.get("title_fr") or article.get("title", ""))
    if len(title_full) > 90:
        title_full = title_full[:88].rsplit(" ", 1)[0] + "…"
    title_raw = title_full.upper()
    margin = 48
    title_bottom = SIZE - 108
    avail_h = title_bottom - (PHOTO_H + 24)
    for fs, wrap_w in [(72, 20), (62, 23), (54, 26), (46, 30)]:
        lines = textwrap.wrap(title_raw, width=wrap_w)
        lh = int(fs * 1.08)
        if len(lines) * lh <= avail_h:
            break
    f_title = _pil_font("Anton-Regular.ttf", fs)
    top = title_bottom - len(lines) * lh
    for i, line in enumerate(lines):
        _draw_multicolor_line(draw, _split_segments(line), margin, top + i * lh,
                              f_title, f_title)

    # ── Séparateur + footer ────────────────────────────────────────────────────
    sep_y = title_bottom + 14
    draw.line([(margin, sep_y), (SIZE - margin, sep_y)], fill=(*_MUSTARD, 180), width=2)
    fy = sep_y + 16
    draw.text((margin, fy), "DÉCRYPTAGE EN DESCRIPTION", font=f_foot, fill=(*_MUSTARD, 210))
    handle = "@HK.MÉDIA"
    hbb = f_foot.getbbox(handle)
    draw.text((SIZE - margin - (hbb[2] - hbb[0]), fy), handle, font=f_foot, fill=(*_WHITE, 160))

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
