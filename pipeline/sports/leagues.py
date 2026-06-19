"""
Configuration centralisée de tous les championnats suivis.
Chaque entrée définit : ID API, nom affiché, sport, fuseau horaire de fin de journée.
"""

# ── FOOTBALL (API-Football) ────────────────────────────────────────────────────
FOOTBALL_LEAGUES = [
    # Compétitions internationales (priorité maximale)
    {"id": 1,   "name": "Coupe du Monde",    "country": "FIFA",     "flag": "🌍",  "color": (0, 100, 60),   "priority": 0},
    {"id": 4,   "name": "Euro",              "country": "UEFA",     "flag": "🇪🇺", "color": (0, 51, 160),   "priority": 1},
    {"id": 6,   "name": "Coupe des Nations", "country": "CONMEBOL", "flag": "🌎",  "color": (0, 120, 200),  "priority": 1},
    # Ligues nationales (actives sept→mai)
    {"id": 61,  "name": "Ligue 1",           "country": "France",   "flag": "🇫🇷", "color": (20, 60, 140),  "priority": 2},
    {"id": 62,  "name": "Ligue 2",           "country": "France",   "flag": "🇫🇷", "color": (30, 80, 160),  "priority": 3},
    {"id": 63,  "name": "National",          "country": "France",   "flag": "🇫🇷", "color": (40, 90, 170),  "priority": 4},
    {"id": 140, "name": "La Liga",           "country": "Espagne",  "flag": "🇪🇸", "color": (180, 30, 30),  "priority": 2},
    {"id": 39,  "name": "Premier League",    "country": "Angleterre","flag": "🏴",  "color": (98, 24, 153),  "priority": 2},
    {"id": 78,  "name": "Bundesliga",        "country": "Allemagne", "flag": "🇩🇪", "color": (215, 0, 0),    "priority": 2},
    {"id": 135, "name": "Serie A",           "country": "Italie",   "flag": "🇮🇹", "color": (0, 82, 147),   "priority": 2},
    # Coupes européennes (actives oct→mai)
    {"id": 2,   "name": "Champions League",  "country": "Europe",   "flag": "🏆",  "color": (0, 32, 91),    "priority": 1},
    {"id": 3,   "name": "Europa League",     "country": "Europe",   "flag": "🏆",  "color": (255, 102, 0),  "priority": 2},
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

# ── COMPÉTITIONS ESPN (sans clé, temps réel) ─────────────────────────────────
# slug ESPN → (nom affiché, couleur header, code pays)
ESPN_COMPETITIONS = [
    {"slug": "fifa.world",    "name": "Coupe du Monde", "country": "FIFA",     "color": (0, 120, 60)},
    {"slug": "uefa.euro",     "name": "Euro UEFA",      "country": "UEFA",     "color": (0, 51, 160)},
    {"slug": "conmebol.america", "name": "Copa América", "country": "CONMEBOL", "color": (0, 100, 200)},
]

# ── SAISONS COURANTES ────────────────────────────────────────────────────────
CURRENT_SEASON_FOOTBALL    = 2024  # free tier API-Sports limité à 2022-2024
CURRENT_SEASON_BASKETBALL  = "2024-2025"
CURRENT_SEASON_F1          = 2025
CURRENT_SEASON_RUGBY       = 2024
