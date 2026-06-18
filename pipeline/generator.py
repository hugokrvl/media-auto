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

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=600,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    captions = json.loads(raw)

    # Sécurité longueur Twitter
    if len(captions.get("twitter", "")) > 270:
        captions["twitter"] = captions["twitter"][:267] + "..."

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
