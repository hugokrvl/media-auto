"""
Renderer DÉCRYPTAGE — thème CLAIR éditorial (onglet « Créer » du site).

Style inspiré des décryptages Instagram « propres » : fond papier crème, palette
navy + or, titres ALL-CAPS bicolores, ICÔNES line-art dans des cercles, chiffres /
phrases-clés surlignés en or, bandeaux photo optionnels, mise en page synthétique.

≠ du reste du média (breaking / data nocturne / sport) qui reste SOMBRE. Ici tout est
dessiné en coordonnées PIXELS (axes 1080×1350, aspect égal) → vrais cercles, contrôle fin.

API : render_decryptage(data) -> list[bytes]  (un PNG 1080×1350 par slide).
"""

import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (Circle, Rectangle, FancyBboxPatch, Arc, Polygon)

import brand as B

# ── Palette CLAIRE ───────────────────────────────────────────────────────────
PAPER = "#F3F1EA"      # fond papier crème (froid, propre)
PAPER_2 = "#ECE7DA"    # cercles d'icônes / panneaux
NAVY = "#15294C"       # bleu nuit (titres, traits d'icônes)
NAVY_SOFT = "#33415C"  # bleu adouci (sous-titres)
BODY = "#3B4254"       # texte courant
GOLD = "#E0A21A"       # or (accents, surlignage)
GOLD_DK = "#B8800C"    # or foncé
RED = "#C8472E"        # tag négatif (risques)
RING = "#C9C1AC"       # contour des cercles d'icônes

W, H = 1080, 1350
MARGIN = 96
CW = W - 2 * MARGIN     # largeur de contenu (888)


# ── Figure / fond ────────────────────────────────────────────────────────────
def _fig():
    """Fig 1080×1350 en coordonnées pixels (y vers le haut), fond papier."""
    dpi = 120
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, facecolor=PAPER, edgecolor="none", zorder=0))
    # filet or discret en bordure (cadre éditorial léger)
    ax.add_patch(Rectangle((34, 34), W - 68, H - 68, fill=False,
                 edgecolor=GOLD, linewidth=1.1, alpha=0.45, zorder=1))
    fig._F = B.fonts()
    return fig, ax


def _finish(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=PAPER)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _Y(top):
    """Convertit une distance depuis le HAUT en coordonnée y (origine en bas)."""
    return H - top


# ════════════════════════════════════════════════════════════════════════════
#  BIBLIOTHÈQUE D'ICÔNES LINE-ART  (dessinées dans un cercle de rayon R)
#  Chaque fonction dessine le glyphe centré en (cx, cy), dimensionné par s (~0.6 R).
# ════════════════════════════════════════════════════════════════════════════
_LW = 3.2          # épaisseur de trait principale
_LW2 = 2.4         # détails


def _line(ax, x1, y1, x2, y2, c=NAVY, lw=_LW, z=5, cap="round"):
    ax.plot([x1, x2], [y1, y2], color=c, lw=lw, solid_capstyle=cap, zorder=z)


def _ic_reseau(ax, cx, cy, s, c):           # blockchain / réseau
    pts = [(cx, cy + s), (cx + s, cy + s * 0.2), (cx + s * 0.6, cy - s),
           (cx - s * 0.6, cy - s), (cx - s, cy + s * 0.2)]
    for x, y in pts:
        _line(ax, cx, cy, x, y, c, _LW2)
    for x, y in pts:
        ax.add_patch(Circle((x, y), s * 0.22, facecolor=c, edgecolor="none", zorder=6))
    ax.add_patch(Circle((cx, cy), s * 0.30, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))


