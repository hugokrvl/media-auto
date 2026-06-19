"""
Rendu PIL du post « Clôture des marchés » — 1080x1080, charte HK Média.
Réutilise la charte commune des posts sport (fond ardoise, en-tête léger, footer).
Indices groupés par zone, valeur de clôture + variation du jour (vert/rouge).
"""

import io
import os
import sys

# Réutilise la charte commune (fond, en-tête, footer, polices, helpers)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sports"))
from scores_renderer import (  # noqa: E402
    SIZE, _bg, _header, _footer, _font, _tw, _th,
    _CREAM, _MUSTARD, _GRAY, _WHITE, _CARD,
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
