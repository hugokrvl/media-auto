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
DIGEST_CHARS = int(os.environ.get("GROQ_DIGEST_CHARS", "14000"))  # taille d'un morceau
# Pacing entre appels : 8b tolère 2s, 70b nécessite ≥7s (12 000 TPM / ~1 300 tok/appel)
PACE_SECONDS        = float(os.environ.get("GROQ_PACE_SECONDS", "2.2"))   # triage 8b
PACE_SECONDS_ENRICH = float(os.environ.get("GROQ_PACE_ENRICH",  "7.0"))   # enrichissement 70b
SCORE_KEEP = int(os.environ.get("GROQ_SCORE_KEEP", "6"))      # seuil de rétention

# ── Prompts ───────────────────────────────────────────────────────────────────
TRIAGE_SYSTEM = """Tu es rédacteur en chef d'un média économique sérieux, orienté vérité.
Tu juges vite si un article mérite d'être relayé sur les réseaux. Réponds UNIQUEMENT
en JSON valide, sans markdown ni commentaire."""

TRIAGE_PROMPT = """Évalue cet article pour un compte média français (finance, tech, actu, sport).

Critères PRIORITAIRES pour garder (score ≥ 6) :
- impact économique ou sociétal réel, pertinent pour un public français
- info vérifiable, fiable, issue d'une source reconnue
- actualité nationale ou internationale significative

À REJETER impérativement (score ≤ 4, keep=false) :
- promotionnel : offres, réductions, codes promo, abonnements ("-X% off", "deal", "discount")
- faits divers locaux sans portée nationale (accidents, arrestations isolées)
- people/lifestyle sans enjeu (célébrités, rumeurs)
- contenu hors sujet pour un public francophone (actualité hyperlocale US/UK sans impact global)

Critère BONUS (monte un peu le score, jamais baisser) :
- potentiel de visualisation de données (chiffres, comparaisons, tendances)

IMPORTANT : une actualité forte et fiable SANS chiffres reste pertinente (→ infographie).
Ne jette que ce qui est anecdotique, promotionnel, non vérifié ou sans intérêt réel.

Réponds en JSON EXACTEMENT ainsi :
{
  "score": <entier 0-10>,
  "verified": <true si info fiable et vérifiable, sinon false>,
  "keep": <true si score >= 6 ET verified, sinon false>,
  "category": "<finance|tech|general|sport|factcheck>",
  "reason": "<1 phrase courte>"
}

Article :
Titre: __TITLE__
Source: __SOURCE__
Résumé: __SUMMARY__"""

DIGEST_SYSTEM = """Tu condenses la transcription d'une vidéo en un résumé DENSE EN DONNÉES,
en français. Tu extrais en priorité : chiffres, pourcentages, montants, dates, comparaisons,
tendances, classements et faits vérifiables. Tu ignores le bavardage. Tu n'inventes RIEN.
Réponds UNIQUEMENT en JSON valide."""

DIGEST_PROMPT = """Transcription (ou extrait) de la vidéo « __TITLE__ ».
Extrais TOUTES les données chiffrées et faits clés, de façon compacte et factuelle.
JSON EXACTEMENT : {"digest": "<résumé dense en données, en français, max 1200 caractères>"}

Transcription :
__BODY__"""

ENRICH_SYSTEM = """Tu es un journaliste de data-visualisation. À partir d'un article
retenu, tu prépares une infographie en FRANÇAIS avec des données structurées réelles.
Tu n'inventes JAMAIS de chiffres. Réponds UNIQUEMENT en JSON valide."""

