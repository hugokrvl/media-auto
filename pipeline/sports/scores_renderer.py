"""
Rendu PIL des posts résultats sportifs — 1080x1080, charte HK Média.
Layout : fond ardoise bleuté, une ligne par match, zéro chevauchement.
Traduction FR robuste (insensible aux accents). Portrait du vainqueur pour la F1.
"""

import io
import os
import sys
import unicodedata
import urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import brand

SIZE     = 1080
FONT_DIR = brand.FONT_DIR

_BG_TOP  = (18,  22,  38)
_BG_BOT  = (24,  30,  50)
_CARD    = (30,  37,  60)
_CREAM   = (242, 236, 220)
_MUSTARD = (226, 165,  15)
_GRAY    = (140, 148, 170)
_WHITE   = (255, 255, 255)
_WIN     = (226, 165,  15)
_DRAW    = (200, 205, 220)
_LOSE    = (80,  87, 110)
_GOLD    = (212, 175,  55)
_SILVER  = (175, 180, 188)
_BRONZE  = (176, 116,  60)

# ── Traductions FR (pays ET clubs) — clés en minuscules, accents tolérés ──────
_FR_RAW: dict[str, str] = {
    # Pays
    "united states": "États-Unis", "usa": "États-Unis", "united states of america": "États-Unis",
    "australia": "Australie", "scotland": "Écosse", "morocco": "Maroc",
    "brazil": "Brésil", "haiti": "Haïti", "türkiye": "Turquie", "turkey": "Turquie",
    "turkiye": "Turquie",
    "georgia": "Géorgie", "czechia": "Tchéquie", "czech republic": "Tchéquie",
    "portugal": "Portugal", "paraguay": "Paraguay", "argentina": "Argentine",
    "france": "France", "germany": "Allemagne", "spain": "Espagne",
    "italy": "Italie", "england": "Angleterre", "netherlands": "Pays-Bas",
    "belgium": "Belgique", "switzerland": "Suisse", "croatia": "Croatie",
    "denmark": "Danemark", "sweden": "Suède", "norway": "Norvège",
    "poland": "Pologne", "ukraine": "Ukraine", "russia": "Russie",
    "japan": "Japon", "south korea": "Corée du Sud", "korea republic": "Corée du Sud",
    "iran": "Iran", "ir iran": "Iran",
    "saudi arabia": "Arabie Saoudite", "senegal": "Sénégal", "nigeria": "Nigéria",
    "cameroon": "Cameroun", "ghana": "Ghana", "egypt": "Égypte",
    "mexico": "Mexique", "canada": "Canada", "colombia": "Colombie",
    "chile": "Chili", "uruguay": "Uruguay", "ecuador": "Équateur",
    "peru": "Pérou", "venezuela": "Venezuela", "bolivia": "Bolivie",
    "serbia": "Serbie", "austria": "Autriche", "romania": "Roumanie",
    "hungary": "Hongrie", "slovakia": "Slovaquie", "slovenia": "Slovénie",
    "wales": "Pays de Galles", "ireland": "Irlande",
    "northern ireland": "Irlande du Nord", "finland": "Finlande",
    "greece": "Grèce", "albania": "Albanie",
    "north macedonia": "Macédoine du Nord", "montenegro": "Monténégro",
    "latvia": "Lettonie", "lithuania": "Lituanie", "estonia": "Estonie",
    "moldova": "Moldavie", "belarus": "Biélorussie", "iceland": "Islande",
    "new zealand": "Nouvelle-Zélande", "costa rica": "Costa Rica",
    "panama": "Panama", "honduras": "Honduras", "el salvador": "Salvador",
    "jamaica": "Jamaïque", "trinidad and tobago": "Trinité-et-Tobago",
    "algeria": "Algérie", "tunisia": "Tunisie", "mali": "Mali",
    "ivory coast": "Côte d'Ivoire", "cote divoire": "Côte d'Ivoire",
    "democratic republic of congo": "RD Congo", "dr congo": "RD Congo",
    "south africa": "Afrique du Sud", "kenya": "Kenya",
    "china": "Chine", "china pr": "Chine", "india": "Inde",
    "indonesia": "Indonésie", "thailand": "Thaïlande", "vietnam": "Viêt Nam",
    "qatar": "Qatar", "united arab emirates": "Émirats arabes unis",
    # Clubs football
    "barcelona": "Barcelone", "fc barcelona": "Barcelone",
    "atletico madrid": "Atlético Madrid", "atletico de madrid": "Atlético Madrid",
    "real madrid": "Real Madrid", "real madrid cf": "Real Madrid",
    "manchester city": "Man. City", "man city": "Man. City",
    "manchester united": "Man. United", "man utd": "Man. United",
    "chelsea": "Chelsea", "arsenal": "Arsenal",
    "tottenham hotspur": "Tottenham", "tottenham": "Tottenham",
    "liverpool": "Liverpool", "newcastle united": "Newcastle",
    "aston villa": "Aston Villa", "west ham united": "West Ham",
    "brighton & hove albion": "Brighton", "brighton": "Brighton",
    "wolverhampton wanderers": "Wolverhampton", "wolves": "Wolverhampton",
    "leicester city": "Leicester", "nottingham forest": "Nottingham",
    "brentford": "Brentford", "crystal palace": "Crystal Palace",
    "paris saint-germain": "PSG", "paris saint germain": "PSG",
    "olympique de marseille": "Marseille",
    "olympique lyonnais": "Lyon", "olympique lyon": "Lyon",
    "as monaco": "Monaco",
    "losc lille": "Lille",
    "stade rennais": "Rennes",
    "rc lens": "Lens",
    "ogc nice": "Nice",
    "toulouse fc": "Toulouse",
    "stade brestois 29": "Brest", "stade brestois": "Brest",
    "rc strasbourg alsace": "Strasbourg", "rc strasbourg": "Strasbourg",
    "fc nantes": "Nantes",
    "montpellier hsc": "Montpellier",
    "havre ac": "Le Havre", "le havre": "Le Havre", "le havre ac": "Le Havre",
    "aj auxerre": "Auxerre", "as saint-etienne": "Saint-Étienne",
    "as saint etienne": "Saint-Étienne",
    "angers sco": "Angers", "fc lorient": "Lorient",
    "bayern munich": "Bayern Munich", "fc bayern münchen": "Bayern Munich",
    "fc bayern munchen": "Bayern Munich", "bayern": "Bayern Munich",
    "borussia dortmund": "Dortmund", "bvb": "Dortmund",
    "rb leipzig": "Leipzig", "bayer leverkusen": "Leverkusen",
    "eintracht frankfurt": "Francfort", "vfb stuttgart": "Stuttgart",
    "borussia monchengladbach": "Mönchengladbach",
    "sc freiburg": "Fribourg", "1 fc union berlin": "Union Berlin",
    "union berlin": "Union Berlin",
    "fc augsburg": "Augsbourg", "werder bremen": "Brême",
    "inter": "Inter Milan", "inter milan": "Inter Milan",
    "fc internazionale milano": "Inter Milan", "internazionale": "Inter Milan",
    "ac milan": "AC Milan", "milan": "AC Milan",
    "juventus": "Juventus", "juventus fc": "Juventus",
    "napoli": "Naples", "ssc napoli": "Naples",
    "as roma": "AS Roma", "roma": "AS Roma",
    "lazio": "Lazio", "ss lazio": "Lazio",
    "atalanta": "Atalanta", "fiorentina": "Fiorentina",
    "acf fiorentina": "Fiorentina",
    "torino": "Turin", "torino fc": "Turin",
    "bologna": "Bologne", "bologna fc 1909": "Bologne",
    "sevilla": "Séville", "sevilla fc": "Séville",
    "real betis": "Betis", "real betis balompie": "Betis",
    "villarreal": "Villarreal", "villarreal cf": "Villarreal",
    "athletic bilbao": "Athletic Bilbao", "athletic club": "Athletic Bilbao",
    "real sociedad": "Real Sociedad",
    "celta vigo": "Celta Vigo", "rc celta": "Celta Vigo",
    "valencia": "Valence", "valencia cf": "Valence",
    "ca osasuna": "Osasuna", "osasuna": "Osasuna",
    "girona": "Girona", "girona fc": "Girona",
    "ajax": "Ajax", "psv": "PSV", "psv eindhoven": "PSV",
    "feyenoord": "Feyenoord", "porto": "Porto", "fc porto": "Porto",
    "benfica": "Benfica", "sl benfica": "Benfica",
    "sporting cp": "Sporting CP", "sporting": "Sporting CP",
    "celtic": "Celtic", "rangers": "Rangers",
    "shakhtar donetsk": "Shakhtar", "dynamo kyiv": "Dynamo Kiev",
    "red bull salzburg": "Salzbourg", "galatasaray": "Galatasaray",
    "club brugge": "Bruges", "club brugge kv": "Bruges",
    "rsc anderlecht": "Anderlecht", "anderlecht": "Anderlecht",
    # Basket NBA
    "los angeles lakers": "Lakers", "golden state warriors": "Warriors",
    "boston celtics": "Celtics", "miami heat": "Heat",
    "brooklyn nets": "Nets", "chicago bulls": "Bulls",
    "milwaukee bucks": "Bucks", "denver nuggets": "Nuggets",
    "phoenix suns": "Suns", "dallas mavericks": "Mavericks",
    "memphis grizzlies": "Grizzlies", "new york knicks": "Knicks",
    "cleveland cavaliers": "Cavaliers", "atlanta hawks": "Hawks",
    "philadelphia 76ers": "76ers", "toronto raptors": "Raptors",
    "oklahoma city thunder": "Thunder", "minnesota timberwolves": "Wolves",
    "sacramento kings": "Kings", "indiana pacers": "Pacers",
    "orlando magic": "Magic", "charlotte hornets": "Hornets",
    "san antonio spurs": "Spurs", "utah jazz": "Jazz",
    "portland trail blazers": "Blazers", "houston rockets": "Rockets",
    "washington wizards": "Wizards", "detroit pistons": "Pistons",
    "los angeles clippers": "Clippers", "new orleans pelicans": "Pelicans",
}


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


