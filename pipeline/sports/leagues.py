"""
Configuration centralisée de tous les championnats suivis.
Chaque entrée définit : ID API, nom affiché, sport, fuseau horaire de fin de journée.
"""

# ── FOOTBALL (API-Football) ────────────────────────────────────────────────────
FOOTBALL_LEAGUES = [
    {"id": 61,  "name": "Ligue 1",          "country": "France",   "flag": "🇫🇷", "color": (255, 255, 255)},
    {"id": 62,  "name": "Ligue 2",          "country": "France",   "flag": "🇫🇷", "color": (200, 200, 200)},
    {"id": 63,  "name": "Ligue 3 (National)","country": "France",  "flag": "🇫🇷", "color": (180, 180, 180)},
    {"id": 140, "name": "La Liga",           "country": "Espagne",  "flag": "🇪🇸", "color": (255, 215, 0)},
    {"id": 39,  "name": "Premier League",    "country": "Angleterre","flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "color": (98, 24, 153)},
    {"id": 78,  "name": "Bundesliga",        "country": "Allemagne","flag": "🇩🇪", "color": (215, 0, 0)},
    {"id": 135, "name": "Serie A",           "country": "Italie",   "flag": "🇮🇹", "color": (0, 82, 147)},
    {"id": 2,   "name": "Champions League",  "country": "Europe",   "flag": "🏆",  "color": (0, 32, 91)},
    {"id": 3,   "name": "Europa League",     "country": "Europe",   "flag": "🏆",  "color": (255, 102, 0)},
]

# ── BASKETBALL (API-Basketball) ────────────────────────────────────────────────
BASKETBALL_LEAGUES = [
    {"id": 12,  "name": "NBA",              "country": "USA",      "flag": "🇺🇸", "color": (29, 66, 138)},
    {"id": 116, "name": "Betclic Elite",    "country": "France",   "flag": "🇫🇷", "color": (0, 90, 170)},
]

# ── FORMULE 1 (API-Formula-1) ─────────────────────────────────────────────────
F1_CONFIG = {
    "name": "Formula 1",
    "flag": "🏎️",
    "color": (225, 6, 0),
}

# ── RUGBY (API-Rugby) ─────────────────────────────────────────────────────────
RUGBY_LEAGUES = [
    {"id": 61,  "name": "Top 14",           "country": "France",   "flag": "🇫🇷", "color": (0, 61, 135)},
    {"id": 45,  "name": "Champions Cup",    "country": "Europe",   "flag": "🏆",  "color": (0, 120, 80)},
]

# ── TENNIS (API-Tennis) ───────────────────────────────────────────────────────
TENNIS_TOURNAMENTS = [
    {"name": "Roland Garros",   "flag": "🇫🇷", "surface": "Clay",  "color": (185, 120, 80)},
    {"name": "Wimbledon",        "flag": "🇬🇧", "surface": "Grass", "color": (0, 100, 0)},
    {"name": "US Open",          "flag": "🇺🇸", "surface": "Hard",  "color": (0, 53, 148)},
    {"name": "Australian Open",  "flag": "🇦🇺", "surface": "Hard",  "color": (0, 122, 204)},
]

# ── SAISONS COURANTES ────────────────────────────────────────────────────────
CURRENT_SEASON_FOOTBALL    = 2024
CURRENT_SEASON_BASKETBALL  = "2024-2025"
CURRENT_SEASON_F1          = 2025
CURRENT_SEASON_RUGBY       = 2024
