"""
Orchestrateur « Clôture des marchés ».
Appelé par markets_close.yml une fois par jour (après la clôture US, en semaine).

- Récupère la clôture du jour des grands indices + BTC + Or via Yahoo Finance
  (API publique v8/chart, sans clé).
- Génère un post 1080x1080 (charte HK) et le sauvegarde dans Supabase (pending),
  un seul par jour (anti-doublon).
"""

import os
import sys
import json
import uuid
import urllib.request
import urllib.parse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markets_renderer import make_markets_post

TODAY = date.today().isoformat()

# Indices suivis (ordre = ordre d'affichage). decimals/prefix pour le format.
INDICES = [
    {"section": "États-Unis",        "name": "S&P 500",    "symbol": "^GSPC",     "decimals": 2},
    {"section": "États-Unis",        "name": "Nasdaq",     "symbol": "^IXIC",     "decimals": 2},
    {"section": "États-Unis",        "name": "Dow Jones",  "symbol": "^DJI",      "decimals": 2},
    {"section": "Europe",            "name": "Stoxx 600",  "symbol": "^STOXX",    "decimals": 2},
    {"section": "Europe",            "name": "CAC 40",     "symbol": "^FCHI",     "decimals": 2},
    {"section": "Europe",            "name": "DAX",        "symbol": "^GDAXI",    "decimals": 2},
    {"section": "Europe",            "name": "FTSE 100",   "symbol": "^FTSE",     "decimals": 2},
    {"section": "Asie",              "name": "Nikkei 225", "symbol": "^N225",     "decimals": 2},
    {"section": "Asie",              "name": "Hang Seng",  "symbol": "^HSI",      "decimals": 2},
    {"section": "Asie",              "name": "Shanghai",   "symbol": "000001.SS", "decimals": 2},
    {"section": "Crypto & Matières", "name": "Bitcoin",    "symbol": "BTC-USD",   "decimals": 0, "prefix": "$"},
    {"section": "Crypto & Matières", "name": "Or (once)",  "symbol": "GC=F",      "decimals": 2, "prefix": "$"},
]

_UA = {"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
_YF = "https://query1.finance.yahoo.com/v8/finance/chart/"

_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]
_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _date_label() -> str:
    d = date.today()
    return f"{_JOURS[d.weekday()].capitalize()} {d.day} {_MOIS[d.month]} {d.year}"


def fetch_quote(symbol: str) -> tuple[float | None, float | None]:
    """Retourne (clôture, variation%) ou (None, None) si indisponible."""
    url = _YF + urllib.parse.quote(symbol)
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        m = d["chart"]["result"][0]["meta"]
        price = m.get("regularMarketPrice")
        prev  = m.get("chartPreviousClose") or m.get("previousClose")
        if price is None or not prev:
            return None, None
        return price, (price - prev) / prev * 100.0
    except Exception as e:
        print(f"[MARKETS] {symbol} erreur : {type(e).__name__}: {e}")
        return None, None


def build_rows() -> list[dict]:
    rows = []
    for idx in INDICES:
        price, chg = fetch_quote(idx["symbol"])
        rows.append({**idx, "value": price, "change": chg})
        if price is not None:
            print(f"[MARKETS] {idx['name']:12} {price:>12,.2f} {chg:+.2f}%")
    return rows


def _already_posted() -> bool:
    try:
        import storage
        res = storage.supabase.table("posts").select("id").eq(
            "chart_type", "markets").eq(
            "article_title", f"Clôture des marchés · {TODAY}").execute()
        return len(res.data) > 0
    except Exception:
        return False


def _save_post(img_bytes: bytes) -> None:
    import storage
    post_id = str(uuid.uuid4())
    image_url = storage.upload_image(img_bytes, f"markets_{post_id}.png")
    storage.supabase.table("posts").insert({
        "id": post_id,
        "article_title": f"Clôture des marchés · {TODAY}",
        "source": "Marchés",
        "category": "finance",
        "chart_type": "markets",
        "relevance_score": 7,
        "verified": True,
        "status": "pending",
        "image_instagram": image_url,
        "image_twitter": image_url,
        "image_linkedin": image_url,
        "caption_instagram": f"📊 Clôture des marchés du {TODAY} #bourse #marchés #finance",
        "caption_twitter": f"📊 Clôture des marchés · {TODAY}",
        "caption_linkedin": f"Clôture des marchés du {TODAY}",
    }).execute()
    print(f"[MARKETS] Post créé : Clôture des marchés · {TODAY}")


def main():
    print(f"=== CLÔTURE MARCHÉS · {TODAY} ===")
    if _already_posted():
        print("[MARKETS] Déjà posté aujourd'hui — stop.")
        return
    rows = build_rows()
    if not any(r["value"] is not None for r in rows):
        print("[MARKETS] Aucune donnée — stop.")
        return
    img = make_markets_post(rows, _date_label())
    _save_post(img)
    try:
        import notifier
        notifier.send("📊 Clôture des marchés publiée")
    except Exception:
        pass
    print("=== FIN ===")


if __name__ == "__main__":
    main()