ENRICH_PROMPT = """Prépare l'infographie de cet article. JSON EXACTEMENT ainsi :
{
  "title_fr": "<titre court accrocheur EN FRANÇAIS, max 75 caractères>",
  "subtitle_fr": "<sous-titre court : contexte/période/unité, max 50 caractères>",
  "chart_type": "<kpi|donut|bar|courbe|infographic>",
  "chart_data": [<selon chart_type, voir règles>],
  "key_points": [<2-4 points clés EN FRANÇAIS si chart_type=infographic, sinon []>]
}

RÈGLES chart_data (données RÉELLES tirées de l'article) :
- "kpi"    : 2-3 chiffres clés. [{"label":"Inflation","value":"3.2","unit":"%","evolution":"-0.4"}]
- "donut"  : répartition/parts. [{"label":"Apple","value":28},{"label":"Samsung","value":22}]
- "bar"    : comparaison/classement. [{"label":"OpenAI","value":40},{"label":"xAI","value":18}]
- "courbe" : évolution temporelle. [{"label":"Jan","value":92},{"label":"Fév","value":88}]
- "infographic" : DERNIER RECOURS SEULEMENT -> chart_data: [], remplis key_points.

ORDRE DE PRIORITÉ POUR LE CHOIX DU TYPE (applique le premier qui est possible) :
1. "kpi"     → s'il y a AU MOINS 1 chiffre clé (montant, %, taux, score, rang…)
2. "bar"     → s'il y a 2+ valeurs comparables (pays, entreprises, produits…)
3. "donut"   → s'il y a une répartition en parts dont le total est 100 % ou proche
4. "courbe"  → s'il y a une série temporelle (mois, trimestres, années…)
5. "infographic" → UNIQUEMENT si l'article est 100 % qualitatif, sans aucun chiffre ni donnée chiffrable

Cherche activement des chiffres même implicites : classements, dates, durées, effectifs, budgets.
"infographic" ne doit représenter qu'une minorité des posts.

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


def _digest_transcript(article: dict) -> str:
    """Map-reduce : compresse la transcription complète d'une vidéo en un résumé
    dense en données, via le modèle pas cher (gros quota). '' si rien/échec."""
    full = article.get("transcript") or ""
    if not full.strip():
        return ""
    chunks = [full[i:i + DIGEST_CHARS] for i in range(0, len(full), DIGEST_CHARS)][:4]
    parts = []
    for ch in chunks:
        try:
            prompt = (DIGEST_PROMPT
                      .replace("__TITLE__", article.get("title", ""))
                      .replace("__BODY__", ch))
            d = _chat(DIGEST_MODEL, DIGEST_SYSTEM, prompt, max_tokens=500)
            txt = (d.get("digest") or "").strip()
            if txt:
                parts.append(txt)
        except Exception as e:
            print(f"[ANALYZER] Digest KO ({type(e).__name__}) sur '{article.get('title','')[:40]}'")
        time.sleep(PACE_SECONDS)
    return " ".join(parts)[:2500]


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
    return _chat(GENERATION_MODEL, ENRICH_SYSTEM, prompt, max_tokens=500)


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
    })
    return article


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
    digested = 0
    for article in selected:
        # Vidéo retenue avec transcription complète -> on la "digère" d'abord
        # (modèle pas cher) pour donner au 70b TOUTES les données sans exploser ses tokens
        digest = None
        if article.get("transcript") and digested < MAX_DIGEST:
            digest = _digest_transcript(article)
            if digest:
                digested += 1
                print(f"[ANALYZER] Vidéo digérée ({len(digest)} car.) : {article.get('title','')[:45]}")
        try:
            e = _enrich_one(article, summary_override=digest)
            article.update({
                "title_fr": e.get("title_fr") or article.get("title", ""),
                "subtitle_fr": e.get("subtitle_fr", ""),
                "chart_type": e.get("chart_type", "infographic"),
                "chart_data": e.get("chart_data", []),
                "key_points": e.get("key_points", []),
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

    print(f"[ANALYZER] {len(enriched)} articles prêts (triage {TRIAGE_MODEL} → "
          f"génération {GENERATION_MODEL})")
    return enriched


if __name__ == "__main__":
    from scraper import fetch_articles
    arts = fetch_articles()
    for a in analyze_articles(arts):
        print(f"[{a.get('score')}/10] [{a.get('chart_type')}] {a.get('title_fr', a['title'])[:70]}")
        print(f"  → {a.get('reason', '')}")
