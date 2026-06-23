"""
Génère les textes de posts pour chaque réseau via Groq.
Respecte les contraintes de chaque plateforme.
"""

import json
import os

# Client Groq PARESSEUX : on ne le crée (et n'exige GROQ_API_KEY) qu'au moment où on
# en a vraiment besoin → le moteur breaking peut tourner sur Mistral seul, sans Groq.
_client = None


def _groq():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client

# Chemin NORMAL des captions = Mistral/Gemini (qualité pro), voir generate_captions().
# Ceci n'est que le REPLI Groq, utilisé seulement si Mistral ET Gemini sont indisponibles.
# On prend alors le 70b (meilleure copy). Quota-safe en prod : 1 run/nuit ≈ ~48k/100k tokens
# 70b même en repli. Mettre GROQ_CAPTION_MODEL="llama-3.1-8b-instant" pour économiser si tu
# relances le pipeline complet plusieurs fois le même jour (tests).
GENERATION_MODEL = os.environ.get("GROQ_CAPTION_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """Tu es le rédacteur en chef d'un média économique et tech sérieux et crédible.
Tu rédiges des légendes SOBRES, FACTUELLES et PROFESSIONNELLES, toujours en FRANÇAIS
impeccable (orthographe et grammaire PARFAITES, aucune faute).

Règles ABSOLUES :
- La légende RÉSUME l'information : en quelques lignes, le lecteur comprend l'essentiel
  (ce qui se passe, les chiffres clés, pourquoi ça compte) SANS avoir vu le visuel.
- Ton de journaliste : neutre, posé, crédible. JAMAIS de ton « assistant / IA », de
  formules creuses (« Découvrez », « incontournable », « révolutionnaire ») ni de
  superlatifs marketing.
- Emojis : UN SEUL maximum par légende, et seulement s'il apporte vraiment quelque chose.
  Zéro est préférable. Pas de hashtags à outrance.
- N'invente AUCUN chiffre : utilise uniquement les faits fournis.

Tu réponds UNIQUEMENT en JSON valide, sans markdown."""

POST_PROMPT = """Rédige 3 légendes pour ce post. Chacune doit RÉSUMER l'information ci-dessous
pour qu'on en comprenne l'idée en quelques lignes.

Sujet : {title}
Source : {source}
Catégorie : {category}
Faits / chiffres clés : {key_data}
Résumé source : {summary}

Consignes par réseau (EN FRANÇAIS, sobre, sans la moindre faute) :
- twitter : 1 à 2 phrases avec l'essentiel (le fait + le chiffre clé). ≤ 260 caractères.
  1 à 2 hashtags pertinents. Pas d'emoji (un seul à la rigueur).
- instagram : 3 à 5 phrases courtes qui RÉSUMENT l'info (quoi, chiffres, pourquoi c'est
  important). Ton clair et professionnel. 0 à 1 emoji MAXIMUM. Termine par 3 à 5 hashtags
  pertinents (pas plus).
- linkedin : 4 à 6 phrases, angle analytique et factuel (contexte + implication concrète).
  AUCUN emoji. 3 hashtags professionnels.

JSON attendu :
{{
  "twitter": "<texte>",
  "instagram": "<texte>",
  "linkedin": "<texte>"
}}"""


def generate_captions(article: dict) -> dict:
    """Retourne les captions pour les 3 réseaux."""
    # Points clés : depuis chart_data (labels:valeurs) ou key_points
    kd = article.get("key_points") or []
    if not kd and article.get("chart_data"):
        kd = [f"{d.get('label', '')}: {d.get('value', '')}{d.get('unit', '')}"
              for d in article["chart_data"] if isinstance(d, dict)]

    # Matière de résumé : résumé RSS si dispo, sinon l'insight (cas décryptage/brève collés).
    summary = (article.get("summary") or article.get("insight") or "").strip()[:400]
    prompt = POST_PROMPT.format(
        title=article.get("title_fr") or article["title"],
        source=article["source"],
        category=article.get("category", ""),
        key_data=", ".join(kd) or "Voir article",
        summary=summary,
    )

    # 1200 tokens : 3 textes (Twitter + Instagram 150-300 mots + LinkedIn 200-400 mots)
    # dépassaient les 600 précédents → JSON tronqué → erreur 'json_validate_failed'.
    def _ask(max_toks: int) -> dict:
        response = _groq().chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=max_toks,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content.strip())

    # Qualité : Mistral/Gemini d'abord (plus rigoureux que le 8b), repli Groq.
    captions = None
    try:
        import llm
        if llm.provider():
            captions = llm.generate_json(prompt, SYSTEM_PROMPT, max_tokens=1400, temperature=0.7)
    except Exception:
        captions = None
    if not (captions and all(k in captions for k in ("twitter", "instagram", "linkedin"))):
        captions = None

    try:
        if captions is None:
            captions = _ask(1200)
    except Exception as e:
        print(f"[GENERATOR] captions échec ({type(e).__name__}), repli minimal : {e}")
        # Repli : un post DOIT toujours être créé, même sans captions IA.
        t = article.get("title_fr") or article.get("title", "")
        s = (article.get("summary", "") or "").strip()[:300]
        cat = article.get("category", "")
        captions = {
            "twitter":   t[:250],
            "instagram": f"{t}\n\n{s}\n\n#{cat}".strip() if cat else f"{t}\n\n{s}".strip(),
            "linkedin":  f"{t}\n\n{s}".strip(),
        }

    # Coercion : un modèle peut renvoyer un objet/liste pour un champ → on aplatit en texte.
    def _as_text(v):
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, dict):
            return " ".join(_as_text(x) for x in v.values())
        if isinstance(v, list):
            return " ".join(_as_text(x) for x in v)
        return str(v)

    _title = article.get("title_fr") or article.get("title", "")
    for k in ("twitter", "instagram", "linkedin"):
        captions[k] = _as_text(captions.get(k, "")) or _title

    # Sécurité longueur Twitter
    if len(captions.get("twitter", "")) > 270:
        captions["twitter"] = captions["twitter"][:267] + "..."

    # Lien vers l'article source en fin de description (Instagram + LinkedIn).
    # Twitter exclu (limite de caractères). Permet de retrouver l'article complet.
    url = article.get("url", "")
    if url and not url.startswith("https://news.google.com"):
        link = f"\n\nArticle complet : {url}"
        captions["instagram"] = captions.get("instagram", "") + link
        captions["linkedin"] = captions.get("linkedin", "") + link

    return captions


if __name__ == "__main__":
    test = {
        "title": "OpenAI lève 40 milliards de dollars, valorisation à 300 milliards",
        "source": "TechCrunch",
        "category": "tech",
        "key_data": ["40 Mds$ levés", "Valorisation 300 Mds$", "+150% en 1 an"],
        "summary": "OpenAI a bouclé un tour de financement record...",
    }
    captions = generate_captions(test)
    for network, text in captions.items():
        print(f"\n── {network.upper()} ({len(text)} chars) ──")
        print(text)
