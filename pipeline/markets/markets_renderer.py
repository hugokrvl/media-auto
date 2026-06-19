"""
Rendus PIL des posts « marchés » — 1080x1080, charte HK Média.
Réutilise la charte commune des posts sport (fond ardoise, en-tête léger, footer).

3 types :
- make_markets_post   : clôture des indices groupés par zone (variation vert/rouge)
- make_movers_post    : Top / Flop des actions mondiales (du jour ou de la semaine)
- make_sentiment_post : sentiment marché — VIX (bourse) + Fear & Greed (crypto)
"""

import io
import os
import sys

# Réutilise la charte commune (fond, en-tête, footer, polices, helpers)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sports"))
from scores_renderer import (  # noqa: E402
    SIZE, _bg, _header, _footer, _font, _tw, _th,
    _CREAM, _MUSTARD, _GRAY, _WHITE, _CARD, _BG_TOP, _BG_BOT,
)
from PIL import ImageDraw  # noqa: E402

_UP    = (52, 199, 123)    # vert hausse
_DOWN  = (235, 83, 83)     # rouge baisse
_FLAT  = (150, 158, 178)   # gris stable
_MKT   = (32, 120, 90)     # accent vert "finance" pour l'en-tête


def _fmt_value(v: float, decimals: int, prefix: str = "") -> str:
    """Format français : 7 500,58 — séparateur de milliers = espace."""
    s = f"{v:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{prefix}{s}"


def _fmt_change(chg: float) -> str:
    return f"{chg:+.2f}".replace(".", ",") + " %"


def _triangle(draw, cx, cy, color, up=True, r=6):
    if up:
        draw.polygon([(cx - r, cy + r - 1), (cx + r, cy + r - 1), (cx, cy - r)], fill=color)
    else:
        draw.polygon([(cx - r, cy - r + 1), (cx + r, cy - r + 1), (cx, cy + r)], fill=color)


