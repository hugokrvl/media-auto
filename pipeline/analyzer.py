"""
Analyse des articles avec Groq — architecture à 2 modèles (quota-safe).

  PASSE 1 — TRIAGE   (llama-3.1-8b-instant, 500k tokens/jour)
    Sur TOUS les articles (~60) : score, vérification, catégorie, garder/jeter.
    Sortie minimale -> coût faible -> on reste large sur les quotas.

  PASSE 2 — ENRICHISSEMENT  (llama-3.3-70b-versatile, qualité)
    Seulement sur les articles retenus (≤ ~12) : titre FR, sous-titre, type de
    graphique + données structurées. La qualité là où elle compte vraiment.

Les captions finales (generator.py) restent sur le 70b.
Garde-fous quota : pacing entre appels + back-off automatique sur rate-limit.
Réglages via variables d'env : GROQ_TRIAGE_MODEL, GROQ_MODEL, GROQ_MAX_ANALYZE,
GROQ_MAX_ENRICH, GROQ_PACE_SECONDS.
"""

import json
import os
import time
from groq import Groq

import article_fetch

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Modèles (surchageables par env)
TRIAGE_MODEL = os.environ.get("GROQ_TRIAGE_MODEL", "llama-3.1-8b-instant")
GENERATION_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Modèle qui "digère" les longues transcriptions vidéo (gros quota, pas cher).
# 8b = 500k tokens/jour. Pour des vidéos très longues, un modèle à plus haut TPM
# (ex. meta-llama/llama-4-scout-17b-16e-instruct, 30k TPM) est préférable.
DIGEST_MODEL = os.environ.get("GROQ_DIGEST_MODEL", "llama-3.1-8b-instant")

# Volumes & cadence (surchargeables par env)
MAX_ANALYZE = int(os.environ.get("GROQ_MAX_ANALYZE", "60"))   # triés en passe 1
MAX_ENRICH = int(os.environ.get("GROQ_MAX_ENRICH", "10"))     # enrichis en passe 2 (70b, 12k TPM)
MAX_DIGEST = int(os.environ.get("GROQ_MAX_DIGEST", "5"))      # vidéos digérées/nuit
MAX_FULLTEXT = int(os.environ.get("FULLTEXT_MAX", "10"))      # articles lus EN ENTIER puis digérés/nuit
DIGEST_CHARS = int(os.environ.get("GROQ_DIGEST_CHARS", "14000"))  # taille d'un morceau
# Pacing entre appels : 8b tolère 2s, 70b nécessite ≥7s (12 000 TPM / ~1 300 tok/appel)
PACE_SECONDS        = float(os.environ.get("GROQ_PACE_SECONDS", "2.2"))   # triage 8b
PACE_SECONDS_ENRICH = float(os.environ.get("GROQ_PACE_ENRICH",  "7.0"))   # enrichissement 70b
SCORE_KEEP = int(os.environ.get("GROQ_SCORE_KEEP", "6"))      # seuil de rétention

# ── Prompts ───────────────────────────────────────────────────────────────────
TRIAGE_SYSTEM = """Tu es rédacteur en chef d'un média économique sérieux, orienté vérité.
Tu juges vite si un article mérite d'être relayé sur les réseaux. Réponds UNIQUEMENT
en JSON valide, sans markdown ni commentaire."""

