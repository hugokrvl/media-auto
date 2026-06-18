# -*- coding: utf-8 -*-
"""Teste la logique 2-passes de analyzer SANS appeler Groq (mock _chat)."""
import os
import sys
import types
os.environ.setdefault("GROQ_API_KEY", "test")  # évite l'erreur d'import
os.environ["GROQ_PACE_SECONDS"] = "0"           # pas d'attente en test

# groq n'est pas installé dans le sandbox -> on mocke le module
_fake = types.ModuleType("groq")
_fake.Groq = lambda *a, **k: None
sys.modules["groq"] = _fake

import analyzer

# Faux articles : 3 gardables (dont 1 VIDÉO avec transcription), 2 à jeter
ARTS = [
    {"title": "Inflation zone euro recule a 2,9%", "source": "Reuters", "summary": "BCE...", "category": "finance"},
    {"title": "Analyse marche par Cheron", "source": "Nicolas Cheron (YT)", "summary": "intro courte",
     "category": "finance", "transcript": "Bonjour " * 4000, "is_video": True},  # ~32k car. -> plusieurs morceaux
    {"title": "Rumeur non verifiee sur une fusion", "source": "Blog X", "summary": "on dit que...", "category": "finance"},
    {"title": "Bitcoin franchit 105000 dollars", "source": "CoinDesk", "summary": "hausse...", "category": "finance"},
    {"title": "Pub pour un casino en ligne", "source": "Spam", "summary": "gagnez...", "category": "general"},
]

digest_calls = {"n": 0}

# Réponses mockées selon le modèle appelé
def fake_chat(model, system, user, max_tokens, retries=4):
    if "résumé dense" in system or "digest" in user.lower():   # PASSE DIGEST (vidéo)
        digest_calls["n"] += 1
        return {"digest": "Marché +3,2% ; ETF 12 Md€ ; DCA limité"}
    if model == analyzer.TRIAGE_MODEL:           # PASSE 1 (triage)
        if "Inflation" in user:   return {"score": 9, "verified": True,  "keep": True,  "category": "finance", "reason": "fort impact"}
        if "Cheron" in user or "marche par" in user: return {"score": 8, "verified": True, "keep": True, "category": "finance", "reason": "analyse"}
        if "Bitcoin" in user:     return {"score": 7, "verified": True,  "keep": True,  "category": "finance", "reason": "tendance"}
        if "Rumeur" in user:      return {"score": 4, "verified": False, "keep": False, "category": "finance", "reason": "non vérifié"}
        return {"score": 1, "verified": False, "keep": False, "category": "general", "reason": "pub"}
    # PASSE 2 (enrichissement 70b) — on vérifie que le digest vidéo est bien transmis
    if "Marché +3,2%" in user:
        return {"title_fr": "TITRE VIDEO", "subtitle_fr": "ST", "chart_type": "courbe",
                "chart_data": [{"label": "T1", "value": 3.2}], "key_points": []}
    return {"title_fr": "TITRE FR", "subtitle_fr": "ST", "chart_type": "kpi",
            "chart_data": [{"label": "X", "value": "1", "unit": "%"}], "key_points": []}

analyzer._chat = fake_chat

res = analyzer.analyze_articles(ARTS)
print(f"\nRetenus après pipeline : {len(res)} (attendu 3)")
for a in res:
    ok = all(k in a for k in ("score", "title_fr", "chart_type", "chart_data"))
    print(f"  {'OK' if ok else 'XX'} [{a['score']}/10] {a['title'][:30]:32} -> title_fr='{a.get('title_fr')}' chart={a.get('chart_type')}")
assert len(res) == 3, "le triage aurait dû garder exactement 3 articles"
assert res[0]["score"] == 9, "tri par score décroissant cassé"
assert digest_calls["n"] >= 1, "la vidéo aurait dû être digérée"
video = next(a for a in res if a["source"].endswith("(YT)"))
assert video["title_fr"] == "TITRE VIDEO", "le digest vidéo n'a pas été transmis au 70b"
print(f"\nDigest vidéo : {digest_calls['n']} appel(s) au modèle de digestion")
print("TOUS LES ASSERTS PASSENT ✅")
