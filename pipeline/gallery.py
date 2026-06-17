"""
Génère une planche-contact de toutes les variantes de design (validation).
Sortie : gallery_instagram.png (carré) + gallery_landscape.png (X/LinkedIn).
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

import brand as B
import dataviz

B.ensure_fonts()
LBL = ImageFont.truetype(os.path.join(B.FONT_DIR, "Barlow-SemiBold.ttf"), 22)


def render(article, network="instagram"):
    return Image.open(io.BytesIO(dataviz.generate_image(article, network))).convert("RGB")


# ── Variantes ────────────────────────────────────────────────────────────────
VARIANTS = [
    # KPI — 1, 2, 3 cartes / gros nombres / avec ou sans évolution
    ("KPI · 3 cartes + évol.", {
        "title_fr": "L'inflation ralentit à 3,2 % en zone euro", "subtitle_fr": "Données mensuelles · BCE",
        "source": "Reuters", "category": "finance", "chart_type": "kpi",
        "chart_data": [{"label": "Inflation", "value": "3.2", "unit": "%", "evolution": "-0.4"},
                       {"label": "Taux directeur", "value": "4.0", "unit": "%", "evolution": "0"},
                       {"label": "Chômage", "value": "6.5", "unit": "%", "evolution": "-0.1"}]}),
    ("KPI · 2 cartes (Md/M€)", {
        "title_fr": "Résultats annuels record pour le groupe", "subtitle_fr": "Exercice 2025",
        "source": "AMF", "category": "finance", "chart_type": "kpi",
        "chart_data": [{"label": "Chiffre d'affaires", "value": "2400000000", "unit": "€", "evolution": "12.5"},
                       {"label": "Bénéfice net", "value": "320000000", "unit": "€", "evolution": "8.2"}]}),
    ("KPI · 1 carte géante", {
        "title_fr": "Nouveau record de transferts cet été", "subtitle_fr": "Mercato · Ligue 1",
        "source": "L'Équipe", "category": "sport", "chart_type": "kpi",
        "chart_data": [{"label": "Dépenses totales", "value": "1200000000", "unit": "€", "evolution": "34.0"}]}),
    ("KPI · 3 cartes sans évol.", {
        "title_fr": "Le bilan chiffré du sommet climatique", "subtitle_fr": "COP · Engagements",
        "source": "AFP", "category": "general", "chart_type": "kpi",
        "chart_data": [{"label": "Pays signataires", "value": "40", "unit": "", "evolution": ""},
                       {"label": "Fonds engagés", "value": "100000000000", "unit": "$", "evolution": ""},
                       {"label": "Objectif 2035", "value": "55", "unit": "%", "evolution": ""}]}),

    # DONUT — 2 à 6 segments
    ("Donut · 2 segments", {
        "title_fr": "Pour ou contre la réforme", "subtitle_fr": "Sondage national",
        "source": "Ifop", "category": "general", "chart_type": "donut",
        "chart_data": [{"label": "Pour", "value": 54}, {"label": "Contre", "value": 46}]}),
    ("Donut · 3 segments", {
        "title_fr": "Répartition du budget de l'État", "subtitle_fr": "Loi de finances 2026",
        "source": "Bercy", "category": "finance", "chart_type": "donut",
        "chart_data": [{"label": "Social", "value": 45}, {"label": "Régalien", "value": 30},
                       {"label": "Autres", "value": 25}]}),
    ("Donut · 4 segments", {
        "title_fr": "Répartition du marché des smartphones", "subtitle_fr": "Parts de marché T2 2026",
        "source": "Counterpoint", "category": "tech", "chart_type": "donut",
        "chart_data": [{"label": "Apple", "value": 28}, {"label": "Samsung", "value": 22},
                       {"label": "Xiaomi", "value": 14}, {"label": "Autres", "value": 36}]}),
    ("Donut · 6 segments", {
        "title_fr": "Mix énergétique français", "subtitle_fr": "Production électrique",
        "source": "RTE", "category": "general", "chart_type": "donut",
        "chart_data": [{"label": "Nucléaire", "value": 65}, {"label": "Hydraulique", "value": 11},
                       {"label": "Éolien", "value": 9}, {"label": "Solaire", "value": 5},
                       {"label": "Gaz", "value": 6}, {"label": "Autres", "value": 4}]}),

    # BAR — 2 à 5 barres / grandes valeurs
    ("Barres · 3", {
        "title_fr": "Podium des médailles olympiques", "subtitle_fr": "Classement final",
        "source": "CIO", "category": "sport", "chart_type": "bar",
        "chart_data": [{"label": "États-Unis", "value": 40}, {"label": "Chine", "value": 38},
                       {"label": "France", "value": 26}]}),
    ("Barres · 4", {
        "title_fr": "Les plus grosses levées de fonds tech", "subtitle_fr": "En milliards de dollars",
        "source": "Crunchbase", "category": "tech", "chart_type": "bar",
        "chart_data": [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25},
                       {"label": "xAI", "value": 18}, {"label": "Mistral", "value": 6}]}),
    ("Barres · 5", {
        "title_fr": "Les langages les plus utilisés", "subtitle_fr": "Enquête développeurs 2026",
        "source": "Stack Overflow", "category": "tech", "chart_type": "bar",
        "chart_data": [{"label": "JavaScript", "value": 62}, {"label": "Python", "value": 58},
                       {"label": "TypeScript", "value": 44}, {"label": "Java", "value": 30},
                       {"label": "Rust", "value": 22}]}),

    # COURBE — court, long, descendant
    ("Courbe · 6 points", {
        "title_fr": "Évolution du Bitcoin sur 6 mois", "subtitle_fr": "Prix en milliers de dollars",
        "source": "CoinDesk", "category": "finance", "chart_type": "courbe",
        "chart_data": [{"label": "Jan", "value": 92}, {"label": "Fév", "value": 88},
                       {"label": "Mar", "value": 95}, {"label": "Avr", "value": 102},
                       {"label": "Mai", "value": 98}, {"label": "Juin", "value": 105}]}),
    ("Courbe · descendante", {
        "title_fr": "Recul du chômage sur l'année", "subtitle_fr": "Taux en %",
        "source": "INSEE", "category": "finance", "chart_type": "courbe",
        "chart_data": [{"label": "T1", "value": 7.5}, {"label": "T2", "value": 7.2},
                       {"label": "T3", "value": 6.9}, {"label": "T4", "value": 6.5}]}),

    # INFOGRAPHIE — 2 à 4 points
    ("Infographie · 4 points", {
        "title_fr": "Sommet sur le climat : les annonces clés", "subtitle_fr": "COP · Décisions du jour",
        "source": "AFP", "category": "general", "chart_type": "infographic",
        "key_points": ["Fin des subventions au charbon d'ici 2030",
                       "Fonds de 100 Md$ pour les pays du Sud",
                       "Objectif -55 % d'émissions en 2035",
                       "40 pays signataires de l'accord"]}),
    ("Infographie · 2 points", {
        "title_fr": "Ce qu'il faut retenir de la décision", "subtitle_fr": "Vérification",
        "source": "AFP Factuel", "category": "factcheck", "chart_type": "infographic",
        "key_points": ["L'information virale est partiellement fausse",
                       "Le chiffre réel est 3 fois inférieur"]}),
]


def montage(items, network, cols, path, thumb_w=360):
    thumbs = [(lbl, render(art, network)) for lbl, art in items]
    w, h = thumbs[0][1].size
    scale = thumb_w / w
    tw, th = int(w * scale), int(h * scale)
    cap, pad = 36, 18
    rows = (len(thumbs) + cols - 1) // cols
    W = cols * tw + (cols + 1) * pad
    H = rows * (th + cap) + (rows + 1) * pad
    canvas = Image.new("RGB", (W, H), (236, 228, 207))
    draw = ImageDraw.Draw(canvas)
    for i, (lbl, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + cap + pad)
        canvas.paste(im.resize((tw, th)), (x, y))
        draw.text((x + 2, y + th + 7), lbl, fill=(28, 26, 21), font=LBL)
    canvas.save(path)
    print(f"[OK] {path} ({len(thumbs)} variantes, {cols}x{rows})")


if __name__ == "__main__":
    # Tout est en carré 1080x1080 (universel 3 réseaux)
    montage(VARIANTS, "instagram", 4, "gallery_instagram.png")
    # Gros plan : 4 designs phares en grand pour validation fine
    focus = [VARIANTS[0], VARIANTS[6], VARIANTS[9], VARIANTS[11]]
    montage(focus, "instagram", 2, "gallery_focus.png", thumb_w=480)