TRIAGE_PROMPT = """Évalue cet article pour un média français ÉCONOMIE / TECH / IA / BLOCKCHAIN / QUANTIQUE.

Critères PRIORITAIRES pour garder (score ≥ 6) :
- impact économique, technologique ou scientifique réel et significatif
- sujets cœur de ligne : intelligence artificielle, cryptomonnaies/blockchain,
  informatique quantique, grandes entreprises tech, marchés, innovation
- info vérifiable, fiable, issue d'une source reconnue

À REJETER impérativement (score ≤ 4, keep=false) :
- promotionnel : offres, réductions, codes promo, abonnements ("-X% off", "deal", "discount")
- faits divers locaux sans portée nationale (accidents, arrestations isolées)
- people/lifestyle sans enjeu (célébrités, rumeurs)
- contenu hors sujet pour un public francophone (actualité hyperlocale US/UK sans impact global)

Critère DÉTERMINANT (ce flux est une rubrique DATA / ÉTUDES, pas l'actu chaude) :
- l'article doit contenir (ou permettre d'extraire) des CHIFFRES exploitables :
  montants, %, taux, classements, parts de marché, séries temporelles, comparaisons.
- monte NETTEMENT le score quand la donnée est riche et chiffrable.

IMPORTANT : l'actualité « chaude » sans angle chiffré est traitée AILLEURS (moteur breaking).
Ici, REJETTE (keep=false) un article fort mais 100 % qualitatif, sans aucun chiffre :
il ne ferait qu'une liste de puces, pas une étude. Ne garde que ce qui se met en graphe.

Réponds en JSON EXACTEMENT ainsi :
{
  "score": <entier 0-10>,
  "verified": <true si info fiable et vérifiable, sinon false>,
  "keep": <true si score >= 6 ET verified, sinon false>,
  "category": "<finance|tech|ia|crypto|quantique|general|sport|factcheck>",
  "reason": "<1 phrase courte>"
}

Article :
Titre: __TITLE__
Source: __SOURCE__
Résumé: __SUMMARY__"""

DIGEST_SYSTEM = """Tu condenses un texte (article complet OU transcription vidéo) en un résumé
DENSE EN DONNÉES, en français. Tu extrais en priorité : chiffres, pourcentages, montants, dates,
comparaisons, tendances, classements et faits vérifiables. Tu ignores le bavardage. Tu n'inventes
RIEN. Réponds UNIQUEMENT en JSON valide."""

DIGEST_PROMPT = """Texte (ou extrait) de « __TITLE__ ».
Extrais TOUTES les données chiffrées et faits clés, de façon compacte et factuelle.
JSON EXACTEMENT : {"digest": "<résumé dense en données, en français, max 1200 caractères>"}

Texte :
__BODY__"""

ENRICH_SYSTEM = """Tu es un journaliste de data-visualisation. À partir d'un article
retenu, tu prépares une infographie en FRANÇAIS avec des données structurées réelles.
Tu n'inventes JAMAIS de chiffres. Réponds UNIQUEMENT en JSON valide."""

ENRICH_PROMPT = """Prépare une PETITE ÉTUDE DATA (carrousel) à partir de cet article.
JSON EXACTEMENT ainsi :
{
  "title_fr": "<titre court, ANGLE CHIFFRÉ, EN FRANÇAIS, max 75 caractères>",
  "subtitle_fr": "<source + période + unité, max 50 caractères>",
  "chart_type": "<kpi|donut|bar|courbe|infographic>",
  "chart_data": [<selon chart_type, voir règles>],
  "key_points": [<2-4 faits clés CHIFFRÉS et factuels EN FRANÇAIS, TOUJOURS remplis>],
  "insight": "<le VERDICT en 1 phrase factuelle tirée des chiffres, EN FRANÇAIS, max 160 caractères>"
}

RÈGLES chart_data (données RÉELLES tirées de l'article, JAMAIS inventées) :
- "kpi"    : 2-3 chiffres clés. [{"label":"Inflation","value":"3.2","unit":"%","evolution":"-0.4"}]
- "donut"  : répartition/parts. [{"label":"Apple","value":28},{"label":"Samsung","value":22}]
- "bar"    : comparaison/classement. [{"label":"OpenAI","value":40},{"label":"xAI","value":18}]
- "courbe" : évolution temporelle. [{"label":"Jan","value":92},{"label":"Fév","value":88}]
- "infographic" : SEULEMENT si l'article n'a STRICTEMENT aucun chiffre -> chart_data: [].

ORDRE DE PRIORITÉ POUR LE CHOIX DU TYPE (applique le premier qui est possible) :
1. "kpi"     → s'il y a AU MOINS 1 chiffre clé (montant, %, taux, score, rang…)
2. "bar"     → s'il y a 2+ valeurs comparables (pays, entreprises, produits…)
3. "donut"   → s'il y a une répartition en parts dont le total est 100 % ou proche
4. "courbe"  → s'il y a une série temporelle (mois, trimestres, années…)
5. "infographic" → DERNIER RECOURS (cet article sera écarté du flux data).

Cherche activement les chiffres même implicites : classements, dates, durées, effectifs, budgets.
"insight" = une conclusion HONNÊTE et vérifiable tirée des données, jamais une exagération.

Article :
Titre: __TITLE__
Source: __SOURCE__
Résumé: __SUMMARY__"""


