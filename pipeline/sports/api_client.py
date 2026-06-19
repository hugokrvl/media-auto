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


# ── ESPN (sans clé — Coupe du Monde + compétitions internationales) ────────────

_ESPN_SLUGS = {
    "fifa.world":     "Coupe du Monde",
    "uefa.euro":      "Euro",
    "conmebol.copa":  "Copa América",
}

_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def get_espn_scores(slug: str) -> list[dict]:
    """
    Récupère les matchs du jour via l'API publique ESPN (sans clé).
    slug : ex. "fifa.world", "uefa.euro"
    Retourne une liste de matchs au même format que get_football_fixtures().
    """
    url = f"{_ESPN_BASE}/{slug}/scoreboard"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"[ESPN] Erreur ({slug}): {e}")
        return []

    fixtures = []
    for event in data.get("events", []):
        comp   = event.get("competitions", [{}])[0]
        teams  = comp.get("competitors", [])
        if len(teams) < 2:
            continue
        status = comp.get("status", {}).get("type", {})
        short  = "FT" if status.get("completed") else (
                 "1H" if "1st" in status.get("description", "").lower() else
                 "2H" if "2nd" in status.get("description", "").lower() else
                 "NS")
        home = teams[0]
        away = teams[1]
        fixtures.append({
            "teams": {
                "home": {
                    "name": home.get("team", {}).get("displayName", ""),
                    "logo": home.get("team", {}).get("logo", ""),
                },
                "away": {
                    "name": away.get("team", {}).get("displayName", ""),
                    "logo": away.get("team", {}).get("logo", ""),
                },
            },
            "goals": {
                "home": int(home.get("score", 0)) if status.get("completed") or short in ("1H","2H") else None,
                "away": int(away.get("score", 0)) if status.get("completed") or short in ("1H","2H") else None,
            },
            "fixture": {"status": {"short": short}},
        })
    return fixtures


def espn_all_finished(fixtures: list[dict]) -> bool:
    finished = {"FT", "AET", "PEN", "CANC", "PST"}
    return bool(fixtures) and all(
        f.get("fixture", {}).get("status", {}).get("short", "") in finished
        for f in fixtures
    )