# Dictionnaire normalisé (clé sans accents/casse) → traduction FR.
_FR_NORM: dict[str, str] = {_strip_accents(k): v for k, v in _FR_RAW.items()}


def _fr(name: str) -> str:
    """Traduit un nom de club/pays EN → FR, insensible aux accents et à la casse.
    Ex : 'Türkiye', 'Turkiye', 'TURKEY' → 'Turquie' ; 'Barcelona' → 'Barcelone'."""
    if not name:
        return name
    return _FR_NORM.get(_strip_accents(name), name)


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, filename)
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()


def _tw(font, text: str) -> int:
    bb = font.getbbox(text)
    return bb[2] - bb[0]


def _th(font, text: str) -> int:
    bb = font.getbbox(text)
    return bb[3] - bb[1]


def _draw_center(draw, cx, cy, text, font, fill):
    bb = font.getbbox(text)
    x  = cx - (bb[2] - bb[0]) // 2 - bb[0]
    y  = cy - (bb[3] - bb[1]) // 2 - bb[1]
    draw.text((x, y), text, font=font, fill=fill)


def _draw_top(draw, x, top_y, text, font, fill):
    """Dessine un texte dont le HAUT visuel est exactement à top_y (gère le bearing)."""
    bb = font.getbbox(text)
    draw.text((x, top_y - bb[1]), text, font=font, fill=fill)
    return top_y + (bb[3] - bb[1])   # renvoie le bas visuel