def make_markets_post(rows: list[dict], date_label: str) -> bytes:
    """
    rows : liste de dicts {section, name, value, change, decimals, prefix}.
           value/change peuvent être None (données indisponibles → tiret).
    date_label : ex. "Jeudi 19 juin 2026".
    """
    import brand
    brand.ensure_fonts()

    img  = _bg(SIZE)
    draw = ImageDraw.Draw(img, "RGBA")

    PAD   = 48
    BOT_H = 56

    body_top = _header(img, draw, "Clôture des marchés", date_label, _MKT)

    f_sec   = _font("Barlow-SemiBold.ttf", 18)
    f_name  = _font("Barlow-SemiBold.ttf", 26)
    f_val   = _font("Anton-Regular.ttf",   30)
    f_chg   = _font("Barlow-SemiBold.ttf", 24)

    # Regroupe en conservant l'ordre des sections
    sections: list[str] = []
    for r in rows:
        if r["section"] not in sections:
            sections.append(r["section"])

    # Hauteurs
    SEC_H  = 34           # bandeau label de section
    ROW_H  = 56           # ligne d'un indice
    SEC_GAP = 8
    n_rows = len(rows)
    n_sec  = len(sections)
    total  = n_sec * SEC_H + n_rows * ROW_H + (n_sec - 1) * SEC_GAP
    avail  = (SIZE - BOT_H) - body_top
    y      = body_top + max(8, (avail - total) // 2)

    # Colonnes : nom à gauche | valeur (droite) | variation (extrême droite)
    chg_right = SIZE - PAD - 4
    val_right = chg_right - 168     # bord droit de la colonne valeur

    for si, sec in enumerate(sections):
        if si > 0:
            y += SEC_GAP
        # Label de section
        draw.text((PAD, y + (SEC_H - _th(f_sec, "A")) // 2 - 2), sec.upper(),
                  font=f_sec, fill=(*_MUSTARD, 220))
        # petite ligne à droite du label
        lx = PAD + _tw(f_sec, sec.upper()) + 16
        draw.line([(lx, y + SEC_H // 2), (SIZE - PAD, y + SEC_H // 2)],
                  fill=(*_GRAY, 60), width=1)
        y += SEC_H

        for r in [x for x in rows if x["section"] == sec]:
            cy = y + ROW_H // 2
            # Carte de fond légère
            draw.rounded_rectangle([PAD, y + 3, SIZE - PAD, y + ROW_H - 3],
                                   radius=10, fill=_CARD)

            # Nom
            nh = _th(f_name, r["name"])
            draw.text((PAD + 18, cy - nh // 2 - f_name.getbbox(r["name"])[1]),
                      r["name"], font=f_name, fill=_CREAM)

            val = r.get("value")
            chg = r.get("change")

            # Valeur de clôture (alignée à droite sur val_right)
            if val is not None:
                vtxt = _fmt_value(val, r.get("decimals", 2), r.get("prefix", ""))
                vh   = _th(f_val, vtxt)
                draw.text((val_right - _tw(f_val, vtxt),
                           cy - vh // 2 - f_val.getbbox(vtxt)[1]),
                          vtxt, font=f_val, fill=_CREAM)
            else:
                draw.text((val_right - _tw(f_val, "—"), cy - 14), "—",
                          font=f_val, fill=_GRAY)

            # Variation (couleur + triangle), alignée à droite sur chg_right
            if chg is not None:
                color = _UP if chg > 0.01 else (_DOWN if chg < -0.01 else _FLAT)
                ctxt  = _fmt_change(chg)
                cw    = _tw(f_chg, ctxt)
                ch    = _th(f_chg, ctxt)
                tx    = chg_right - cw
                draw.text((tx, cy - ch // 2 - f_chg.getbbox(ctxt)[1]),
                          ctxt, font=f_chg, fill=color)
                # triangle juste à gauche du texte
                if chg > 0.01:
                    _triangle(draw, tx - 16, cy, color, up=True)
                elif chg < -0.01:
                    _triangle(draw, tx - 16, cy, color, up=False)
                else:
                    draw.line([(tx - 22, cy), (tx - 10, cy)], fill=color, width=3)
            else:
                draw.text((chg_right - _tw(f_chg, "n/d"), cy - 12), "n/d",
                          font=f_chg, fill=_GRAY)

            y += ROW_H

    _footer(draw, "CLÔTURE DU JOUR")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


_CCY = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "HKD": "HK$",
        "CNY": "¥", "KRW": "₩", "DKK": "kr", "CHF": "CHF"}


def _trunc(font, txt, max_w):
    while _tw(font, txt) > max_w and len(txt) > 3:
        txt = txt[:-2].rstrip() + "."
    return txt


def make_movers_post(gainers: list[dict], losers: list[dict],
                     title: str, subtitle: str) -> bytes:
    """
    Top / Flop des actions mondiales.
    gainers / losers : listes de {name, price, change, currency, decimals}.
    title : ex. "Top / Flop du jour" — subtitle : libellé de date.
    """
    import brand
    brand.ensure_fonts()

    img  = _bg(SIZE)
    draw = ImageDraw.Draw(img, "RGBA")

    PAD   = 48
    BOT_H = 56
    body_top = _header(img, draw, title, subtitle, _MKT)

    f_sec   = _font("Barlow-SemiBold.ttf", 20)
    f_name  = _font("Barlow-SemiBold.ttf", 26)
    f_price = _font("Barlow-SemiBold.ttf", 19)
    f_chg   = _font("Anton-Regular.ttf",   30)

    groups = [("PLUS FORTES HAUSSES", _UP, gainers, True),
              ("PLUS FORTES BAISSES", _DOWN, losers, False)]

    ROW_H, SEC_H, SEC_GAP = 58, 42, 12
    n_rows = len(gainers) + len(losers)
    total  = 2 * SEC_H + n_rows * ROW_H + SEC_GAP
    avail  = (SIZE - BOT_H) - body_top
    y      = body_top + max(6, (avail - total) // 2)

    chg_right   = SIZE - PAD - 8
    price_right = chg_right - 150     # bord droit colonne prix

    for gi, (label, color, rows, up) in enumerate(groups):
        if gi > 0:
            y += SEC_GAP
        # En-tête de section : triangle + label coloré
        _triangle(draw, PAD + 9, y + SEC_H // 2, color, up=up, r=8)
        draw.text((PAD + 28, y + (SEC_H - _th(f_sec, "A")) // 2 - 2),
                  label, font=f_sec, fill=color)
        ll = PAD + 28 + _tw(f_sec, label) + 16
        draw.line([(ll, y + SEC_H // 2), (SIZE - PAD, y + SEC_H // 2)],
                  fill=(*_GRAY, 50), width=1)
        y += SEC_H

        for r in rows:
            cy = y + ROW_H // 2
            draw.rounded_rectangle([PAD, y + 3, SIZE - PAD, y + ROW_H - 3],
                                   radius=10, fill=_CARD)

            # Variation (extrême droite, gros, coloré) + triangle
            ctxt = _fmt_change(r["change"])
            cw   = _tw(f_chg, ctxt)
            ch   = _th(f_chg, ctxt)
            tx   = chg_right - cw
            draw.text((tx, cy - ch // 2 - f_chg.getbbox(ctxt)[1]),
                      ctxt, font=f_chg, fill=color)
            _triangle(draw, tx - 18, cy, color, up=up)

            # Prix + devise (colonne droite, gris)
            if r.get("price") is not None:
                sym  = _CCY.get(r.get("currency", ""), r.get("currency", ""))
                ptxt = _fmt_value(r["price"], r.get("decimals", 2)) + (f" {sym}" if sym else "")
                pw   = _tw(f_price, ptxt)
                px   = price_right - pw
                draw.text((px, cy - _th(f_price, ptxt) // 2 - f_price.getbbox(ptxt)[1]),
                          ptxt, font=f_price, fill=_GRAY)
            else:
                px = price_right

            # Nom (gauche, tronqué pour ne pas toucher le prix)
            name_max = (px - 24) - (PAD + 18)
            nm = _trunc(f_name, r["name"], name_max)
            draw.text((PAD + 18, cy - _th(f_name, nm) // 2 - f_name.getbbox(nm)[1]),
                      nm, font=f_name, fill=_CREAM)

            y += ROW_H

    _footer(draw, "MSCI WORLD · USD")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _gauge(draw, x, y, w, h, frac, zones, marker=_WHITE):
    """Barre jauge segmentée. zones = [(frac_debut, frac_fin, couleur)]. frac = position du curseur."""
    # Segments colorés
    for z0, z1, col in zones:
        draw.rounded_rectangle([x + int(w * z0), y, x + int(w * z1), y + h],
                               radius=h // 2, fill=col)
    # Curseur (trait blanc + pastille)
    mx = x + int(w * max(0.0, min(1.0, frac)))
    draw.line([(mx, y - 8), (mx, y + h + 8)], fill=marker, width=4)
    draw.ellipse([mx - 9, y + h // 2 - 9, mx + 9, y + h // 2 + 9], fill=marker)


def make_sentiment_post(bourse: dict, crypto: dict, subtitle: str) -> bytes:
    """
    Post sentiment marché.
    bourse : {value, label, color, frac, zones, hint}  (VIX)
    crypto : {value, label, color, frac, zones, hint}  (Fear & Greed)
    """
    import brand
    brand.ensure_fonts()

    img  = _bg(SIZE)
    draw = ImageDraw.Draw(img, "RGBA")

    PAD   = 48
    BOT_H = 56
    body_top = _header(img, draw, "Sentiment des marchés", subtitle, _MKT)

    f_panel = _font("Anton-Regular.ttf",   34)
    f_big   = _font("Anton-Regular.ttf",   96)
    f_label = _font("Anton-Regular.ttf",   40)
    f_hint  = _font("Barlow-SemiBold.ttf", 21)
    f_scale = _font("Barlow-SemiBold.ttf", 16)

    avail   = (SIZE - BOT_H) - body_top
    GAP     = 28
    panel_h = (avail - GAP) // 2
    px0, px1 = PAD, SIZE - PAD

    for pi, (heading, d, lo_txt, hi_txt) in enumerate([
        ("BOURSE · VIX", bourse, "Calme", "Panique"),
        ("CRYPTO · FEAR & GREED", crypto, "Peur extrême", "Avidité extrême"),
    ]):
        py = body_top + pi * (panel_h + GAP) + (6 if pi == 0 else 0)
        # Carte panneau
        draw.rounded_rectangle([px0, py, px1, py + panel_h], radius=18, fill=_CARD)
        # Barre d'accent gauche (couleur du sentiment)
        draw.rounded_rectangle([px0, py, px0 + 7, py + panel_h], radius=4, fill=d["color"])

        inner = px0 + 36
        # Titre du panneau
        draw.text((inner, py + 22), heading, font=f_panel, fill=_CREAM)

        # Grande valeur + label coloré
        val_txt = d["value"]
        draw.text((inner, py + 64), val_txt, font=f_big, fill=d["color"])
        vb = f_big.getbbox(val_txt)
        draw.text((inner + (vb[2] - vb[0]) + 28, py + 104),
                  d["label"].upper(), font=f_label, fill=d["color"])

        # Jauge
        gx = inner
        gw = (px1 - 36) - inner
        gy = py + panel_h - 70
        _gauge(draw, gx, gy, gw, 20, d["frac"], d["zones"])
        # Bornes de l'échelle
        draw.text((gx, gy + 30), lo_txt, font=f_scale, fill=_GRAY)
        draw.text((gx + gw - _tw(f_scale, hi_txt), gy + 30), hi_txt, font=f_scale, fill=_GRAY)

        # Phrase d'explication
        draw.text((inner, py + panel_h - 132), d["hint"], font=f_hint, fill=_GRAY)

    _footer(draw, "BAROMÈTRE HEBDO")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
