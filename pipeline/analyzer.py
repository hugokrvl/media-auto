"""
Analyse les articles avec Groq (llama-3.3-70b).
Retourne un score de pertinence, vérifie les infos, trie et sélectionne les meilleurs.
"""

import json
import os
import re
import traceback
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

ANALYSIS_PROMPT = """Analyse cet article et retourne un JSON avec exactement cette structure :

{
  "score": <entier 0-10>,
  "verified": <true si info vérifiable et fiable, false sinon>,
  "keep": <true si score >= 6 et verified, false sinon>,
  "category": "<finance|tech|general|sport|factcheck>",
  "key_data": [<liste de 1-3 chiffres/faits clés extraits de l'article, ex: "+12% de croissance">],
  "chart_type": "<kpi|donut|bar|infographic>",
  "reason": "<1 phrase expliquant le score>"
}

chart_type guide :
- kpi : article avec des chiffres clés isolés (ex: résultats financiers, stats)
- donut : article avec des répartitions/comparaisons (ex: parts de marché, votes)
- bar : article avec une évolution dans le temps (ex: cours boursier, croissance)
- infographic : article narratif sans données structurées (fallback)

Article :
Titre: {title}
Source: {source}
Résumé: {summary}"""


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
            traceback.print_exc()
            break  # Stop après la première erreur pour voir le vrai problème

    # Trie par score décroissant, garde max 15 articles
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected = results[:15]
    print(f"[ANALYZER] {len(selected)}/{len(to_analyze)} articles sélectionnés")
    return selected


def _analyze_one(article: dict) -> dict:
    prompt = ANALYSIS_PROMPT.format(
        title=article["title"],
        source=article["source"],
        summary=article["summary"][:600],
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()
    print(f"[DEBUG] Réponse Groq brute : {repr(raw[:200])}")

    # Extraction robuste du JSON
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(raw)


if __name__ == "__main__":
    from scraper import fetch_articles
    articles = fetch_articles()
    selected = analyze_articles(articles)
    for a in selected:
        print(f"[{a['score']}/10] [{a['chart_type']}] {a['title'][:70]}")
        print(f"  → {a.get('reason', '')}")
