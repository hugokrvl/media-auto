"""
Orchestrateur résultats sportifs.
Appelé par le workflow sports_results.yml toutes les 30 min (18h→02h).

Logique :
- Pour chaque championnat suivi, vérifie si des matchs ont eu lieu aujourd'hui.
- Si TOUS les matchs du jour sont terminés ET que le post n'a pas encore été créé
  → génère l'image + sauvegarde dans Supabase.
"""

import os
import sys
import uuid
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import api_client as _api
from leagues import (
    FOOTBALL_LEAGUES, BASKETBALL_LEAGUES, RUGBY_LEAGUES,
    ESPN_COMPETITIONS,
    CURRENT_SEASON_FOOTBALL, CURRENT_SEASON_BASKETBALL,
    CURRENT_SEASON_F1, CURRENT_SEASON_RUGBY,
    F1_CONFIG,
)
from scores_renderer import make_football_scores, make_f1_podium
import storage
import notifier

TODAY = date.today().isoformat()


def _already_posted(league_name: str, sport_date: str) -> bool:
    """Vérifie si un post résultats pour ce championnat/date existe déjà."""
    try:
        rows = storage.supabase.table("posts").select("id").eq(
            "chart_type", "scores"
        ).eq("source", league_name).eq(
            "article_title", f"Résultats {league_name} · {sport_date}"
        ).execute()
        return len(rows.data) > 0
    except Exception:
        return False


def _save_scores_post(league_name: str, img_bytes: bytes, sport_date: str,
                      category: str = "sport") -> None:
    """Upload l'image et sauvegarde le post résultats dans Supabase."""
    post_id = str(uuid.uuid4())
    image_url = storage.upload_image(img_bytes, f"scores_{post_id}.png")

    storage.supabase.table("posts").insert({
        "id": post_id,
        "article_title": f"Résultats {league_name} · {sport_date}",
        "source": league_name,
        "category": category,
        "chart_type": "scores",
        "relevance_score": 7,
        "verified": True,
        "status": "pending",
        "image_instagram": image_url,
        "image_twitter": image_url,
        "image_linkedin": image_url,
        "caption_instagram": f"Résultats {league_name} du {sport_date}. #sport #{league_name.replace(' ','')}",
        "caption_twitter": f"Résultats {league_name} · {sport_date}",
        "caption_linkedin": f"Résultats {league_name} du {sport_date}",
    }).execute()
    print(f"[SPORT] Post créé : {league_name} · {sport_date}")


def run_football() -> None:
    """Vérifie tous les championnats football et génère les posts si complets."""
    for league in FOOTBALL_LEAGUES:
        lid  = league["id"]
        name = league["name"]
        try:
            fixtures = _api.get_football_fixtures(lid, CURRENT_SEASON_FOOTBALL, TODAY)
            if not fixtures:
                continue
            if not _api.all_finished(fixtures):
                print(f"[FOOT] {name} : {len(fixtures)} matchs, pas encore tous terminés")
                continue
            if _already_posted(name, TODAY):
                print(f"[FOOT] {name} : déjà posté aujourd'hui")
                continue
            print(f"[FOOT] {name} : {len(fixtures)} matchs terminés → génération post")
            img = make_football_scores(fixtures, league)
            _save_scores_post(name, img, TODAY)
            notifier.send(f"⚽ Résultats {name} publiés ({len(fixtures)} matchs)")
        except Exception as e:
            print(f"[FOOT] {name} erreur : {e}")


def run_basketball() -> None:
    """Vérifie NBA et Betclic Elite."""
    for league in BASKETBALL_LEAGUES:
        lid  = league["id"]
        name = league["name"]
        try:
            games = _api.get_basketball_games(lid, CURRENT_SEASON_BASKETBALL, TODAY)
            if not games:
                continue
            if not _api.basketball_all_finished(games):
                print(f"[BASKET] {name} : pas encore tous terminés")
                continue
            if _already_posted(name, TODAY):
                continue
            print(f"[BASKET] {name} : {len(games)} matchs terminés → génération post")
            # Réutilise le renderer football (même structure score home/away)
            fixtures_fmt = [
                {
                    "teams": {
                        "home": {"name": g.get("teams", {}).get("home", {}).get("name", ""),
                                 "logo": g.get("teams", {}).get("home", {}).get("logo", "")},
                        "away": {"name": g.get("teams", {}).get("away", {}).get("name", ""),
                                 "logo": g.get("teams", {}).get("away", {}).get("logo", "")},
                    },
                    "goals": {"home": g.get("scores", {}).get("home", {}).get("total"),
                              "away": g.get("scores", {}).get("away", {}).get("total")},
                    "fixture": {"status": {"short": g.get("status", {}).get("short", "FT")}},
                }
                for g in games
            ]
            img = make_football_scores(fixtures_fmt, league)
            _save_scores_post(name, img, TODAY)
            notifier.send(f"🏀 Résultats {name} publiés ({len(games)} matchs)")
        except Exception as e:
            print(f"[BASKET] {name} erreur : {e}")