# ── Appel Groq robuste (back-off sur rate-limit) ──────────────────────────────
def _chat(model: str, system: str, user: str, max_tokens: int, retries: int = 4) -> dict:
    delay = 15.0  # backoff initial plus généreux (5→15s) pour le 70b à 12k TPM
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.2,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content.strip())
        except Exception as e:
            msg = str(e).lower()
            is_rate = "rate" in msg or "429" in msg or "quota" in msg
            if is_rate and attempt < retries - 1:
                print(f"[ANALYZER] Rate-limit {model}, pause {delay:.0f}s "
                      f"(essai {attempt + 1}/{retries})")
                time.sleep(delay)
                delay *= 2  # back-off exponentiel
                continue
            raise


def _fill(prompt: str, article: dict, summary_len: int) -> str:
    return (prompt
            .replace("__TITLE__", article.get("title", ""))
            .replace("__SOURCE__", article.get("source", ""))
            .replace("__SUMMARY__", (article.get("summary", "") or "")[:summary_len]))


# ── Passes ────────────────────────────────────────────────────────────────────
def _triage_one(article: dict) -> dict:
    return _chat(TRIAGE_MODEL, TRIAGE_SYSTEM,
                 _fill(TRIAGE_PROMPT, article, 350), max_tokens=180)


def _digest_text(title: str, text: str, max_chunks: int = 4, cap: int = 2500) -> str:
    """Map-reduce : compresse un texte long (article complet OU transcription) en un
    résumé dense en données, via le modèle pas cher (gros quota). '' si rien/échec.
    Le 70b ne verra QUE ce condensé → tous les chiffres captés, tokens 70b préservés.
    `max_chunks` : nombre de morceaux digérés ; `cap` : longueur max du condensé final."""
    text = (text or "").strip()
    if not text:
        return ""
    chunks = [text[i:i + DIGEST_CHARS] for i in range(0, len(text), DIGEST_CHARS)][:max_chunks]
    parts = []
    for ch in chunks:
        try:
            prompt = DIGEST_PROMPT.replace("__TITLE__", title).replace("__BODY__", ch)
            d = _chat(DIGEST_MODEL, DIGEST_SYSTEM, prompt, max_tokens=500)
            txt = (d.get("digest") or "").strip()
            if txt:
                parts.append(txt)
        except Exception as e:
            print(f"[ANALYZER] Digest KO ({type(e).__name__}) sur '{title[:40]}'")
        time.sleep(PACE_SECONDS)
    return " ".join(parts)[:cap]


def _digest_transcript(article: dict) -> str:
    """Compat : digère la transcription d'une vidéo (utilisé par reprocess.py)."""
    return _digest_text(article.get("title", ""), article.get("transcript") or "")


def _enrich_one(article: dict, summary_override: str = None) -> dict:
    """Enrichissement 70b. Si summary_override (digest vidéo) est fourni, on l'utilise
    à la place du résumé court et on autorise un peu plus de contexte."""
    if summary_override:
        prompt = (ENRICH_PROMPT
                  .replace("__TITLE__", article.get("title", ""))
                  .replace("__SOURCE__", article.get("source", ""))
                  .replace("__SUMMARY__", summary_override[:1600]))
    else:
        prompt = _fill(ENRICH_PROMPT, article, 600)
    return _chat(GENERATION_MODEL, ENRICH_SYSTEM, prompt, max_tokens=600)


def enrich_with_transcript(article: dict) -> dict:
    """Regénère un article à partir de sa transcription complète (collage manuel sur
    le site). Digest (modèle pas cher) → enrichissement (70b). Utilisé par reprocess.py."""
    digest = _digest_transcript(article) if article.get("transcript") else None
    try:
        e = _enrich_one(article, summary_override=digest)
    except Exception as ex:
        print(f"[ANALYZER] Enrichissement transcript KO: {type(ex).__name__}")
        e = {}
    article.update({
        "title_fr": e.get("title_fr") or article.get("title", ""),
        "subtitle_fr": e.get("subtitle_fr", ""),
        "chart_type": e.get("chart_type", "infographic"),
        "chart_data": e.get("chart_data", []),
        "key_points": e.get("key_points", []),
        "insight": e.get("insight", ""),
    })
    return article


