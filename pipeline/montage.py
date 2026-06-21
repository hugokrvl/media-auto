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


# ── Détourage (rembg) ──────────────────────────────────────────────────────────
# Modèle configurable via REMBG_MODEL (défaut : isnet-general-use = bords nets, ~178 Mo) :
#   - "isnet-general-use" : meilleure qualité générale → montages PRO (recommandé)
#   - "u2net_human_seg"   : spécialisé silhouettes humaines (très propre sur les personnes)
#   - "u2netp"            : léger ~4 Mo (rapide, bords plus grossiers) — pratique en local
# En CI le modèle est mis en cache (~/.u2net) → téléchargé une seule fois, pas à chaque run.
_REMBG_MODEL = (os.environ.get("REMBG_MODEL") or "isnet-general-use").strip()
_MODEL_URL = f"https://github.com/danielgatis/rembg/releases/download/v0.0.0/{_REMBG_MODEL}.onnx"
_session = None


def _ensure_model() -> None:
    """Garantit la présence du modèle (téléchargé via urllib, robuste vs le downloader rembg)."""
    home = os.path.expanduser(os.environ.get("U2NET_HOME") or "~/.u2net")
    os.makedirs(home, exist_ok=True)
    dest = os.path.join(home, f"{_REMBG_MODEL}.onnx")
    if not os.path.exists(dest) or os.path.getsize(dest) < 100_000:
        import urllib.request
        req = urllib.request.Request(_MODEL_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r:   # 300 s : modèles lourds (~178 Mo)
            open(dest, "wb").write(r.read())


def _cutout(photo_bytes: bytes) -> Image.Image | None:
    """Détoure une photo (fond transparent). None si rembg indisponible → repli bandes."""
    global _session
    try:
        from rembg import remove, new_session
        if _session is None:
            _ensure_model()
            _session = new_session(_REMBG_MODEL)
        return Image.open(io.BytesIO(remove(photo_bytes, session=_session))).convert("RGBA")
    except Exception as e:
        print(f"[MONTAGE] détourage indisponible ({type(e).__name__}: {e})")
        return None


def make_montage_image(article: dict, people: list[dict],
                       badge: str | None = None) -> bytes:
    """
    Montage PRO : silhouettes détourées sur fond design (glow + ombres), layout
    adaptatif. Si rembg indisponible → repli automatique sur le montage en bandes.
    people : liste de {name, label, photo_bytes} (2 à 4 personnes).
    """
    people = [p for p in people if p.get("photo_bytes")][:4]
    cutouts = []
    for p in people:
        c = _cutout(p["photo_bytes"])
        if c is None:
            return _make_strips(article, people, badge)   # rembg KO → repli
        cutouts.append((p, c))
    if not cutouts:
        return _make_strips(article, people, badge)
    try:
        return _make_pro(article, cutouts, badge)
    except Exception as e:
        print(f"[MONTAGE] rendu pro échec ({type(e).__name__}: {e}) → bandes")
        return _make_strips(article, people, badge)


def _make_pro(article: dict, cutouts: list, badge: str | None) -> bytes:
    """Montage pro : découpes sur fond dégradé HK + glow catégorie + ombres portées."""
    brand.ensure_fonts()
    cat = _CAT_COLORS.get(article.get("category", "tech"), _MUSTARD)
    n = len(cutouts)

    # Fond dégradé sombre
    img = Image.new("RGB", (SIZE, SIZE), (14, 16, 24))
    dd = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / SIZE
        dd.line([(0, y), (SIZE, y)],
                fill=(int(14 + 16 * t), int(16 + 18 * t), int(24 + 26 * t)))
    img = img.convert("RGBA")

    PH = 662 if n <= 2 else 566
    base_y = 706
    overlap = 0.10 if n <= 2 else 0.16
    MAXW = SIZE - 56                       # le groupe doit tenir dans le cadre

    def _layout(ph_h):
        sz = [max(1, int(ph_h * ph.width / ph.height)) for _, ph in cutouts]
        lf, cur = [], 0
        for i, w in enumerate(sz):
            lf.append(cur)
            if i < n - 1:
                cur += w - int(min(w, sz[i + 1]) * overlap)
        return sz, lf, cur + sz[-1]

    # Positionnement avec CHEVAUCHEMENT → un seul groupe soudé ("casting" de poster)
    # plutôt que des visages isolés. Si trop large (portraits larges), on réduit la hauteur.
    sizes, lefts, total = _layout(PH)
    if total > MAXW:
        PH = int(PH * MAXW / total)
        sizes, lefts, total = _layout(PH)
    top_y = base_y - PH
    shift = (SIZE - total) // 2
    lefts = [x + shift for x in lefts]
    xs = [lefts[i] + sizes[i] // 2 for i in range(n)]
    gcx = sum(xs) // n

    # 1) UNE seule lumière d'ambiance derrière tout le groupe (couleur catégorie)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([gcx - 380, top_y - 30, gcx + 380, top_y + 540],
                                 fill=(*cat, 78))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(130)))

    # 2) Ombre au sol COMMUNE → les figures reposent sur le même plan
    floor = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(floor).ellipse([lefts[0] - 30, base_y - 58,
                                   lefts[-1] + sizes[-1] + 30, base_y + 44], fill=(0, 0, 0, 160))
    img.alpha_composite(floor.filter(ImageFilter.GaussianBlur(42)))

    # 3) Figures du BORD vers le CENTRE (le centre passe devant → cohésion de groupe).
    #    Halo sombre derrière chaque silhouette = sépare les figures qui se chevauchent.
    for i in sorted(range(n), key=lambda k: -abs(k - (n - 1) / 2)):
        p, ph = cutouts[i]
        ph2 = ph.resize((sizes[i], PH), Image.LANCZOS)
        x = lefts[i]
        sep = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        sep.paste(Image.new("RGBA", ph2.size, (0, 0, 0, 205)), (x, top_y + 6), ph2.split()[3])
        img.alpha_composite(sep.filter(ImageFilter.GaussianBlur(20)))
        img.alpha_composite(ph2, (x, top_y))

    # Dégradé sombre bas (lisibilité titre + étiquettes)
    grad = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    g0 = 380
    for yy in range(g0, SIZE):
        gd.line([(0, yy), (SIZE, yy)],
                fill=(10, 11, 17, int(255 * ((yy - g0) / (SIZE - g0)) ** 1.4)))
    img.alpha_composite(grad)
    draw = ImageDraw.Draw(img, "RGBA")

    # Étiquettes nom/société sous chaque visage (ombre portée pour la lisibilité)
    f_nm = _pil_font("Anton-Regular.ttf", 30)
    f_org = _pil_font("Barlow-SemiBold.ttf", 19)
    for (p, ph), cx in zip(cutouts, xs):
        last = (p.get("name", "").split()[-1] or p.get("name", "")).upper()
        nb = f_nm.getbbox(last)
        nx = cx - (nb[2] - nb[0]) // 2
        draw.text((nx + 2, 616), last, font=f_nm, fill=(0, 0, 0, 190))
        draw.text((nx, 614), last, font=f_nm, fill=_WHITE)
        org = p.get("label", "")
        if org:
            ob = f_org.getbbox(org)
            draw.text((cx - (ob[2] - ob[0]) // 2, 652), org, font=f_org, fill=_MUSTARD)

    # Cadre + badges + HK
    draw.rectangle([8, 8, SIZE - 8, SIZE - 8], outline=(*_MUSTARD, 230), width=16)
    f_badge = _pil_font("Barlow-SemiBold.ttf", 26)
    f_hk = _pil_font("Anton-Regular.ttf", 36)
    cat_label = brand.CATEGORY_LABELS.get(article.get("category", "tech"),
                                          (article.get("category") or "TECH").upper())
    by2 = _draw_badge(draw, cat_label, 48, 48, cat, f_badge)
    if badge:
        _draw_badge(draw, badge, 48, by2 + 10, _RED, f_badge)
    draw.ellipse([SIZE - 108, 34, SIZE - 28, 114], fill=_MUSTARD)
    hb = f_hk.getbbox("HK")
    draw.text((SIZE - 68 - (hb[2] - hb[0]) // 2, 74 - (hb[3] - hb[1]) // 2 - hb[1]),
              "HK", font=f_hk, fill=_BLACK)

    # Titre (chiffres jaunes)
    import textwrap
    title = (article.get("title_fr") or article.get("title", "")).upper()
    for fs, ww in [(70, 20), (60, 23), (52, 26), (46, 30)]:
        lines = textwrap.wrap(title, ww)
        lh = int(fs * 1.06)
        if len(lines) * lh <= 250:
            break
    f_t = _pil_font("Anton-Regular.ttf", fs)
    top = (SIZE - 104) - len(lines) * lh
    for i, ln in enumerate(lines):
        _draw_multicolor_line(draw, _split_segments(ln), 48, top + i * lh, f_t, f_t)

    # Footer
    sy = SIZE - 92
    draw.line([(48, sy), (SIZE - 48, sy)], fill=(*_MUSTARD, 180), width=2)
    f_f = _pil_font("Barlow-SemiBold.ttf", 24)
    draw.text((48, sy + 14), "DÉCRYPTAGE EN DESCRIPTION", font=f_f, fill=(*_MUSTARD, 210))
    hh = f_f.getbbox("@HK.MÉDIA")
    draw.text((SIZE - 48 - (hh[2] - hh[0]), sy + 14), "@HK.MÉDIA", font=f_f, fill=(*_WHITE, 160))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def _make_strips(article: dict, people: list[dict],
                 badge: str | None = None) -> bytes:
    """REPLI : montage en bandes côte à côte (si le détourage rembg est indisponible)."""
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
