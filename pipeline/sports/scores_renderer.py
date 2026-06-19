"""
Rendu PIL des posts résultats sportifs — 1080x1080, charte HK Média.

Design : fond sombre, header championnat couleur, grille matchs logos + scores.
"""

import io
import os
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import brand

SIZE     = 1080
FONT_DIR = brand.FONT_DIR

_BG      = (14, 14, 18)
_CARD    = (28, 28, 36)
_CREAM   = (245, 237, 218)
_MUSTARD = (226, 165, 15)
_GRAY    = (110, 110, 120)
_WHITE   = (255, 255, 255)
_WIN     = (226, 165, 15)
_DRAW    = (180, 180, 180)
_LOSE    = (80, 80, 90)

# Couleurs podium F1 (sans emojis)
_GOLD   = (212, 175, 55)
_SILVER = (170, 170, 175)
_BRONZE = (160, 100, 50)


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, filename)
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()


def _download_logo(url: str, size: int = 60) -> Image.Image | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            img = Image.open(io.BytesIO(r.read())).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ox = (size - img.width) // 2
        oy = (size - img.height) // 2
        result.paste(img, (ox, oy), img)
        return result
    except Exception:
        return None


def _draw_country_pill(draw: ImageDraw.ImageDraw, text: str, color: tuple,
                        x: int, y: int, font: ImageFont.FreeTypeFont) -> None:
    """Remplace les emojis drapeaux par une pill colorée avec le code pays."""
    bb = font.getbbox(text)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    px, py = 12, 5
    draw.rounded_rectangle([x, y, x + tw + px*2, y + th + py*2], radius=5, fill=color)
    draw.text((x + px, y + py - bb[1]), text, font=font, fill=_WHITE)