def _download(url: str, timeout: int = 8, retries: int = 3) -> bytes | None:
    """Télécharge une image. Retry avec backoff sur 429 (rate-limit Wikimedia)."""
    if not url:
        return None
    import time
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None


def _logo(url: str, size: int = 68) -> Image.Image | None:
    raw = _download(url)
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
        return out
    except Exception:
        return None


def _bg(size: int) -> Image.Image:
    img  = Image.new("RGB", (size, size), _BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        r = int(_BG_TOP[0] + (_BG_BOT[0] - _BG_TOP[0]) * t)
        g = int(_BG_TOP[1] + (_BG_BOT[1] - _BG_TOP[1]) * t)
        b = int(_BG_TOP[2] + (_BG_BOT[2] - _BG_TOP[2]) * t)
        draw.line([(0, y), (size - 1, y)], fill=(r, g, b))
    return img


def _header(img, draw, title: str, subtitle: str, accent) -> int:
    """En-tête commun : titre + sous-titre sans chevauchement, monogramme HK,
    ligne séparatrice. Retourne l'ordonnée Y où commence le corps."""
    PAD   = 48
    f_t   = _font("Anton-Regular.ttf",   38)
    f_s   = _font("Barlow-SemiBold.ttf", 20)
    f_hk  = _font("Anton-Regular.ttf",   24)

    title = title.upper()
    sub   = (subtitle or "").upper()

    top_y = 28
    tb    = f_t.getbbox(title)
    title_h = tb[3] - tb[1]

    # Texte titre (réserve la place pour le monogramme HK à droite)
    title_bottom = _draw_top(draw, PAD + 18, top_y, title, f_t, _CREAM)

    by = title_bottom + 8
    if sub:
        sb = f_s.getbbox(sub)
        sub_bottom = _draw_top(draw, PAD + 18, by, sub, f_s, _GRAY)
        by = sub_bottom + 14
    else:
        by += 14

    # Accent vertical à gauche, hauteur = bloc titre+sous-titre
    draw.rectangle([PAD, top_y + 2, PAD + 5, by - 12], fill=accent)

    # Monogramme HK (centré verticalement sur le bloc titre)
    hk_r  = 28
    hk_cx = SIZE - PAD - hk_r
    hk_cy = top_y + title_h // 2 + 2
    draw.ellipse([hk_cx - hk_r, hk_cy - hk_r, hk_cx + hk_r, hk_cy + hk_r], fill=_MUSTARD)
    _draw_center(draw, hk_cx, hk_cy, "HK", f_hk, _BG_TOP)

    # Ligne séparatrice
    draw.rectangle([PAD, by, SIZE - PAD, by + 1], fill=(*accent, 90))
    return by + 1


def _footer(draw, left_text: str):
    PAD    = 48
    BOT_H  = 56
    f_foot = _font("Barlow-SemiBold.ttf", 19)
    fy = SIZE - BOT_H
    draw.rectangle([PAD, fy, SIZE - PAD, fy + 1], fill=(*_MUSTARD, 55))
    ty = fy + (BOT_H - _th(f_foot, "A")) // 2
    draw.text((PAD, ty), left_text, font=f_foot, fill=(*_MUSTARD, 200))
    hm = "@HK.MÉDIA"
    draw.text((SIZE - PAD - _tw(f_foot, hm), ty), hm, font=f_foot, fill=(*_WHITE, 90))


# ──────────────────────────────────────────────────────────────────────────────
#  FOOTBALL / BASKET / RUGBY — une ligne par match
# ──────────────────────────────────────────────────────────────────────────────

def make_football_scores(fixtures: list[dict], league: dict) -> bytes:
    brand.ensure_fonts()

    img  = _bg(SIZE)
    draw = ImageDraw.Draw(img, "RGBA")

    PAD   = 48
    BOT_H = 56
    lc    = league.get("color", (226, 165, 15))

    f_team  = _font("Barlow-SemiBold.ttf", 24)
    f_score = _font("Anton-Regular.ttf",   60)
    f_sep   = _font("Anton-Regular.ttf",   30)

    body_top = _header(img, draw, league["name"], league.get("country", ""), lc)

    # Layout cartes
    LOGO_SZ = 64
    IPAD    = 18
    VPAD    = 14
    CARD_H  = LOGO_SZ + 2 * VPAD
    GAP     = 10

    n       = len(fixtures)
    total_h = n * CARD_H + (n - 1) * GAP
    avail   = (SIZE - BOT_H) - body_top
    y0      = body_top + (avail - total_h) // 2

    SCORE_ZONE = 180
    SIDE_W     = (SIZE - 2 * PAD - SCORE_ZONE) // 2
    score_cx   = SIZE // 2
    NAME_MAX_W = SIDE_W - LOGO_SZ - IPAD * 2 - 8

    def trunc(txt, max_w):
        while _tw(f_team, txt) > max_w and len(txt) > 3:
            txt = txt[:-2].rstrip() + "."
        return txt

    for i, fix in enumerate(fixtures):
        home   = fix.get("teams", {}).get("home", {})
        away   = fix.get("teams", {}).get("away", {})
        goals  = fix.get("goals", {})
        g_h    = goals.get("home")
        g_a    = goals.get("away")
        status = fix.get("fixture", {}).get("status", {}).get("short", "NS")

        y  = y0 + i * (CARD_H + GAP)
        x1 = PAD
        x2 = SIZE - PAD
        cy = y + CARD_H // 2

        draw.rounded_rectangle([x1, y, x2, y + CARD_H], radius=12, fill=_CARD)

        lx_h = x1 + IPAD
        lx_a = x2 - IPAD - LOGO_SZ
        ly   = y + VPAD
        logo_h = _logo(home.get("logo", ""), LOGO_SZ)
        logo_a = _logo(away.get("logo", ""), LOGO_SZ)
        if logo_h:
            img.paste(logo_h, (lx_h, ly), logo_h)
        if logo_a:
            img.paste(logo_a, (lx_a, ly), logo_a)

        h_name = trunc(_fr(home.get("name", "")), NAME_MAX_W)
        a_name = trunc(_fr(away.get("name", "")), NAME_MAX_W)

        nh   = _th(f_team, h_name)
        bb_h = f_team.getbbox(h_name)
        draw.text((lx_h + LOGO_SZ + 10, cy - nh // 2 - bb_h[1]), h_name,
                  font=f_team, fill=_CREAM)

        nw_a = _tw(f_team, a_name)
        bb_a = f_team.getbbox(a_name)
        draw.text((lx_a - 10 - nw_a, cy - nh // 2 - bb_a[1]), a_name,
                  font=f_team, fill=_CREAM)

        finished = status not in ("NS", "TBD", "")
        if g_h is not None and g_a is not None and finished:
            c_h = _WIN if g_h > g_a else (_LOSE if g_h < g_a else _DRAW)
            c_a = _WIN if g_a > g_h else (_LOSE if g_a < g_h else _DRAW)

            t_gh, t_sep, t_ga = str(g_h), "–", str(g_a)
            w_gh, w_sep, w_ga = _tw(f_score, t_gh), _tw(f_sep, t_sep), _tw(f_score, t_ga)
            sp    = 12
            total = w_gh + sp + w_sep + sp + w_ga
            sx    = score_cx - total // 2
            _draw_center(draw, sx + w_gh // 2, cy, t_gh, f_score, c_h)
            _draw_center(draw, sx + w_gh + sp + w_sep // 2, cy, t_sep, f_sep, _GRAY)
            _draw_center(draw, sx + w_gh + sp + w_sep + sp + w_ga // 2, cy, t_ga, f_score, c_a)
        else:
            _draw_center(draw, score_cx, cy, "–", f_sep, _GRAY)

    _footer(draw, "RÉSULTATS DU JOUR")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
#  FORMULE 1 — podium + portrait du vainqueur à droite
# ──────────────────────────────────────────────────────────────────────────────

# ── Portraits curatés (fichiers Wikimedia Commons vérifiés = VISAGE) ──────────
# Override quand l'infobox Wikipédia renvoie une voiture ou une photo de loin.
# Plusieurs fichiers par pilote = rotation (varie le portrait des vainqueurs récurrents).
# Clé = nom normalisé (sans accents, minuscules). Valeur = liste de titres Commons.
_PORTRAIT_FILES: dict[str, list[str]] = {
    "oscar piastri": [
        "Oscar Piastri in Trafalgar Square, 2nd July 2025.png",
    ],
    "max verstappen": [
        "Max Verstappen at the Red Bull Fan Zone – Crown Riverwalk, Melbourne "
        "(028A7659) - cropped.jpg",
    ],
    # Ajoutables : "lance stroll", "oliver bearman", "alexander albon", etc.
}


def _commons_thumb(title: str, size: int = 480) -> str | None:
    """Résout un titre de fichier Commons → URL de miniature (taille cachée
    par Wikimedia → évite le rate-limit 429 des originaux pleine résolution)."""
    import json
    t = title if title.lower().startswith("file:") else f"File:{title}"
    params = urllib.parse.urlencode({
        "action": "query", "titles": t, "prop": "imageinfo",
        "iiprop": "url", "iiurlwidth": str(size), "format": "json",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        for p in d.get("query", {}).get("pages", {}).values():
            ii = p.get("imageinfo", [])
            if ii:
                return ii[0].get("thumburl") or ii[0].get("url")
    except Exception:
        pass
    return None


def _wikipedia_lead_image(name: str) -> str | None:
    """URL de l'image d'infobox Wikipédia (= portrait/visage cadré du pilote).
    Bien plus fiable qu'une recherche d'images : c'est la photo de présentation."""
    import json
    slug = urllib.parse.quote(name.replace(" ", "_"))
    for lang in ("fr", "en"):
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
            src = (d.get("originalimage", {}).get("source")
                   or d.get("thumbnail", {}).get("source"))
            if src:
                return src
        except Exception:
            continue
    return None


def _fetch_driver_portrait(name: str) -> bytes | None:
    """Portrait du pilote (visage), par ordre de fiabilité :
    1. override curaté Commons (rotation par jour si plusieurs photos)
    2. image d'infobox Wikipédia (FR puis EN)
    3. recherche Wikimedia générique."""
    if not name:
        return None

    # 1. Override curaté — garantit un visage là où l'infobox échoue,
    #    et fait tourner les portraits pour les vainqueurs récurrents.
    from datetime import date
    files = _PORTRAIT_FILES.get(_strip_accents(name))
    if files:
        idx = date.today().toordinal() % len(files)
        for k in range(len(files)):
            url = _commons_thumb(files[(idx + k) % len(files)])
            if url:
                data = _download(url, timeout=12)
                if data:
                    return data

    # 2. Infobox Wikipédia
    url = _wikipedia_lead_image(name)
    if url:
        data = _download(url, timeout=12)
        if data:
            return data
    # Repli : recherche Wikimedia classique
    try:
        from image_fetch import _fetch_wikimedia, download_image
    except Exception:
        return None
    last = _strip_accents(name.split()[-1])
    for q in (f"{name} portrait", name):
        u = _fetch_wikimedia(q, prefer_name=last)
        if u:
            data = download_image(u)
            if data:
                return data
    return None


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Recadre l'image pour remplir w×h (crop centré, biais vers le haut pour le visage)."""
    src, tgt = im.width / im.height, w / h
    if src > tgt:                       # trop large → rogne les côtés
        nw = int(im.height * tgt)
        left = (im.width - nw) // 2
        im = im.crop((left, 0, left + nw, im.height))
    else:                              # trop haute → rogne le bas (garde la tête)
        nh = int(im.width / tgt)
        top = (im.height - nh) // 4
        im = im.crop((0, top, im.width, top + nh))
    return im.resize((w, h), Image.LANCZOS)


def _rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return mask


def make_f1_podium(race: dict, results: list[dict], winner_photo: bytes | None = None) -> bytes:
    brand.ensure_fonts()

    img  = _bg(SIZE)
    draw = ImageDraw.Draw(img, "RGBA")

    PAD    = 48
    BOT_H  = 56
    F1_RED = (210, 0, 0)

    body_top = _header(img, draw, "Formula 1",
                       race.get("competition", {}).get("name", "Grand Prix"), F1_RED)

    n = min(3, len(results))

    # Portrait du vainqueur (P1) — fetch si non fourni
    if winner_photo is None and results:
        winner_photo = _fetch_driver_portrait(results[0].get("driver", {}).get("name", ""))

    avail = (SIZE - BOT_H) - body_top
    block_h = 486
    GAP     = 18
    CARD_H  = (block_h - (n - 1) * GAP) // n
    y0      = body_top + (avail - block_h) // 2

    f_rank   = _font("Anton-Regular.ttf",   72)
    f_driver = _font("Anton-Regular.ttf",   36)
    f_detail = _font("Barlow-SemiBold.ttf", 21)

    has_photo = winner_photo is not None
    if has_photo:
        PANEL_W = 348
        panel_x = SIZE - PAD - PANEL_W
        rows_x2 = panel_x - 26
    else:
        rows_x2 = SIZE - PAD

    # ── Portrait à droite ─────────────────────────────────────────────────────
    if has_photo:
        try:
            por = Image.open(io.BytesIO(winner_photo)).convert("RGB")
            por = _cover(por, PANEL_W, block_h)
            mask = _rounded_mask(PANEL_W, block_h, 16)
            img.paste(por, (panel_x, y0), mask)

            # Dégradé sombre bas pour lisibilité du texte
            grad = Image.new("RGBA", (PANEL_W, block_h), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(grad)
            gh   = int(block_h * 0.42)
            for k in range(gh):
                a = int(220 * (k / gh) ** 1.4)
                gd.line([(0, block_h - gh + k), (PANEL_W, block_h - gh + k)],
                        fill=(8, 10, 18, a))
            grad.putalpha(Image.composite(grad.getchannel("A"),
                                          Image.new("L", (PANEL_W, block_h), 0),
                                          _rounded_mask(PANEL_W, block_h, 16)))
            img.paste(grad, (panel_x, y0), grad)

            # Liseré or + badge VAINQUEUR + nom
            draw.rounded_rectangle([panel_x, y0, panel_x + PANEL_W, y0 + block_h],
                                   radius=16, outline=(*_GOLD, 230), width=3)
            f_badge = _font("Barlow-SemiBold.ttf", 20)
            f_name  = _font("Anton-Regular.ttf",   34)
            win = results[0]
            wname = win.get("driver", {}).get("name", "").upper()
            wteam = win.get("team", {}).get("name", "")
            # Badge
            bx, byy = panel_x + 20, y0 + block_h - 118
            btxt = "VAINQUEUR"
            bw = _tw(f_badge, btxt) + 24
            draw.rounded_rectangle([bx, byy, bx + bw, byy + 32], radius=8, fill=(*_GOLD, 235))
            _draw_center(draw, bx + bw // 2, byy + 16, btxt, f_badge, _BG_TOP)
            # Nom + équipe
            _draw_top(draw, panel_x + 20, byy + 42, wname, f_name, _WHITE)
            draw.text((panel_x + 20, byy + 80), wteam, font=f_detail, fill=(220, 220, 230))
        except Exception:
            has_photo = False
            rows_x2 = SIZE - PAD

    # ── Classement à gauche ───────────────────────────────────────────────────
    for idx in range(n):
        res    = results[idx]
        color  = [_GOLD, _SILVER, _BRONZE][idx]
        y      = y0 + idx * (CARD_H + GAP)
        name   = res.get("driver", {}).get("name", f"Pilote {idx+1}").upper()
        team_n = res.get("team", {}).get("name", "")
        time_v = res.get("time", {}).get("time", "") or str(res.get("points", ""))

        draw.rounded_rectangle([PAD, y, rows_x2, y + CARD_H], radius=12, fill=_CARD)
        draw.rounded_rectangle([PAD, y, PAD + 7, y + CARD_H], radius=4, fill=color)

        cy = y + CARD_H // 2
        _draw_center(draw, PAD + 52, cy, str(idx + 1), f_rank, color)

        # Tronque le nom si portrait présent (cartes plus étroites)
        name_max = rows_x2 - (PAD + 100) - 16
        nm = name
        while _tw(f_driver, nm) > name_max and len(nm) > 4:
            nm = nm[:-2].rstrip() + "."

        draw.text((PAD + 100, cy - 30), nm, font=f_driver, fill=_CREAM)
        detail = f"{team_n}  ·  {time_v}" if time_v else team_n
        if _tw(f_detail, detail) > name_max:
            detail = team_n
        draw.text((PAD + 100, cy + 12), detail, font=f_detail, fill=_GRAY)

    _footer(draw, "RÉSULTATS COURSE")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
