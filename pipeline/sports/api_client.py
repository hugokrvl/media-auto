"""
Client unifié pour toutes les APIs api-sports.io.
Une seule clé API_SPORTS_KEY fonctionne pour Football, Basketball, F1, Rugby, Tennis.
"""

import os
import json
import urllib.request
import urllib.parse
from datetime import date, timedelta

API_KEY = os.environ.get("API_SPORTS_KEY", "")

_BASES = {
    "football":   "https://v3.football.api-sports.io",
    "basketball": "https://v1.basketball.api-sports.io",
    "formula1":   "https://v1.formula-1.api-sports.io",
    "rugby":      "https://v1.rugby.api-sports.io",
    "tennis":     "https://v1.tennis.api-sports.io",
}


def _get(sport: str, endpoint: str, params: dict) -> dict:
    """Appel générique à api-sports.io. Lève une exception si pas de clé."""
    if not API_KEY:
        raise RuntimeError("API_SPORTS_KEY manquante — ajoutez-la dans .env et GitHub Secrets")
    base = _BASES[sport]
    qs = urllib.parse.urlencode(params)
    url = f"{base}/{endpoint}?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "x-apisports-key": API_KEY,
            "User-Agent": "HKMedia/1.0 (mediaauto; hugo1actualite@gmail.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    errors = data.get("errors", {})
    if errors:
        raise RuntimeError(f"API-Sports erreur [{sport}/{endpoint}]: {errors}")
    return data


# ── FOOTBALL ──────────────────────────────────────────────────────────────────

def get_football_fixtures(league_id: int, season: int, match_date: str) -> list[dict]:
    """
    Retourne les matchs d'une ligue pour une date donnée (YYYY-MM-DD).
    Chaque match contient : teams (home/away name + logo), goals, fixture (status).
    """
    data = _get("football", "fixtures", {
        "league": league_id,
        "season": season,
        "date": match_date,
    })
    return data.get("response", [])


def all_finished(fixtures: list[dict]) -> bool:
    """Retourne True si tous les matchs sont terminés (FT, AET, PEN, AWD, WO)."""
    finished = {"FT", "AET", "PEN", "AWD", "WO", "CANC", "PST", "ABD"}
    return all(
        f.get("fixture", {}).get("status", {}).get("short", "") in finished
        for f in fixtures
    )


# ── BASKETBALL ────────────────────────────────────────────────────────────────

def get_basketball_games(league_id: int, season: str, match_date: str) -> list[dict]:
    data = _get("basketball", "games", {
        "league": league_id,
        "season": season,
        "date": match_date,
    })
    return data.get("response", [])


def basketball_all_finished(games: list[dict]) -> bool:
    finished = {"FT", "AOT", "CANC", "PST", "ABD"}
    return all(
        g.get("status", {}).get("short", "") in finished
        for g in games
    )


# ── FORMULE 1 ─────────────────────────────────────────────────────────────────

def get_f1_race(season: int, match_date: str) -> dict | None:
    """Retourne la course F1 du jour si elle existe et est terminée."""
    data = _get("formula1", "races", {
        "season": season,
        "date": match_date,
        "type": "Race",
    })
    races = data.get("response", [])
    if not races:
        return None
    race = races[0]
    status = race.get("status", "")
    if status not in ("Race Finished", "Finished"):
        return None
    return race


def get_f1_results(race_id: int) -> list[dict]:
    data = _get("formula1", "results", {"race": race_id})
    return data.get("response", [])


# ── RUGBY ─────────────────────────────────────────────────────────────────────

def get_rugby_games(league_id: int, match_date: str) -> list[dict]:
    data = _get("rugby", "games", {
        "league": league_id,
        "date": match_date,
    })
    return data.get("response", [])


def rugby_all_finished(games: list[dict]) -> bool:
    finished = {"FT", "AOT", "CANC", "PST"}
    return all(
        g.get("status", {}).get("short", "") in finished
        for g in games
    )


# ── UTILITAIRE ────────────────────────────────────────────────────────────────

def today_str() -> str:
    return date.today().isoformat()


def yesterday_str() -> str:
    return (date.today() - timedelta(days=1)).isoformat()
