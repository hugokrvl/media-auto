"""
Analyse les articles avec Groq (llama-3.3-70b).
Retourne un score de pertinence, vérifie les infos, trie et sélectionne les meilleurs.
"""

import json
import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """Tu es un rédacteur en chef d'un média économique sérieux, orienté vérité et ouverture.
Tu analyses des articles de presse pour décider lesquels méritent d'être relayés sur les réseaux sociaux.

Critères d'évaluation :
- Pertinence économique ou sociétale (impact réel sur les gens)
- Fiabilité de la source et recoupement possible
- Originalité / valeur ajoutée de l'info
- Potentiel de visualisation de données (chiffres, comparaisons, tendances)

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans commentaires."""

ANALYSIS_PROMPT = """Analyse cet article et prépare une infographie en FRANÇAIS.
Retourne un JSON avec EXACTEMENT cette structure :

{
  "score": <entier 0-10>,
  "verified": <true si info vérifiable et fiable, false sinon>,
  "keep": <true si score >= 6 et verified, false sinon>,
  "category": "<finance|tech|general|sport|factcheck>",
  "title_fr": "<titre court et accrocheur EN FRANÇAIS, max 75 caractères>",
  "subtitle_fr": "<sous-titre court EN FRANÇAIS : contexte/période/unité, max 50 caractères>",
  "chart_type": "<kpi|donut|bar|courbe|infographic>",
  "chart_data": [<voir format selon chart_type ci-dessous>],
  "key_points": [<2-4 points clés EN FRANÇAIS si chart_type=infographic, sinon []>],
  "reason": "<1 phrase expliquant le score>"
}

RÈGLES chart_data (TRÈS IMPORTANT — données réelles tirées de l'article) :
- chart_type "kpi" : 2-3 chiffres clés isolés. Format :
    [{"label": "Inflation", "value": "3.2", "unit": "%", "evolution": "-0.4"}, ...]
    (evolution = variation en %, "" si inconnue ; value en nombre, point décimal)
- chart_type "donut" : répartition/parts (total = 100 idéalement). Format :
    [{"label": "Apple", "value": 28}, {"label": "Samsung", "value": 22}, ...]
- chart_type "bar" : comparaison/classement. Format :
    [{"label": "OpenAI", "value": 40}, {"label": "Anthropic", "value": 25}, ...]
- chart_type "courbe" : évolution temporelle. Format :
    [{"label": "Jan", "value": 92}, {"label": "Fév", "value": 88}, ...]
- chart_type "infographic" : PAS de données chiffrées exploitables -> chart_data: [], remplis key_points.

N'INVENTE JAMAIS de chiffres. Si l'article ne contient pas de données chiffrées
fiables, utilise chart_type "infographic" avec des key_points factuels.

Article :
Titre: __TITLE__
Source: __SOURCE__
Résumé: __SUMMARY__"""


def analyze_articles(articles: list[dict], max_to_analyze: int = 60) -> list[dict]:
    """Analyse jusqu'à `max_to_analyze` articles et retourne ceux qui passent le filtre."""
    # Limite pour respecter le quota Groq
    to_analyze = articles[:max_to_analyze]
    results = []

    for article in to_analyze:
        try:
            analysis = _analyze_one(article)
            if analysis.get("keep"):
                article.update(analysis)
                results.append(article)
        except Exception as e:
            print(f"[ANALYZER] Erreur sur '{article['title'][:50]}': {type(e).__name__}: {e}")

    # Trie par score décroissant, garde max 15 articles
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected = results[:15]
    print(f"[ANALYZER] {len(selected)}/{len(to_analyze)} articles sélectionnés")
    return selected


def _analyze_one(article: dict) -> dict:
    prompt = (ANALYSIS_PROMPT
              .replace("__TITLE__", article["title"])
              .replace("__SOURCE__", article["source"])
              .replace("__SUMMARY__", article["summary"][:600]))

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=700,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


if __name__ == "__main__":
    from scraper import fetch_articles
    articles = fetch_articles()
    selected = analyze_articles(articles)
    for a in selected:
        print(f"[{a['score']}/10] [{a['chart_type']}] {a['title'][:70]}")
        print(f"  → {a.get('reason', '')}")