# ── Décryptage : texte collé → carrousel long (sections) ──────────────────────
# Icônes line-art disponibles dans le renderer clair (decrypt_light.ICONS).
DECRYPT_ICONS = ("reseau, cadenas, banque, echange, hausse, baisse, barres, bouclier, globe, "
                 "ampoule, portefeuille, cible, alerte, horloge, piece, groupe, document, "
                 "balance, bitcoin")

DECRYPT_SYS = ("Tu es journaliste-vulgarisateur. Tu transformes un contenu (transcription "
               "vidéo, article…) en un DÉCRYPTAGE visuel en carrousel : des slides au titre "
               "fort, chaque point illustré d'une icône et d'un chiffre/mot-clé à surligner. "
               "Tout EN FRANÇAIS, FACTUEL, tu n'inventes RIEN. Réponds UNIQUEMENT en JSON valide.")

DECRYPT_PROMPT = """Transforme ce contenu en un DÉCRYPTAGE pour carrousel Instagram (3 à 5 slides).
JSON EXACTEMENT :
{
  "titre": "<ligne 1 du titre principal, MAJUSCULES, ≤14 car.>",
  "titre2": "<ligne 2 du titre principal, MAJUSCULES, ≤16 car.>",
  "intro": "<phrase d'accroche EN FRANÇAIS, ≤90 car.>",
  "slides": [
    {
      "titre": "<ligne 1 du titre de slide, MAJUSCULES, ≤14 car.>",
      "titre2": "<ligne 2, MAJUSCULES, ≤16 car. (peut être vide)>",
      "photo": "<requête photo EN ANGLAIS si une vraie photo aide (ex: 'gold bitcoin coins'), sinon ''>",
      "points": [
        {
          "label": "<2-4 mots, l'idée>",
          "texte": "<fait EN FRANÇAIS, ≤95 car., chiffré si possible>",
          "icon": "<UNE icône parmi: __ICONS__>",
          "fort": "<le chiffre OU mot-clé À SURLIGNER, copié EXACTEMENT depuis 'texte', sinon ''>"
        }
      ]
    }
  ],
  "insight": "<conclusion à retenir, 1 phrase, ≤150 car.>",
  "insight_fort": "<phrase-clé à surligner, copiée depuis 'insight', sinon ''>"
}
RÈGLES : 3 à 5 slides ; 3-5 points par slide ; "icon" OBLIGATOIRE et choisi dans la liste ;
"fort" doit être un EXTRAIT EXACT de "texte" (sinon "") ; "photo" sur 2 slides MAXIMUM (sinon "").
Garde les chiffres. N'invente rien. Titres COURTS et percutants.

Contenu :
__BODY__"""


