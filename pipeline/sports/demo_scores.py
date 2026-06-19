"""Génère des posts résultats démo (sans clé API)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scores_renderer import make_football_scores, make_f1_podium
from leagues import FOOTBALL_LEAGUES, F1_CONFIG

# ── Démo Ligue 1 ──────────────────────────────────────────────────────────────
ligue1 = next(l for l in FOOTBALL_LEAGUES if l["id"] == 61)
fixtures_ligue1 = [
    {"teams": {"home": {"name": "PSG",       "logo": "https://media.api-sports.io/football/teams/85.png"},
               "away": {"name": "Lyon",       "logo": "https://media.api-sports.io/football/teams/80.png"}},
     "goals": {"home": 3, "away": 1},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Marseille",  "logo": "https://media.api-sports.io/football/teams/81.png"},
               "away": {"name": "Nice",       "logo": "https://media.api-sports.io/football/teams/84.png"}},
     "goals": {"home": 0, "away": 0},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Monaco",     "logo": "https://media.api-sports.io/football/teams/91.png"},
               "away": {"name": "Lille",      "logo": "https://media.api-sports.io/football/teams/79.png"}},
     "goals": {"home": 2, "away": 1},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Lens",       "logo": "https://media.api-sports.io/football/teams/116.png"},
               "away": {"name": "Rennes",     "logo": "https://media.api-sports.io/football/teams/111.png"}},
     "goals": {"home": 1, "away": 2},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Strasbourg", "logo": "https://media.api-sports.io/football/teams/95.png"},
               "away": {"name": "Nantes",     "logo": "https://media.api-sports.io/football/teams/83.png"}},
     "goals": {"home": 1, "away": 1},
     "fixture": {"status": {"short": "FT"}}},
]

print("Génération Ligue 1...")
img = make_football_scores(fixtures_ligue1, ligue1)
with open("demo_ligue1.png", "wb") as f: f.write(img)
print("OK -> demo_ligue1.png")

# ── Démo Champions League ──────────────────────────────────────────────────────
cl = next(l for l in FOOTBALL_LEAGUES if l["id"] == 2)
fixtures_cl = [
    {"teams": {"home": {"name": "Real Madrid",   "logo": "https://media.api-sports.io/football/teams/541.png"},
               "away": {"name": "Man. City",     "logo": "https://media.api-sports.io/football/teams/50.png"}},
     "goals": {"home": 2, "away": 1},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Bayern",        "logo": "https://media.api-sports.io/football/teams/157.png"},
               "away": {"name": "PSG",           "logo": "https://media.api-sports.io/football/teams/85.png"}},
     "goals": {"home": 1, "away": 3},
     "fixture": {"status": {"short": "FT"}}},
    {"teams": {"home": {"name": "Barcelona",     "logo": "https://media.api-sports.io/football/teams/529.png"},
               "away": {"name": "Inter",         "logo": "https://media.api-sports.io/football/teams/505.png"}},
     "goals": {"home": 0, "away": 0},
     "fixture": {"status": {"short": "FT"}}},
]

print("Génération Champions League...")
img = make_football_scores(fixtures_cl, cl)
with open("demo_cl.png", "wb") as f: f.write(img)
print("OK -> demo_cl.png")

# ── Démo F1 ───────────────────────────────────────────────────────────────────
race = {"competition": {"name": "Grand Prix de Monaco"}, "id": 1}
results_f1 = [
    {"driver": {"name": "Charles Leclerc", "abbr": "LEC", "nationality": "Monaco"},
     "team": {"name": "Ferrari"}, "time": {"time": "1:38:25.456"}},
    {"driver": {"name": "Max Verstappen", "abbr": "VER", "nationality": "Netherlands"},
     "team": {"name": "Red Bull"}, "time": {"time": "+12.643"}},
    {"driver": {"name": "Lando Norris", "abbr": "NOR", "nationality": "United Kingdom"},
     "team": {"name": "McLaren"}, "time": {"time": "+18.921"}},
]

print("Génération F1 Podium...")
img = make_f1_podium(race, results_f1)
with open("demo_f1.png", "wb") as f: f.write(img)
print("OK -> demo_f1.png")
