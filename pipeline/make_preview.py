"""
Génère un aperçu du tableau de planning (comme le matin sur le site)
avec une fournée réaliste de posts du jour. Sortie : preview_planning.png
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

import brand as B
import dataviz

B.ensure_fonts()

# Palette site (sombre)
SITE_BG = (13, 13, 13)
CARD_BG = (20, 20, 20)
BORDER = (42, 42, 42)
WHITE = (240, 240, 240)
GRAY = (140, 140, 140)
MUSTARD = (226, 165, 15)
GREEN = (74, 222, 128)

F_TITLE = ImageFont.truetype(os.path.join(B.FONT_DIR, "DMSerifDisplay-Regular.ttf"), 26)
F_CHIP = ImageFont.truetype(os.path.join(B.FONT_DIR, "Barlow-SemiBold.ttf"), 19)
F_CAP = ImageFont.truetype(os.path.join(B.FONT_DIR, "Barlow-Regular.ttf"), 20)
F_BTN = ImageFont.truetype(os.path.join(B.FONT_DIR, "Barlow-SemiBold.ttf"), 21)
F_H1 = ImageFont.truetype(os.path.join(B.FONT_DIR, "DMSerifDisplay-Regular.ttf"), 40)
F_SUB = ImageFont.truetype(os.path.join(B.FONT_DIR, "Barlow-Medium.ttf"), 22)

POSTS = [
    {"score": 9, "cat": "finance", "caption": "📉 L'inflation en zone euro recule à 3,2 %, son plus bas depuis 2021. La BCE temporise sur les taux.",
     "art": {"title_fr": "L'inflation ralentit à 3,2 % en zone euro", "subtitle_fr": "Données mensuelles · BCE",
             "source": "Reuters", "category": "finance", "chart_type": "kpi",
             "chart_data": [{"label": "Inflation", "value": "3.2", "unit": "%", "evolution": "-0.4"},
                            {"label": "Taux directeur", "value": "4.0", "unit": "%", "evolution": "0"},
                            {"label": "Chômage", "value": "6.5", "unit": "%", "evolution": "-0.1"}]}},
    {"score": 8, "cat": "tech", "caption": "🚀 Les levées de fonds dans l'IA explosent. OpenAI rafle 40 Md$, loin devant ses concurrents.",
     "art": {"title_fr": "Les plus grosses levées de fonds tech", "subtitle_fr": "En milliards de dollars",
             "source": "Crunchbase", "category": "tech", "chart_type": "bar",
             "chart_data": [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25},
                            {"label": "xAI", "value": 18}, {"label": "Mistral", "value": 6}]}},
    {"score": 8, "cat": "general", "caption": "⚡ D'où vient l'électricité française ? Le nucléaire reste largement dominant à 65 % du mix.",
     "art": {"title_fr": "Mix énergétique français", "subtitle_fr": "Production électrique",
             "source": "RTE", "category": "general", "chart_type": "donut",
             "chart_data": [{"label": "Nucléaire", "value": 65}, {"label": "Hydraulique", "value": 11},
                            {"label": "Éolien", "value": 9}, {"label": "Solaire", "value": 5},
                            {"label": "Gaz", "value": 6}, {"label": "Autres", "value": 4}]}},
    {"score": 7, "cat": "finance", "caption": "₿ Le Bitcoin franchit les 105 000 $ après six mois de hausse continue. Retour sur la tendance.",
     "art": {"title_fr": "Évolution du Bitcoin sur 6 mois", "subtitle_fr": "Prix en milliers de dollars",
             "source": "CoinDesk", "category": "finance", "chart_type": "courbe",
             "chart_data": [{"label": "Jan", "value": 92}, {"label": "Fév", "value": 88},
                            {"label": "Mar", "value": 95}, {"label": "Avr", "value": 102},
                            {"label": "Mai", "value": 98}, {"label": "Juin", "value": 105}]}},
    {"score": 9, "cat": "general", "caption": "🌍 Sommet climatique : 4 décisions majeures actées. Fin du charbon, fonds Sud, objectif 2035.",
     "art": {"title_fr": "Sommet sur le climat : les annonces clés", "subtitle_fr": "COP · Décisions du jour",
             "source": "AFP", "category": "general", "chart_type": "infographic",
             "key_points": ["Fin des subventions au charbon d'ici 2030",
                            "Fonds de 100 Md$ pour les pays du Sud",
                            "Objectif -55 % d'émissions en 2035",
                            "40 pays signataires de l'accord"]}},
    {"score": 7, "cat": "sport", "caption": "🏅 Tableau des médailles : les États-Unis devancent la Chine d'un cheveu, la France 3e.",
     "art": {"title_fr": "Podium des médailles olympiques", "subtitle_fr": "Classement final",
             "source": "CIO", "category": "sport", "chart_type": "bar",
             "chart_data": [{"label": "États-Unis", "value": 40}, {"label": "Chine", "value": 38},
                            {"label": "France", "value": 26}]}},
]

CAT_LABEL = {"finance": "FINANCE", "tech": "TECH", "general": "ACTUALITÉ", "sport": "SPORT", "factcheck": "VÉRIF"}


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(post, w):
    img = Image.open(io.BytesIO(dataviz.generate_image(post["art"], "instagram"))).convert("RGB")
    img = img.resize((w, w))
    txt_h = 250
    h = w + txt_h
    c = Image.new("RGB", (w, h), CARD_BG)
    d = ImageDraw.Draw(c)
    c.paste(img, (0, 0))
    pad = 18
    y = w + 16
    # Chips : catégorie + score
    cat = CAT_LABEL.get(post["cat"], post["cat"].upper())
    cw = int(d.textlength(cat, font=F_CHIP)) + 24
    d.rounded_rectangle([pad, y, pad + cw, y + 30], radius=15, fill=MUSTARD)
    d.text((pad + 12, y + 5), cat, font=F_CHIP, fill=(20, 20, 20))
    sc = f"★ {post['score']}/10"
    sw = int(d.textlength(sc, font=F_CHIP)) + 24
    d.rounded_rectangle([w - pad - sw, y, w - pad, y + 30], radius=15, outline=BORDER, width=2)
    d.text((w - pad - sw + 12, y + 5), sc, font=F_CHIP, fill=GREEN if post["score"] >= 8 else MUSTARD)
    y += 46
    # Titre
    for line in wrap(d, post["art"]["title_fr"], F_TITLE, w - 2 * pad)[:2]:
        d.text((pad, y), line, font=F_TITLE, fill=WHITE)
        y += 32
    y += 6
    # Caption snippet
    for line in wrap(d, post["caption"], F_CAP, w - 2 * pad)[:2]:
        d.text((pad, y), line, font=F_CAP, fill=GRAY)
        y += 26
    # Boutons
    by = h - 56
    bw = w - 2 * pad - 110
    d.rounded_rectangle([pad, by, pad + bw, by + 40], radius=10, fill=MUSTARD)
    d.text((pad + bw // 2 - 55, by + 9), "✓  Approuver", font=F_BTN, fill=(15, 15, 15))
    d.rounded_rectangle([pad + bw + 12, by, w - pad, by + 40], radius=10, outline=BORDER, width=2)
    d.text((pad + bw + 36, by + 9), "👁 Voir", font=F_BTN, fill=WHITE)
    # Bord carte
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=14, outline=BORDER, width=2)
    return c


def build():
    cols, cw, gap, margin = 3, 430, 26, 44
    cards = [card(p, cw) for p in POSTS]
    ch = cards[0].height
    rows = (len(cards) + cols - 1) // cols
    head = 130
    W = margin * 2 + cols * cw + (cols - 1) * gap
    H = head + margin + rows * ch + (rows - 1) * gap + margin
    canvas = Image.new("RGB", (W, H), SITE_BG)
    d = ImageDraw.Draw(canvas)
    # En-tête
    d.text((margin, 38), "HK", font=F_H1, fill=MUSTARD)
    d.text((margin + 70, 46), "MÉDIA · Planning", font=F_H1, fill=WHITE)
    d.text((margin, 96), "Fournée du 17 juin — 6 posts générés cette nuit · en attente de validation",
           font=F_SUB, fill=GRAY)
    d.line([margin, head - 6, W - margin, head - 6], fill=BORDER, width=1)
    for i, cc in enumerate(cards):
        r, col = divmod(i, cols)
        x = margin + col * (cw + gap)
        yy = head + margin + r * (ch + gap)
        canvas.paste(cc, (x, yy))
    canvas.save("preview_planning.png")
    print(f"[OK] preview_planning.png ({W}x{H})")


if __name__ == "__main__":
    build()