def enrich_decryptage(article: dict) -> dict:
    """Texte collé → décryptage CLAIR (titre bicolore, icônes, surlignage). Digest (8b,
    token-safe) pour les longs textes, puis structuration (70b). Utilisé par
    reprocess.run_generate (création depuis le site, rendu par decrypt_light)."""
    text = (article.get("pending_transcript") or article.get("transcript")
            or article.get("summary") or "").strip()
    if not text:
        return article
    # Texte long → on le digère (découpe + extraction par le 8b) avant le 70b.
    body = (_digest_text(article.get("title", ""), text, max_chunks=6, cap=5000)
            if len(text) > 4000 else text)
    prompt = DECRYPT_PROMPT.replace("__ICONS__", DECRYPT_ICONS).replace(
        "__BODY__", (body or text)[:5000])
    try:
        e = _chat(GENERATION_MODEL, DECRYPT_SYS, prompt, max_tokens=1500)
    except Exception as ex:
        print(f"[ANALYZER] Décryptage KO: {type(ex).__name__}: {ex}")
        e = {}

    # Nettoyage des slides + points
    slides = []
    for s in (e.get("slides") or [])[:5]:
        if not isinstance(s, dict):
            continue
        pts = []
        for p in (s.get("points") or [])[:5]:
            if not isinstance(p, dict):
                continue
            txt = (p.get("texte") or p.get("text") or "").strip()
            if not (p.get("label") or txt):
                continue
            pts.append({
                "label": (p.get("label") or "").strip()[:34],
                "texte": txt[:110],
                "icon": (p.get("icon") or "").strip().lower(),
                "fort": (p.get("fort") or "").strip()[:60],
            })
        if pts:
            slides.append({
                "titre": (s.get("titre") or "").strip()[:18],
                "titre2": (s.get("titre2") or "").strip()[:20],
                "photo": (s.get("photo") or "").strip()[:60],
                "points": pts,
            })

    titre = (e.get("titre") or "").strip()[:18]
    titre2 = (e.get("titre2") or "").strip()[:20]
    if not titre and slides:                          # repli depuis la 1re slide / le titre brut
        titre, titre2 = slides[0]["titre"], slides[0]["titre2"]
    title_fr = (f"{titre} {titre2}".strip() or article.get("title") or "Décryptage")[:90]

    article.update({
        "decrypt_data": {
            "titre": titre or title_fr.upper()[:18],
            "titre2": titre2,
            "intro": (e.get("intro") or "").strip()[:100],
            "insight": (e.get("insight") or "").strip()[:160],
            "insight_fort": (e.get("insight_fort") or "").strip()[:60],
            "cover_icons": [p["icon"] for s in slides for p in s["points"]
                            if p["icon"]][:3] or ["reseau", "cadenas", "piece"],
            "slides": slides,
            "source": (article.get("source") or "").strip(),
        },
        "title_fr": title_fr,
        "subtitle_fr": (e.get("intro") or "").strip()[:50],
        "sections": slides,                            # compat (legacy)
        "insight": (e.get("insight") or "").strip()[:170],
        "chart_type": "decryptage",
        # key_points agrégés → captions (generator)
        "key_points": [p["texte"] for s in slides for p in s["points"]][:6],
    })
    return article


def _clean_slides(raw_slides) -> list[dict]:
    """Nettoie/borne une liste de slides {titre,titre2,photo,points[{label,texte,icon,fort}]}."""
    slides = []
    for s in (raw_slides or [])[:5]:
        if not isinstance(s, dict):
            continue
        pts = []
        for p in (s.get("points") or [])[:5]:
            if not isinstance(p, dict):
                continue
            txt = (p.get("texte") or p.get("text") or "").strip()
            if not (p.get("label") or txt):
                continue
            pts.append({"label": (p.get("label") or "").strip()[:34], "texte": txt[:110],
                        "icon": (p.get("icon") or "").strip().lower(),
                        "fort": (p.get("fort") or "").strip()[:60]})
        if pts:
            slides.append({"titre": (s.get("titre") or "").strip()[:18],
                           "titre2": (s.get("titre2") or "").strip()[:20],
                           "photo": (s.get("photo") or "").strip()[:60], "points": pts})
    return slides


SPLIT_SYS = ("Tu es chef d'édition. Le texte reçu peut couvrir PLUSIEURS sujets sans rapport. "
             "Tu le découpes en POSTS DISTINCTS : 1 SUJET = 1 POST (jamais deux sujets mélangés). "
             "Un sujet RICHE (≥4 faits) → décryptage ; un sujet MINCE (1-2 faits) → brève "
             "(titre + 1 phrase + photo). EN FRANÇAIS, FACTUEL, tu n'inventes RIEN. JSON valide.")

SPLIT_PROMPT = """Découpe ce contenu en 1 à 4 POSTS, UN PAR SUJET distinct.
JSON EXACTEMENT :
{
  "posts": [
    {
      "format": "decryptage",
      "titre": "<MAJUSCULES, ≤14 car.>", "titre2": "<MAJUSCULES, ≤16 car.>",
      "intro": "<accroche EN FRANÇAIS, ≤90 car.>",
      "slides": [
        {"titre": "<MAJ ≤14>", "titre2": "<MAJ ≤16>", "photo": "<requête photo EN si utile sinon ''>",
         "points": [{"label": "<2-4 mots>", "texte": "<fait ≤95 car.>",
                     "icon": "<UNE icône parmi: __ICONS__>", "fort": "<extrait EXACT de texte ou ''>"}]}
      ],
      "insight": "<conclusion ≤150 car.>", "insight_fort": "<extrait de insight ou ''>"
    },
    {
      "format": "breve",
      "titre": "<MAJ ≤14>", "titre2": "<MAJ ≤16>",
      "phrase": "<le fait en 1 phrase EN FRANÇAIS, ≤140 car.>", "fort": "<extrait de phrase ou ''>",
      "photo": "<requête photo EN (ex: 'yann lecun portrait')>"
    }
  ]
}
RÈGLES : 1 SUJET = 1 POST. 1 à 4 posts. Décryptage = 3-4 slides, 3-5 points/slide, "icon"
OBLIGATOIRE (liste), "fort" = extrait EXACT. Brève quand peu de matière (1 actu ponctuelle).
Garde les chiffres. Titres COURTS et percutants. N'invente RIEN.

Contenu :
__BODY__"""


