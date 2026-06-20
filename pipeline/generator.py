"""
Génère les textes de posts pour chaque réseau via Groq.
Respecte les contraintes de chaque plateforme.
"""

import json
import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Captions sur le 8b (500k tokens/jour) : qualité suffisante pour le social media,
# économise le quota 70b (100k/jour) pour l'enrichissement structuré uniquement.
GENERATION_MODEL = os.environ.get("GROQ_CAPTION_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = """Tu es un community manager expert en médias économiques et tech.
Tu rédiges des posts viraux, informatifs et engageants pour les réseaux sociaux.
Tu écris TOUJOURS en FRANÇAIS, même si l'article source est en anglais.
Ton style : direct, factuel, accrocheur. Pas de phrases creuses.
Tu réponds UNIQUEMENT en JSON valide, sans markdown."""

POST_PROMPT = """Rédige 3 versions de post pour cet article :

Article : {title}
Source : {source}
Catégorie : {category}
Points clés : {key_data}
Résumé : {summary}

Écris EN FRANÇAIS. Contraintes :
- Twitter/X : max 260 caractères, 2-3 hashtags pertinents, emoji autorisé
- Instagram : 150-300 mots, storytelling, 8-12 hashtags thématiques, émojis
- LinkedIn : 200-400 mots, ton professionnel-analytique, 3-5 hashtags, pas d'émoji excessif

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

    prompt = POST_PROMPT.format(
        title=article.get("title_fr") or article["title"],
        source=article["source"],
        category=article.get("category", ""),
        key_data=", ".join(kd) or "Voir article",
        summary=article.get("summary", "")[:400],
    )

    # 1200 tokens : 3 textes (Twitter + Instagram 150-300 mots + LinkedIn 200-400 mots)
    # dépassaient les 600 précédents → JSON tronqué → erreur 'json_validate_failed'.
    def _ask(max_toks: int) -> dict:
        response = client.chat.completions.create(
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
            "instagram": f"{t}\n\n{s}\n\n#{cat} #actualité".strip(),
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
        link = f"\n\n📄 Article complet : {url}"
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