def make_football_scores(fixtures: list[dict], league: dict) -> bytes:
    """
    Génère un post résultats 1080x1080.
    fixtures : matchs formatés (teams home/away name+logo, goals home/away, fixture status)
    league   : dict de leagues.py (name, country, color, flag=code texte)
    """
    brand.ensure_fonts()

    img = Image.new("RGB", (SIZE, SIZE), _BG)
    draw = ImageDraw.Draw(img, "RGBA")

    f_champ   = _font("Anton-Regular.ttf",    44)
    f_country = _font("Barlow-SemiBold.ttf",  24)
    f_code    = _font("Barlow-SemiBold.ttf",  20)
    f_team    = _font("Barlow-SemiBold.ttf",  26)
    f_score   = _font("Anton-Regular.ttf",    54)
    f_footer  = _font("Barlow-SemiBold.ttf",  22)
    f_hk      = _font("Anton-Regular.ttf",    30)

    margin   = 48
    header_h = 128
    footer_h = 54
    brd      = 14

    # Cadre jaune
    draw.rectangle([brd//2, brd//2, SIZE-brd//2, SIZE-brd//2],
                   outline=(*_MUSTARD, 200), width=brd)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_color = league.get("color", (40, 40, 50))
    draw.rectangle([0, 0, SIZE, header_h], fill=hdr_color)
    draw.rectangle([0, 0, SIZE, header_h], fill=(0, 0, 0, 90))

    # Pill pays (remplace emoji drapeau)
    country_code = league.get("country", "")[:3].upper()
    pill_color   = tuple(max(0, c - 40) for c in hdr_color[:3])
    _draw_country_pill(draw, country_code, pill_color, margin, 30, f_code)

    champ_x = margin
    draw.text((champ_x, 54), league["name"].upper(), font=f_champ, fill=_WHITE)
    draw.text((champ_x, 100), f"Résultats · {league.get('country', '')}", font=f_country,
              fill=(*_WHITE, 170))

    # Monogramme HK
    hk_r = 34
    hk_cx, hk_cy = SIZE - 68, header_h // 2
    draw.ellipse([hk_cx-hk_r, hk_cy-hk_r, hk_cx+hk_r, hk_cy+hk_r], fill=_MUSTARD)
    hk_bb = f_hk.getbbox("HK")
    draw.text((hk_cx-(hk_bb[2]-hk_bb[0])//2, hk_cy-(hk_bb[3]-hk_bb[1])//2-hk_bb[1]),
              "HK", font=f_hk, fill=_BG)

    # ── Calcul disposition cartes — centrage vertical ─────────────────────────
    card_gap  = 12
    available = SIZE - header_h - footer_h - 32   # zone utile
    n         = len(fixtures)
    card_h    = min(100, max(60, (available - card_gap * (n - 1)) // max(n, 1)))
    logo_size = max(36, card_h - 26)

    total_content = n * card_h + (n - 1) * card_gap
    y_start = header_h + (available - total_content) // 2 + 16

    # ── Cartes matchs ─────────────────────────────────────────────────────────
    for i, fix in enumerate(fixtures):
        home   = fix.get("teams", {}).get("home", {})
        away   = fix.get("teams", {}).get("away", {})
        goals  = fix.get("goals", {})
        g_home = goals.get("home")
        g_away = goals.get("away")

        y        = y_start + i * (card_h + card_gap)
        cx1, cx2 = margin, SIZE - margin
        draw.rounded_rectangle([cx1, y, cx2, y + card_h], radius=10, fill=_CARD)

        logo_y   = y + (card_h - logo_size) // 2
        name_pad = logo_size + 20

        # Logos
        logo_h = _download_logo(home.get("logo", ""), logo_size)
        logo_a = _download_logo(away.get("logo", ""), logo_size)
        if logo_h:
            img.paste(logo_h, (cx1 + 14, logo_y), logo_h)
        if logo_a:
            img.paste(logo_a, (cx2 - 14 - logo_size, logo_y), logo_a)

        # Noms (tronqués)
        h_name = home.get("name", "")[:15]
        a_name = away.get("name", "")[:15]
        h_bb   = f_team.getbbox(h_name)
        a_bb   = f_team.getbbox(a_name)
        ty     = y + (card_h - (h_bb[3] - h_bb[1])) // 2 - h_bb[1]
        draw.text((cx1 + 14 + name_pad, ty), h_name, font=f_team, fill=_CREAM)
        draw.text((cx2 - 14 - logo_size - (a_bb[2]-a_bb[0]), ty), a_name, font=f_team, fill=_CREAM)

        # Score centré
        if g_home is not None and g_away is not None:
            if g_home > g_away:
                c_score = _WIN
            elif g_away > g_home:
                c_score = _LOSE
            else:
                c_score = _DRAW
            score_txt = f"{g_home}  –  {g_away}"
            sb = f_score.getbbox(score_txt)
            sx = (SIZE - (sb[2]-sb[0])) // 2
            sy = y + (card_h - (sb[3]-sb[1])) // 2 - sb[1]
            draw.text((sx, sy), score_txt, font=f_score, fill=_CREAM)
        else:
            elapsed = fix.get("fixture", {}).get("status", {}).get("elapsed")
            live    = f"{elapsed}'" if elapsed else "–"
            lb      = f_score.getbbox(live)
            draw.text(((SIZE-(lb[2]-lb[0]))//2, y+(card_h-(lb[3]-lb[1]))//2-lb[1]),
                      live, font=f_score, fill=_GRAY)

    # ── Footer ────────────────────────────────────────────────────────────────
    sep_y = SIZE - footer_h
    draw.line([(margin, sep_y), (SIZE-margin, sep_y)], fill=(*_MUSTARD, 100), width=1)
    draw.text((margin, sep_y + 14), "RÉSULTATS DU JOUR", font=f_footer, fill=(*_MUSTARD, 200))
    hb = f_footer.getbbox("@HK.MÉDIA")
    draw.text((SIZE-margin-(hb[2]-hb[0]), sep_y+14), "@HK.MÉDIA", font=f_footer,
              fill=(*_WHITE, 130))

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def make_f1_podium(race: dict, results: list[dict]) -> bytes:
    """Post podium F1 : top 3 pilotes avec rang stylisé (sans emojis)."""
    brand.ensure_fonts()

    img  = Image.new("RGB", (SIZE, SIZE), _BG)
    draw = ImageDraw.Draw(img, "RGBA")

    f_title  = _font("Anton-Regular.ttf",   50)
    f_sub    = _font("Barlow-SemiBold.ttf", 26)
    f_rank   = _font("Anton-Regular.ttf",   96)
    f_driver = _font("Anton-Regular.ttf",   46)
    f_team   = _font("Barlow-SemiBold.ttf", 26)
    f_footer = _font("Barlow-SemiBold.ttf", 22)
    f_hk     = _font("Anton-Regular.ttf",   30)

    margin   = 48
    header_h = 128
    brd      = 14

    draw.rectangle([brd//2, brd//2, SIZE-brd//2, SIZE-brd//2],
                   outline=(*_MUSTARD, 200), width=brd)

    # Header rouge F1
    draw.rectangle([0, 0, SIZE, header_h], fill=(185, 0, 0))
    draw.rectangle([0, 0, SIZE, header_h], fill=(0, 0, 0, 70))

    race_name = race.get("competition", {}).get("name", "Grand Prix")
    draw.text((margin, 22), "FORMULA 1", font=f_title, fill=_WHITE)
    draw.text((margin, 80), race_name.upper(), font=f_sub, fill=(*_WHITE, 190))

    # Pill "F1"
    _draw_country_pill(draw, "F1", (140, 0, 0), SIZE - 140, 30, f_sub)

    # HK
    hk_r = 34
    hk_cx, hk_cy = SIZE - 68, header_h // 2
    draw.ellipse([hk_cx-hk_r, hk_cy-hk_r, hk_cx+hk_r, hk_cy+hk_r], fill=_MUSTARD)
    hk_bb = f_hk.getbbox("HK")
    draw.text((hk_cx-(hk_bb[2]-hk_bb[0])//2, hk_cy-(hk_bb[3]-hk_bb[1])//2-hk_bb[1]),
              "HK", font=f_hk, fill=_BG)

    # ── Podium ────────────────────────────────────────────────────────────────
    podium_colors = [_GOLD, _SILVER, _BRONZE]
    card_h  = 160
    card_gap = 20
    n       = min(3, len(results))
    total   = n * card_h + (n-1) * card_gap
    y_start = header_h + (SIZE - header_h - 54 - total) // 2

    for idx in range(n):
        res    = results[idx]
        color  = podium_colors[idx]
        y      = y_start + idx * (card_h + card_gap)
        driver = res.get("driver", {})
        team   = res.get("team", {})
        name   = driver.get("name", f"Pilote {idx+1}").upper()
        team_n = team.get("name", "")
        time_v = res.get("time", {}).get("time", "") or str(res.get("points", ""))

        # Fond carte avec bordure gauche colorée
        draw.rounded_rectangle([margin, y, SIZE-margin, y+card_h], radius=12, fill=_CARD)
        draw.rounded_rectangle([margin, y, margin+8, y+card_h], radius=4, fill=color)

        # Rang (grand chiffre coloré)
        rank_txt = str(idx + 1)
        rb = f_rank.getbbox(rank_txt)
        draw.text((margin + 30, y + (card_h - (rb[3]-rb[1])) // 2 - rb[1]),
                  rank_txt, font=f_rank, fill=color)

        # Nom pilote
        nb = f_driver.getbbox(name)
        draw.text((margin + 140, y + 34), name, font=f_driver, fill=_CREAM)

        # Équipe · Temps
        detail = f"{team_n}  ·  {time_v}" if time_v else team_n
        draw.text((margin + 140, y + 94), detail, font=f_team, fill=_GRAY)

    # ── Footer ────────────────────────────────────────────────────────────────
    sep_y = SIZE - 54
    draw.line([(margin, sep_y), (SIZE-margin, sep_y)], fill=(*_MUSTARD, 100), width=1)
    draw.text((margin, sep_y+14), "RÉSULTATS COURSE", font=f_footer, fill=(*_MUSTARD, 200))
    hb = f_footer.getbbox("@HK.MÉDIA")
    draw.text((SIZE-margin-(hb[2]-hb[0]), sep_y+14), "@HK.MÉDIA", font=f_footer,
              fill=(*_WHITE, 130))

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