def split_into_posts(article: dict) -> list[dict]:
    """Texte collé (pouvant couvrir plusieurs sujets) → LISTE de posts distincts (1 sujet =
    1 post). Chaque post : format 'decryptage' (decrypt_data) ou 'breve' (breve_data).
    Digest (8b) token-safe → 1 appel de structuration (70b). Repli sur un décryptage unique."""
    text = (article.get("pending_transcript") or article.get("transcript")
            or article.get("summary") or "").strip()
    if not text:
        return []
    body = (_digest_text(article.get("title", ""), text, max_chunks=8, cap=6000)
            if len(text) > 4000 else text)
    prompt = SPLIT_PROMPT.replace("__ICONS__", DECRYPT_ICONS).replace("__BODY__", (body or text)[:6000])
    try:
        e = _chat(GENERATION_MODEL, SPLIT_SYS, prompt, max_tokens=3000)
    except Exception as ex:
        print(f"[ANALYZER] Découpe KO: {type(ex).__name__}: {ex}")
        e = {}

    src = (article.get("source") or "").strip()
    cat = article.get("category") or "general"
    out = []
    for po in (e.get("posts") or [])[:4]:
        if not isinstance(po, dict):
            continue
        fmt = (po.get("format") or "decryptage").strip().lower()
        titre = (po.get("titre") or "").strip()[:18]
        titre2 = (po.get("titre2") or "").strip()[:20]
        title_fr = (f"{titre} {titre2}".strip() or "Sujet")[:90]

        if fmt == "breve":
            phrase = (po.get("phrase") or "").strip()[:160]
            if not (titre or phrase):
                continue
            out.append({
                "format": "breve",
                "breve_data": {"titre": titre or title_fr.upper()[:18], "titre2": titre2,
                               "phrase": phrase, "fort": (po.get("fort") or "").strip()[:60],
                               "photo": (po.get("photo") or "").strip()[:60], "source": src},
                "title_fr": title_fr, "source": src, "category": cat,
                "chart_type": "breve", "insight": phrase, "key_points": [phrase],
            })
        else:
            slides = _clean_slides(po.get("slides"))
            if not slides:
                continue
            if not titre:
                titre, titre2 = slides[0]["titre"], slides[0]["titre2"]
                title_fr = (f"{titre} {titre2}".strip() or "Décryptage")[:90]
            out.append({
                "format": "decryptage",
                "decrypt_data": {"titre": titre or title_fr.upper()[:18], "titre2": titre2,
                                 "intro": (po.get("intro") or "").strip()[:100],
                                 "insight": (po.get("insight") or "").strip()[:160],
                                 "insight_fort": (po.get("insight_fort") or "").strip()[:60],
                                 "cover_icons": [p["icon"] for s in slides for p in s["points"]
                                                 if p["icon"]][:3] or ["reseau", "cadenas", "piece"],
                                 "slides": slides, "source": src},
                "title_fr": title_fr, "source": src, "category": cat, "chart_type": "decryptage",
                "insight": (po.get("insight") or "").strip()[:170],
                "key_points": [p["texte"] for s in slides for p in s["points"]][:6],
            })

    # Repli : si la découpe n'a rien donné, on retombe sur UN décryptage (comportement d'avant).
    if not out:
        art2 = dict(article)
        enrich_decryptage(art2)
        if art2.get("decrypt_data"):
            out.append({"format": "decryptage", "decrypt_data": art2["decrypt_data"],
                        "title_fr": art2.get("title_fr") or "Décryptage", "source": src,
                        "category": cat, "chart_type": "decryptage",
                        "insight": art2.get("insight", ""),
                        "key_points": art2.get("key_points", [])})
    print(f"[ANALYZER] Découpe → {len(out)} post(s) "
          f"({sum(p['format']=='decryptage' for p in out)} décryptage / "
          f"{sum(p['format']=='breve' for p in out)} brève)")
    return out