def run_f1() -> None:
    """Vérifie si une course F1 a eu lieu aujourd'hui."""
    try:
        race = _api.get_f1_race(CURRENT_SEASON_F1, TODAY)
        if not race:
            return
        name = race.get("competition", {}).get("name", "Grand Prix")
        if _already_posted(f"F1 · {name}", TODAY):
            return
        race_id = race.get("id")
        results = _api.get_f1_results(race_id) if race_id else []
        if not results:
            return
        print(f"[F1] {name} terminé → génération podium")
        img = make_f1_podium(race, results)
        _save_scores_post(f"F1 · {name}", img, TODAY)
        notifier.send(f"🏎️ Podium F1 {name} publié")
    except Exception as e:
        print(f"[F1] erreur : {e}")


def run_rugby() -> None:
    """Vérifie le Top 14 et Champions Cup."""
    for league in RUGBY_LEAGUES:
        lid  = league["id"]
        name = league["name"]
        try:
            games = _api.get_rugby_games(lid, TODAY)
            if not games:
                continue
            if not _api.rugby_all_finished(games):
                print(f"[RUGBY] {name} : pas encore terminé")
                continue
            if _already_posted(name, TODAY):
                continue
            print(f"[RUGBY] {name} : {len(games)} matchs → génération post")
            fixtures_fmt = [
                {
                    "teams": {
                        "home": {"name": g.get("teams", {}).get("home", {}).get("name", ""),
                                 "logo": g.get("teams", {}).get("home", {}).get("logo", "")},
                        "away": {"name": g.get("teams", {}).get("away", {}).get("name", ""),
                                 "logo": g.get("teams", {}).get("away", {}).get("logo", "")},
                    },
                    "goals": {"home": g.get("scores", {}).get("home"),
                              "away": g.get("scores", {}).get("away")},
                    "fixture": {"status": {"short": g.get("status", {}).get("short", "FT")}},
                }
                for g in games
            ]
            img = make_football_scores(fixtures_fmt, league)
            _save_scores_post(name, img, TODAY)
            notifier.send(f"🏉 Résultats {name} publiés")
        except Exception as e:
            print(f"[RUGBY] {name} erreur : {e}")


def run_espn() -> None:
    """Compétitions internationales via ESPN (sans clé) : Coupe du Monde, Euro, Copa."""
    for comp in ESPN_COMPETITIONS:
        slug = comp["slug"]
        name = comp["name"]
        try:
            fixtures = _api.get_espn_scores(slug)
            if not fixtures:
                continue
            if not _api.espn_all_finished(fixtures):
                print(f"[ESPN] {name} : {len(fixtures)} matchs, pas encore terminés")
                continue
            if _already_posted(name, TODAY):
                print(f"[ESPN] {name} : déjà posté aujourd'hui")
                continue
            print(f"[ESPN] {name} : {len(fixtures)} matchs terminés → génération post")
            img = make_football_scores(fixtures, comp)
            _save_scores_post(name, img, TODAY)
            notifier.send(f"⚽ Résultats {name} publiés ({len(fixtures)} matchs)")
        except Exception as e:
            print(f"[ESPN] {name} erreur : {e}")


def main():
    print(f"=== SPORTS RESULTS · {TODAY} ===")

    # ESPN en premier (Coupe du Monde, Euro…) — sans clé, toujours disponible
    run_espn()

    # API-Sports (championnats nationaux) — nécessite API_SPORTS_KEY
    if _api.API_KEY:
        run_football()
        run_basketball()
        run_f1()
        run_rugby()
    else:
        print("⚠️  API_SPORTS_KEY absente — championnats nationaux ignorés")

    print("=== FIN ===")


if __name__ == "__main__":
    main()