def _ic_cadenas(ax, cx, cy, s, c):          # cadenas / sécurité / offre limitée
    bw, bh = s * 1.5, s * 1.15
    ax.add_patch(FancyBboxPatch((cx - bw / 2, cy - bh), bw, bh,
                 boxstyle="round,pad=0,rounding_size=%.1f" % (s * 0.22),
                 facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Arc((cx, cy - bh * 0.08), s * 1.0, s * 1.25, angle=0,
                 theta1=20, theta2=160, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Circle((cx, cy - bh * 0.45), s * 0.16, facecolor=c, edgecolor="none", zorder=7))
    _line(ax, cx, cy - bh * 0.45, cx, cy - bh * 0.72, c, _LW2, z=7)


def _ic_banque(ax, cx, cy, s, c):           # banque / état / institution
    _line(ax, cx - s * 1.2, cy + s * 0.05, cx + s * 1.2, cy + s * 0.05, c, _LW)   # base toit
    ax.add_patch(Polygon([(cx, cy + s), (cx - s * 1.2, cy + s * 0.05),
                          (cx + s * 1.2, cy + s * 0.05)], closed=True,
                          facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    for dx in (-0.8, -0.27, 0.27, 0.8):
        _line(ax, cx + dx * s, cy - s * 0.9, cx + dx * s, cy + s * 0.0, c, _LW2)   # colonnes
    _line(ax, cx - s * 1.25, cy - s * 0.95, cx + s * 1.25, cy - s * 0.95, c, _LW)  # socle


def _ic_echange(ax, cx, cy, s, c):          # échange / transfert / liquidité
    ax.add_patch(Arc((cx, cy), s * 1.7, s * 1.7, angle=0, theta1=25, theta2=200,
                 edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Arc((cx, cy), s * 1.7, s * 1.7, angle=0, theta1=205, theta2=380,
                 edgecolor=c, lw=_LW, zorder=6))
    _arrow_head(ax, cx + s * 0.78, cy + s * 0.32, 35, s * 0.45, c)
    _arrow_head(ax, cx - s * 0.78, cy - s * 0.32, 215, s * 0.45, c)


def _ic_courbe_haut(ax, cx, cy, s, c):      # performance / croissance
    _line(ax, cx - s * 1.1, cy + s, cx - s * 1.1, cy - s, c, _LW2)        # axe Y
    _line(ax, cx - s * 1.1, cy - s, cx + s * 1.1, cy - s, c, _LW2)        # axe X
    xs = [cx - s * 0.9, cx - s * 0.2, cx + s * 0.3, cx + s * 0.95]
    ys = [cy - s * 0.4, cy + s * 0.05, cy - s * 0.15, cy + s * 0.75]
    ax.plot(xs, ys, color=c, lw=_LW, solid_capstyle="round", zorder=6)
    _arrow_head(ax, xs[-1], ys[-1], 48, s * 0.5, c)


def _ic_courbe_bas(ax, cx, cy, s, c):       # baisse / volatilité / risque
    _line(ax, cx - s * 1.1, cy + s, cx - s * 1.1, cy - s, c, _LW2)
    _line(ax, cx - s * 1.1, cy - s, cx + s * 1.1, cy - s, c, _LW2)
    xs = [cx - s * 0.9, cx - s * 0.2, cx + s * 0.3, cx + s * 0.95]
    ys = [cy + s * 0.6, cy + s * 0.05, cy + s * 0.25, cy - s * 0.6]
    ax.plot(xs, ys, color=c, lw=_LW, solid_capstyle="round", zorder=6)
    _arrow_head(ax, xs[-1], ys[-1], -52, s * 0.5, c)


def _ic_barres(ax, cx, cy, s, c):           # comparaison / marché
    for i, h in enumerate((0.5, 0.95, 0.7, 1.25)):
        x = cx - s + i * (s * 0.66)
        ax.add_patch(Rectangle((x, cy - s), s * 0.42, h * s, facecolor=PAPER,
                     edgecolor=c, lw=_LW2, zorder=6))


def _ic_bouclier(ax, cx, cy, s, c):         # protection / assurance / sécurité
    verts = [(cx, cy + s * 1.1), (cx + s, cy + s * 0.55), (cx + s, cy - s * 0.25),
             (cx, cy - s * 1.15), (cx - s, cy - s * 0.25), (cx - s, cy + s * 0.55)]
    ax.add_patch(Polygon(verts, closed=True, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    _line(ax, cx - s * 0.42, cy - s * 0.05, cx - s * 0.05, cy - s * 0.45, c, _LW)   # check
    _line(ax, cx - s * 0.05, cy - s * 0.45, cx + s * 0.5, cy + s * 0.4, c, _LW)


def _ic_globe(ax, cx, cy, s, c):            # international / portabilité / monde
    ax.add_patch(Circle((cx, cy), s, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Arc((cx, cy), s * 0.9, s * 2, angle=0, theta1=0, theta2=360,
                 edgecolor=c, lw=_LW2, zorder=6))
    _line(ax, cx - s, cy, cx + s, cy, c, _LW2)
    _line(ax, cx - s * 0.86, cy + s * 0.5, cx + s * 0.86, cy + s * 0.5, c, _LW2)
    _line(ax, cx - s * 0.86, cy - s * 0.5, cx + s * 0.86, cy - s * 0.5, c, _LW2)


def _ic_ampoule(ax, cx, cy, s, c):          # innovation / idée
    ax.add_patch(Circle((cx, cy + s * 0.2), s * 0.8, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Rectangle((cx - s * 0.35, cy - s * 0.95), s * 0.7, s * 0.5,
                 facecolor=PAPER, edgecolor=c, lw=_LW2, zorder=6))
    _line(ax, cx - s * 0.25, cy - s * 0.62, cx + s * 0.25, cy - s * 0.62, c, _LW2, z=7)
    for a in (60, 90, 120):                  # rayons
        r = math.radians(a)
        _line(ax, cx + math.cos(r) * s * 1.0, cy + s * 0.2 + math.sin(r) * s * 1.0,
              cx + math.cos(r) * s * 1.4, cy + s * 0.2 + math.sin(r) * s * 1.4, GOLD, _LW2)


def _ic_portefeuille(ax, cx, cy, s, c):     # portefeuille / épargne / wallet
    bw, bh = s * 2.0, s * 1.4
    ax.add_patch(FancyBboxPatch((cx - bw / 2, cy - bh / 2), bw, bh,
                 boxstyle="round,pad=0,rounding_size=%.1f" % (s * 0.2),
                 facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Rectangle((cx + bw / 2 - s * 0.7, cy - s * 0.28), s * 0.7, s * 0.56,
                 facecolor=PAPER_2, edgecolor=c, lw=_LW2, zorder=7))
    ax.add_patch(Circle((cx + bw / 2 - s * 0.35, cy), s * 0.1, facecolor=c, edgecolor="none", zorder=8))


def _ic_cible(ax, cx, cy, s, c):            # objectif / cible
    for rr in (1.0, 0.62, 0.26):
        ax.add_patch(Circle((cx, cy), s * rr, facecolor=PAPER if rr > 0.3 else c,
                     edgecolor=c, lw=_LW2 if rr < 1 else _LW, zorder=6))


def _ic_alerte(ax, cx, cy, s, c):           # vulnérabilité / risque / attention
    ax.add_patch(Polygon([(cx, cy + s * 1.1), (cx + s * 1.15, cy - s * 0.8),
                          (cx - s * 1.15, cy - s * 0.8)], closed=True,
                          facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6,
                          joinstyle="round"))
    _line(ax, cx, cy + s * 0.55, cx, cy - s * 0.18, c, _LW, z=7)
    ax.add_patch(Circle((cx, cy - s * 0.48), s * 0.13, facecolor=c, edgecolor="none", zorder=7))


def _ic_horloge(ax, cx, cy, s, c):          # 24/7 / temps / liquidité
    ax.add_patch(Circle((cx, cy), s, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    _line(ax, cx, cy, cx, cy + s * 0.62, c, _LW, z=7)
    _line(ax, cx, cy, cx + s * 0.45, cy + s * 0.18, c, _LW, z=7)


def _ic_piece(ax, cx, cy, s, c):            # monnaie / valeur / actif
    ax.add_patch(Circle((cx, cy), s, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    ax.add_patch(Circle((cx, cy), s * 0.72, facecolor=PAPER, edgecolor=c, lw=_LW2, zorder=6))
    fp = plt.matplotlib.font_manager.FontProperties(weight="bold")
    ax.text(cx, cy, "$", ha="center", va="center", color=c, fontsize=s * 0.95,
            fontproperties=fp, zorder=7)


def _ic_groupe(ax, cx, cy, s, c):           # adoption / confiance / communauté
    for dx in (-s * 0.6, s * 0.6):
        ax.add_patch(Circle((cx + dx, cy + s * 0.35), s * 0.42,
                     facecolor=PAPER, edgecolor=c, lw=_LW2, zorder=6))
        ax.add_patch(Arc((cx + dx, cy - s * 0.55), s * 1.05, s * 1.2, angle=0,
                     theta1=20, theta2=160, edgecolor=c, lw=_LW2, zorder=6))


def _ic_document(ax, cx, cy, s, c):         # régulation / cadre légal / document
    ax.add_patch(Rectangle((cx - s * 0.75, cy - s), s * 1.5, s * 2,
                 facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    for i in range(3):
        _line(ax, cx - s * 0.45, cy + s * (0.4 - i * 0.45),
              cx + s * 0.45, cy + s * (0.4 - i * 0.45), c, _LW2, z=7)


def _ic_balance(ax, cx, cy, s, c):          # comparaison / équilibre / régulation
    _line(ax, cx, cy - s, cx, cy + s, c, _LW)
    _line(ax, cx - s, cy + s * 0.7, cx + s, cy + s * 0.7, c, _LW)
    for dx in (-s, s):
        ax.add_patch(Arc((cx + dx, cy + s * 0.55), s * 0.9, s * 0.7, angle=0,
                     theta1=200, theta2=340, edgecolor=c, lw=_LW2, zorder=6))
        _line(ax, cx + dx - s * 0.42, cy + s * 0.62, cx + dx, cy + s * 0.3, c, _LW2)
        _line(ax, cx + dx + s * 0.42, cy + s * 0.62, cx + dx, cy + s * 0.3, c, _LW2)
    ax.add_patch(Rectangle((cx - s * 0.3, cy - s), s * 0.6, s * 0.18,
                 facecolor=c, edgecolor="none", zorder=6))


def _ic_bitcoin(ax, cx, cy, s, c):          # bitcoin / crypto
    ax.add_patch(Circle((cx, cy), s, facecolor=PAPER, edgecolor=c, lw=_LW, zorder=6))
    fp = plt.matplotlib.font_manager.FontProperties(weight="bold")
    ax.text(cx, cy - s * 0.02, "B", ha="center", va="center", color=c,
            fontsize=s * 1.25, fontproperties=fp, zorder=7)
    _line(ax, cx - s * 0.12, cy + s * 0.6, cx - s * 0.12, cy - s * 0.62, c, _LW2, z=8)
    _line(ax, cx + s * 0.18, cy + s * 0.6, cx + s * 0.18, cy - s * 0.62, c, _LW2, z=8)


def _ic_puce(ax, cx, cy, s, c):             # défaut : pastille
    ax.add_patch(Circle((cx, cy), s * 0.5, facecolor=GOLD, edgecolor="none", zorder=6))


def _arrow_head(ax, x, y, ang_deg, size, c):
    """Petite pointe de flèche (triangle) orientée à ang_deg, sommet en (x,y)."""
    a = math.radians(ang_deg)
    back = a + math.pi
    left = back + math.radians(28)
    right = back - math.radians(28)
    p1 = (x + math.cos(left) * size, y + math.sin(left) * size)
    p2 = (x + math.cos(right) * size, y + math.sin(right) * size)
    ax.add_patch(Polygon([(x, y), p1, p2], closed=True, facecolor=c,
                 edgecolor="none", zorder=7))


ICONS = {
    "reseau": _ic_reseau, "blockchain": _ic_reseau, "technologie": _ic_reseau,
    "cadenas": _ic_cadenas, "securite": _ic_cadenas, "limite": _ic_cadenas,
    "banque": _ic_banque, "etat": _ic_banque, "institution": _ic_banque,
    "echange": _ic_echange, "transfert": _ic_echange,
    "hausse": _ic_courbe_haut, "croissance": _ic_courbe_haut, "performance": _ic_courbe_haut,
    "baisse": _ic_courbe_bas, "volatilite": _ic_courbe_bas, "risque": _ic_courbe_bas,
    "barres": _ic_barres, "marche": _ic_barres, "comparaison": _ic_barres,
    "bouclier": _ic_bouclier, "protection": _ic_bouclier, "assurance": _ic_bouclier,
    "globe": _ic_globe, "monde": _ic_globe, "international": _ic_globe, "portabilite": _ic_globe,
    "ampoule": _ic_ampoule, "innovation": _ic_ampoule, "idee": _ic_ampoule,
    "portefeuille": _ic_portefeuille, "epargne": _ic_portefeuille, "wallet": _ic_portefeuille,
    "cible": _ic_cible, "objectif": _ic_cible,
    "alerte": _ic_alerte, "attention": _ic_alerte, "vulnerabilite": _ic_alerte,
    "horloge": _ic_horloge, "temps": _ic_horloge, "liquidite": _ic_horloge,
    "piece": _ic_piece, "monnaie": _ic_piece, "valeur": _ic_piece, "actif": _ic_piece,
    "groupe": _ic_groupe, "adoption": _ic_groupe, "confiance": _ic_groupe, "communaute": _ic_groupe,
    "document": _ic_document, "regulation": _ic_document, "loi": _ic_document,
    "balance": _ic_balance, "equilibre": _ic_balance,
    "bitcoin": _ic_bitcoin, "crypto": _ic_bitcoin,
    "puce": _ic_puce,
}

# Mots-clés → icône (repli si l'IA ne fournit pas d'icône valide).
_KW = [
    (("blockchain", "réseau", "reseau", "décentralis", "protocole", "techno"), "reseau"),
    (("sécur", "secur", "clé", "cle ", "chiffr", "crypto-actif", "minage"), "cadenas"),
    (("limit", "plafond", "rare", "21 million", "offre", "fixe"), "cadenas"),
    (("état", "etat", "banque centrale", "monétaire", "gouvern", "institution"), "banque"),
    (("échange", "echange", "transfer", "paiement", "transac"), "echange"),
    (("perform", "croissance", "hausse", "progress", "rendement"), "hausse"),
    (("volatil", "baisse", "chute", "effondre", "perte", "krach"), "baisse"),
    (("compar", "marché", "marche", "classement"), "barres"),
    (("protég", "proteg", "protection", "assurance", "couvert", "refuge"), "bouclier"),
    (("intern", "monde", "global", "mondial", "portab", "frontière"), "globe"),
    (("innov", "idée", "idee", "nouveau", "futur", "découv"), "ampoule"),
    (("épargne", "epargne", "portefeuille", "wallet", "diversif"), "portefeuille"),
    (("objectif", "but", "cible", "viser"), "cible"),
    (("risqu", "vulnér", "vulner", "menace", "danger", "attention", "faille"), "alerte"),
    (("24/7", "liquid", "rapide", "instant", "temps", "permanent"), "horloge"),
    (("adopt", "confiance", "communaut", "institutionnel", "utilisateur"), "groupe"),
    (("régul", "regul", "légal", "legal", "cadre", "loi", "juridique"), "document"),
    (("monnaie", "valeur", "actif", "réserve", "reserve"), "piece"),
    (("bitcoin", "btc", "satoshi"), "bitcoin"),
]


def _icon_for(name, label, texte):
    """Résout l'icône : nom explicite → mot-clé → défaut 'puce'."""
    if name and str(name).strip().lower() in ICONS:
        return ICONS[str(name).strip().lower()]
    hay = f"{label} {texte}".lower()
    for keys, ic in _KW:
        if any(k in hay for k in keys):
            return ICONS[ic]
    return ICONS["puce"]


def _draw_icon(ax, name, label, texte, cx, cy, R=46, accent=NAVY):
    """Cercle clair + anneau + glyphe line-art centré."""
    ax.add_patch(Circle((cx, cy), R, facecolor=PAPER_2, edgecolor=RING, lw=1.6, zorder=4))
    fn = _icon_for(name, label, texte)
    fn(ax, cx, cy, R * 0.52, accent)


# ── Texte : mesure, flow riche (surlignage or inline) ────────────────────────
def _renderer(fig):
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _wpx(fig, text, fp, fs):
    """Largeur en pixels d'un texte (1 unité data = 1 px ici)."""
    if not text:
        return 0.0
    t = fig.text(0, 0, text, fontproperties=fp, fontsize=fs)
    w = t.get_window_extent(_renderer(fig)).width
    t.remove()
    return w


def _flow_rich(fig, ax, x, y_top, max_w, words, fp, fs, lh, base=BODY):
    """Pose des mots (chacun (texte, couleur)) avec retour à la ligne. Renvoie le y du bas."""
    space = _wpx(fig, " ", fp, fs)
    cx, y = x, y_top
    first = True
    for word, col in words:
        ww = _wpx(fig, word, fp, fs)
        if not first and cx + ww > x + max_w:
            cx = x
            y += lh
            first = True
        ax.text(cx, _Y(y), word, ha="left", va="top", color=col or base,
                fontproperties=fp, fontsize=fs, zorder=5)
        cx += ww + space
        first = False
    return y + lh        # bas de la dernière ligne (en "depuis le haut")


def _rich_words(texte, fort):
    """Découpe `texte` en (mot, couleur) ; les mots couverts par `fort` passent en or."""
    words = texte.split()
    gold_set = set()
    if fort:
        f = fort.strip().lower()
        toks = [w.strip(".,;:!?»«()").lower() for w in words]
        ftoks = [t.strip(".,;:!?»«()").lower() for t in f.split()]
        if ftoks:
            for i in range(len(toks) - len(ftoks) + 1):
                if toks[i:i + len(ftoks)] == ftoks:
                    gold_set.update(range(i, i + len(ftoks)))
    return [(w, GOLD_DK if i in gold_set else None) for i, w in enumerate(words)]


# ── Titre bicolore ───────────────────────────────────────────────────────────
def _two_tone_title(fig, ax, l1, l2, y_top, fs=78, x=MARGIN, max_w=CW):
    F = fig._F
    fp = F["body_xb"]

    def _wrap(s):
        s = (s or "").strip().upper()
        if not s:
            return []
        out, cur = [], ""
        for w in s.split():
            t = (cur + " " + w).strip()
            if _wpx(fig, t, fp, fs) <= max_w:
                cur = t
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out

    y = y_top
    lh = fs * 1.20
    for ln in _wrap(l1):
        ax.text(x, _Y(y), ln, ha="left", va="top", color=NAVY, fontproperties=fp,
                fontsize=fs, zorder=5)
        y += lh
    for ln in _wrap(l2):
        ax.text(x, _Y(y), ln, ha="left", va="top", color=GOLD, fontproperties=fp,
                fontsize=fs, zorder=5)
        y += lh
    return y


def _footer(fig, ax, source=""):
    F = fig._F
    ax.add_patch(Circle((W / 2, 62), 26, facecolor=NAVY, edgecolor="none", zorder=5))
    ax.text(W / 2, 62, "HK", ha="center", va="center", color=PAPER,
            fontproperties=F["num"], fontsize=20, zorder=6)
    ax.plot([W / 2 - 26, W / 2 + 26], [30, 30], color=GOLD, lw=2.4, zorder=5)
    if source:
        ax.text(W - MARGIN, 60, "@HK.MÉDIA", ha="right", va="center", color=NAVY_SOFT,
                fontproperties=F["body_sb"], fontsize=14, zorder=5)


# ── Bloc « point » : icône + label + texte (avec surlignage) ─────────────────
def _point_block(fig, ax, x, y_top, max_w, p, row_h, icon_R=46):
    """Dessine un point dans une bande de hauteur row_h. Icône à gauche, texte à droite."""
    F = fig._F
    label = (p.get("label") or "").strip()
    texte = (p.get("texte") or p.get("text") or "").strip()
    fort = p.get("fort") or p.get("highlight")
    icon = p.get("icon")

    cy = y_top + row_h / 2
    cx_icon = x + icon_R
    _draw_icon(ax, icon, label, texte, cx_icon, _Y(cy), R=icon_R)

    tx = x + icon_R * 2 + 30
    tw = max_w - (icon_R * 2 + 30)
    y = y_top + 6
    if label:
        ax.text(tx, _Y(y), label, ha="left", va="top", color=NAVY,
                fontproperties=F["body_bold"], fontsize=27, zorder=5)
        y += 40
    if texte:
        _flow_rich(fig, ax, tx, y, tw, _rich_words(texte, fort), F["body_md"], 22.5, 30)


# ════════════════════════════════════════════════════════════════════════════
#  SLIDES
# ════════════════════════════════════════════════════════════════════════════
def _slide_cover(fig, ax, data):
    F = fig._F
    ax.text(MARGIN, _Y(150), "DÉCRYPTAGE", ha="left", va="top", color=GOLD_DK,
            fontproperties=F["body_sb"], fontsize=22, zorder=5)
    ax.plot([MARGIN, MARGIN + 250], [_Y(196), _Y(196)], color=GOLD, lw=3, zorder=5)

    yb = _two_tone_title(fig, ax, data.get("titre", ""), data.get("titre2", ""),
                         y_top=250, fs=92)
    intro = (data.get("intro") or "").strip()
    if intro:
        _flow_rich(fig, ax, MARGIN, yb + 40, CW,
                   [(w, None) for w in intro.split()], F["body_md"], 28, 40, base=BODY)

    # rangée d'icônes-thème (au centre du vide, séparateur or au-dessus)
    ax.plot([MARGIN, W - MARGIN], [_Y(820), _Y(820)], color=RING, lw=1.2, zorder=4)
    icons = (data.get("cover_icons") or ["reseau", "cadenas", "piece"])[:3]
    n = len(icons)
    gap = CW / n
    for i, name in enumerate(icons):
        cx = MARGIN + gap * (i + 0.5)
        _draw_icon(ax, name, "", "", cx, _Y(960), R=66)

    ax.text(W - MARGIN, _Y(1190), "GLISSEZ", ha="right", va="center", color=GOLD_DK,
            fontproperties=F["body_sb"], fontsize=15, zorder=5)
    ax.plot([W - MARGIN + 8], [_Y(1190)], marker=">", markersize=10, color=GOLD_DK, zorder=5)
    _footer(fig, ax, data.get("source", ""))


def _slide_section(fig, ax, sec, photo_img=None):
    yb = _two_tone_title(fig, ax, sec.get("titre", ""), sec.get("titre2", ""),
                         y_top=150, fs=70)
    yb += 8
    ax.plot([MARGIN, MARGIN + 120], [_Y(yb), _Y(yb)], color=GOLD, lw=4, zorder=5)
    top = yb + 40

    if photo_img is not None:
        bh = 300
        _photo_band(ax, photo_img, top, bh)
        top += bh + 40

    points = [p for p in (sec.get("points") or []) if (p.get("label") or p.get("texte"))][:5]
    bottom = 150                              # marge basse (pied)
    row_h = max(120, ((H - bottom) - top) / max(1, len(points)))
    y = top
    for p in points:
        _point_block(fig, ax, MARGIN, y, CW, p, row_h)
        y += row_h
    _footer(fig, ax, sec.get("source", ""))


def _slide_takeaway(fig, ax, data):
    F = fig._F
    _two_tone_title(fig, ax, "À RETENIR", "", y_top=180, fs=78)
    ax.plot([MARGIN, MARGIN + 120], [_Y(290), _Y(290)], color=GOLD, lw=4, zorder=5)

    insight = (data.get("insight") or "").strip()
    # encadré callout
    ax.add_patch(FancyBboxPatch((MARGIN, _Y(720)), CW, 380,
                 boxstyle="round,pad=0,rounding_size=24", facecolor="#FFFFFF",
                 edgecolor=GOLD, lw=2, zorder=3, alpha=0.6))
    _draw_icon(ax, "bouclier", "", "", MARGIN + 70, _Y(420), R=46)
    words = _rich_words(insight, data.get("insight_fort"))
    _flow_rich(fig, ax, MARGIN + 160, 392, CW - 200, words, F["body_md"], 30, 42, base=NAVY)

    src = (data.get("source") or "").strip()
    if src:
        ax.text(MARGIN, _Y(800), f"Source : {src}", ha="left", va="top", color=NAVY_SOFT,
                fontproperties=F["body_sb"], fontsize=16, zorder=5)
    ax.text(MARGIN, _Y(860), "SUIVEZ @HK.MÉDIA POUR VOS DÉCRYPTAGES", ha="left", va="top",
            color=GOLD_DK, fontproperties=F["body_sb"], fontsize=15, zorder=5)
    _footer(fig, ax, data.get("source", ""))


# ── Bandeau photo ────────────────────────────────────────────────────────────
def _photo_band(ax, pil_img, y_top, bh):
    """Place une image PIL en bandeau pleine largeur de contenu, recadrée 'cover'."""
    try:
        import numpy as np
        img = pil_img.convert("RGB")
        tw, th = CW, bh
        iw, ih = img.size
        scale = max(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh))
        left = (nw - tw) // 2
        top = (nh - th) // 2
        img = img.crop((left, top, left + tw, top + th))
        ax.imshow(np.asarray(img), extent=(MARGIN, MARGIN + CW, _Y(y_top + bh), _Y(y_top)),
                  zorder=3, aspect="auto")
        ax.add_patch(Rectangle((MARGIN, _Y(y_top + bh)), CW, bh, fill=False,
                     edgecolor=NAVY, lw=2, zorder=4))
    except Exception as e:
        print(f"[DECRYPT] bandeau photo KO ({type(e).__name__}: {e})")


def _fetch_photo(query):
    """Récupère une photo concept (Unsplash/Pexels via image_fetch). None si indispo."""
    if not query:
        return None
    try:
        import image_fetch
        from PIL import Image
        url = image_fetch.fetch_photo_url({"title": query, "category": "general"})
        if not url:
            return None
        raw = image_fetch.download_image(url)
        return Image.open(io.BytesIO(raw)) if raw else None
    except Exception as e:
        print(f"[DECRYPT] photo indispo ({type(e).__name__})")
        return None


# ── Point d'entrée ───────────────────────────────────────────────────────────
def render_decryptage(data: dict) -> list[bytes]:
    """data = {titre, titre2, intro, source, insight, slides:[{titre,titre2,photo,points:
    [{label,texte,icon,fort}]}]}. Renvoie la liste des PNG (couverture → sections → à retenir)."""
    out = []

    def _safe(builder, *a):
        try:
            fig, ax = _fig()
            builder(fig, ax, *a)
            out.append(_finish(fig))
        except Exception as e:
            print(f"[DECRYPT] slide KO ({type(e).__name__}: {e})")

    _safe(_slide_cover, data)
    photos_left = 2                                   # plafond réseau : 2 bandeaux photo max
    for sec in (data.get("slides") or [])[:6]:
        img = None
        if sec.get("photo") and photos_left > 0:
            img = _fetch_photo(sec.get("photo"))
            if img is not None:
                photos_left -= 1
        _safe(_slide_section, sec, img)
    if (data.get("insight") or "").strip():
        _safe(_slide_takeaway, data)
    return out


if __name__ == "__main__":
    sample = {
        "titre": "LE BITCOIN", "titre2": "KÉZACO ?",
        "intro": "Tout comprendre en moins d'une minute : techno, promesse, limites.",
        "source": "HK Média", "cover_icons": ["reseau", "cadenas", "piece"],
        "insight": "Le Bitcoin n'est pas un actif refuge mais une assurance contre le "
                   "débasement monétaire — à intégrer avec mesure dans un portefeuille.",
        "insight_fort": "assurance contre le débasement monétaire",
        "slides": [
            {"titre": "LE BITCOIN", "titre2": "KÉZACO ?", "points": [
                {"label": "Technologie", "texte": "Blockchain décentralisée, sécurisée par le mécanisme de Proof-of-Work.", "icon": "reseau", "fort": "Proof-of-Work"},
                {"label": "Offre limitée", "texte": "21 millions de BTC maximum, garantissant une rareté absolue.", "icon": "cadenas", "fort": "rareté absolue"},
                {"label": "Promesse", "texte": "Indépendant des États et des politiques monétaires.", "icon": "banque"},
                {"label": "Utilités", "texte": "Moyen d'échange, actif spéculatif, réserve de valeur.", "icon": "echange"},
                {"label": "Performance", "texte": "+9 300 % sur 10 ans, mais volatilité 3x celle de l'or.", "icon": "hausse", "fort": "+9 300 % sur 10 ans"}]},
            {"titre": "LES", "titre2": "INCONVÉNIENTS", "points": [
                {"label": "Volatilité extrême", "texte": "Fluctuations de +/-30 % en quelques mois.", "icon": "volatilite", "fort": "+/-30 %"},
                {"label": "Risque de perte", "texte": "Possibilité de baisses brutales et prolongées.", "icon": "baisse"},
                {"label": "Sécurité", "texte": "Piratages, perte de clés privées, failles des plateformes.", "icon": "cadenas"},
                {"label": "Régulation", "texte": "Cadre légal en évolution (UE, États-Unis, Chine).", "icon": "document"}]},
            {"titre": "LES", "titre2": "AVANTAGES", "points": [
                {"label": "Portabilité", "texte": "Transférable rapidement et à moindre coût à l'international.", "icon": "globe"},
                {"label": "Diversification", "texte": "Diversifie un portefeuille traditionnel (actions, obligations, or).", "icon": "portefeuille"},
                {"label": "Innovation", "texte": "Exposé à la finance décentralisée (DeFi) et aux nouvelles technologies.", "icon": "ampoule"},
                {"label": "Liquidité", "texte": "Marché ouvert 24/7, avec une liquidité élevée.", "icon": "horloge", "fort": "24/7"}]},
        ],
    }
    slides = render_decryptage(sample)
    for i, png in enumerate(slides, 1):
        with open(f"test_decrypt_{i}.png", "wb") as f:
            f.write(png)
        print(f"Slide {i} : {len(png) // 1024} KB")
    print(f"{len(slides)} slides generes.")