def analyze_articles(articles: list[dict], max_to_analyze: int = None) -> list[dict]:
    """Triage (8b) sur tous, puis enrichissement (70b) sur les meilleurs retenus."""
    limit = max_to_analyze or MAX_ANALYZE
    to_analyze = articles[:limit]

    # PASSE 1 — triage léger (modèle volume)
    kept = []
    for article in to_analyze:
        try:
            t = _triage_one(article)
            if t.get("score", 0) >= SCORE_KEEP and t.get("verified") and t.get("keep", True):
                article.update({
                    "score": t.get("score", 0),
                    "verified": t.get("verified", False),
                    "category": t.get("category", article.get("category", "general")),
                    "reason": t.get("reason", ""),
                })
                kept.append(article)
        except Exception as e:
            print(f"[ANALYZER] Triage KO '{article.get('title','')[:45]}': {type(e).__name__}")
        time.sleep(PACE_SECONDS)

    kept.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected = kept[:MAX_ENRICH]
    print(f"[ANALYZER] Triage : {len(kept)}/{len(to_analyze)} retenus "
          f"→ enrichissement des {len(selected)} meilleurs ({GENERATION_MODEL})")

    # PASSE 2 — enrichissement qualité (modèle 70b) sur les retenus
    enriched = []
    vid_digested = art_digested = 0
    for article in selected:
        # On donne au 70b le MAXIMUM de données SANS exploser son quota : on ne lui passe
        # jamais le texte brut, mais un DIGEST produit par le modèle pas cher (8b, gros quota).
        #   - vidéo  -> digest de la transcription complète
        #   - sinon  -> on tente le TEXTE COMPLET de l'article (article_fetch) puis digest
        # Repli auto : pas de texte (paywall / Google News / blocage) -> digest=None ->
        # _enrich_one retombe sur le résumé RSS court. ÉQUITÉ : on est APRÈS le triage,
        # donc lire un article en entier ne change PAS son score (aucun avantage de sélection).
        digest = None
        if article.get("transcript") and vid_digested < MAX_DIGEST:
            digest = _digest_transcript(article)
            if digest:
                vid_digested += 1
                print(f"[ANALYZER] Vidéo digérée ({len(digest)} car.) : {article.get('title','')[:45]}")
        elif not article.get("transcript") and art_digested < MAX_FULLTEXT:
            full = article_fetch.fetch_fulltext(article.get("url", ""))
            if full:
                digest = _digest_text(article.get("title", ""), full)
                if digest:
                    art_digested += 1
                    print(f"[ANALYZER] Article complet lu+digéré ({len(full)}→{len(digest)} car.) : {article.get('title','')[:45]}")
        try:
            e = _enrich_one(article, summary_override=digest)
            article.update({
                "title_fr": e.get("title_fr") or article.get("title", ""),
                "subtitle_fr": e.get("subtitle_fr", ""),
                "chart_type": e.get("chart_type", "infographic"),
                "chart_data": e.get("chart_data", []),
                "key_points": e.get("key_points", []),
                "insight": e.get("insight", ""),
            })
            enriched.append(article)
        except Exception as e:
            print(f"[ANALYZER] Enrichissement KO '{article.get('title','')[:45]}': {type(e).__name__}")
            # On garde quand même l'article avec un rendu de repli (infographic)
            article.setdefault("title_fr", article.get("title", ""))
            article.setdefault("chart_type", "infographic")
            article.setdefault("chart_data", [])
            article.setdefault("key_points", [])
            enriched.append(article)
        time.sleep(PACE_SECONDS_ENRICH)  # 70b : 7s min pour rester sous 12k TPM

    print(f"[ANALYZER] {len(enriched)} articles prêts "
          f"({art_digested} lus en entier, {vid_digested} vidéos digérées ; "
          f"triage {TRIAGE_MODEL} → génération {GENERATION_MODEL})")
    return enriched


if __name__ == "__main__":
    from scraper import fetch_articles
    arts = fetch_articles()
    for a in analyze_articles(arts):
        print(f"[{a.get('score')}/10] [{a.get('chart_type')}] {a.get('title_fr', a['title'])[:70]}")
        print(f"  → {a.get('reason', '')}")
