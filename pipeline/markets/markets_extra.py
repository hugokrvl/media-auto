"""
Orchestrateur des posts marchés "extra" — dispatch selon le jour :
- Lundi→Vendredi : Top / Flop des actions mondiales DU JOUR
- Samedi         : Top / Flop DE LA SEMAINE (variation 5 séances)
- Dimanche       : Sentiment marché — VIX (bourse) + Fear & Greed (crypto)

Source : Yahoo Finance (sans clé) + alternative.me (Fear & Greed crypto, sans clé).
Sauvegarde dans Supabase en `pending`, un post par type et par jour (anti-doublon).
"""

import os
import sys
import json
import uuid
import time
import urllib.request
import urllib.parse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markets_renderer import make_movers_post, make_sentiment_post

TODAY = date.today().isoformat()
_UA = {"User-Agent": "Mozilla/5.0 (compatible; HKMedia/1.0)"}
_YF = "https://query1.finance.yahoo.com/v8/finance/chart/"

_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]
_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _date_label() -> str:
    d = date.today()
    return f"{_JOURS[d.weekday()].capitalize()} {d.day} {_MOIS[d.month]} {d.year}"


# ── Univers d'actions mondiales (curaté = fiable) ──────────────────────────────
# (nom affiché, symbole Yahoo). Grandes capitalisations US / Europe / Asie.
WORLD_STOCKS = [
    ("Apple", "AAPL"), ("Microsoft", "MSFT"), ("Nvidia", "NVDA"), ("Amazon", "AMZN"),
    ("Alphabet", "GOOGL"), ("Meta", "META"), ("Tesla", "TSLA"), ("Broadcom", "AVGO"),
    ("AMD", "AMD"), ("Netflix", "NFLX"), ("JPMorgan", "JPM"), ("Visa", "V"),
    ("Walmart", "WMT"), ("Exxon", "XOM"), ("Coca-Cola", "KO"), ("Oracle", "ORCL"),
    ("Eli Lilly", "LLY"), ("Berkshire", "BRK-B"), ("Disney", "DIS"), ("McDonald's", "MCD"),
    ("LVMH", "MC.PA"), ("L'Oréal", "OR.PA"), ("TotalEnergies", "TTE.PA"),
    ("Airbus", "AIR.PA"), ("Sanofi", "SAN.PA"), ("Schneider", "SU.PA"),
    ("ASML", "ASML.AS"), ("SAP", "SAP.DE"), ("Siemens", "SIE.DE"),
    ("Nestlé", "NESN.SW"), ("Novartis", "NOVN.SW"), ("Novo Nordisk", "NOVO-B.CO"),
    ("Shell", "SHEL.L"), ("AstraZeneca", "AZN.L"), ("Toyota", "7203.T"),
    ("Sony", "6758.T"), ("TSMC", "TSM"), ("Samsung", "005930.KS"),
    ("Alibaba", "BABA"), ("Tencent", "TCEHY"),
]


def _yahoo(symbol: str, rng: str = "1d", interval: str = "1d") -> dict | None:
    url = f"{_YF}{urllib.parse.quote(symbol)}?range={rng}&interval={interval}"
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _day_change(symbol: str):
    d = _yahoo(symbol)
    if not d:
        return None
    try:
        m = d["chart"]["result"][0]["meta"]
        p, pv = m.get("regularMarketPrice"), m.get("chartPreviousClose")
        if p and pv:
            return p, (p - pv) / pv * 100.0, m.get("currency", "")
    except Exception:
        pass
    return None


def _week_change(symbol: str):
    d = _yahoo(symbol, rng="1mo", interval="1d")
    if not d:
        return None
    try:
        res = d["chart"]["result"][0]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        cur = res["meta"].get("currency", "")
        if len(closes) >= 6:
            last, ref = closes[-1], closes[-6]   # ~5 séances avant
            return last, (last - ref) / ref * 100.0, cur
    except Exception:
        pass
    return None


def _movers(weekly: bool):
    """Retourne (gainers, losers) triés, top 5 chacun."""
    fn = _week_change if weekly else _day_change
    rows = []
    for name, sym in WORLD_STOCKS:
        r = fn(sym)
        if r:
            price, chg, cur = r
            dec = 0 if price >= 1000 else 2
            rows.append({"name": name, "price": price, "change": chg,
                         "currency": cur, "decimals": dec})
        time.sleep(0.05)
    rows.sort(key=lambda x: -x["change"])
    return rows[:5], rows[-5:][::-1]


# ── Sentiment : VIX + Fear & Greed crypto ──────────────────────────────────────

def _vix():
    d = _yahoo("^VIX")
    if not d:
        return None
    try:
        return d["chart"]["result"][0]["meta"].get("regularMarketPrice")
    except Exception:
        return None


def _crypto_fng():
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        v = d["data"][0]
        return int(v["value"]), v["value_classification"]
    except Exception:
        return None, None


_GREEN  = (52, 199, 123)
_LIME   = (150, 200, 80)
_GRAYC  = (150, 158, 178)
_ORANGE = (235, 150, 60)
_RED    = (235, 83, 83)


def _vix_panel(vix: float) -> dict:
    if   vix < 15: label, color, hint = "Calme", _GREEN,  "Volatilité faible : marché serein, peu de stress."
    elif vix < 20: label, color, hint = "Normal", _LIME,  "Volatilité modérée : conditions habituelles."
    elif vix < 30: label, color, hint = "Nervosité", _ORANGE, "Volatilité élevée : les investisseurs se couvrent."
    else:          label, color, hint = "Panique", _RED,   "Volatilité extrême : aversion au risque marquée."
    zones = [(0.0, 0.375, _GREEN), (0.375, 0.5, _LIME),
             (0.5, 0.75, _ORANGE), (0.75, 1.0, _RED)]
    return {"value": f"{vix:.1f}".replace(".", ","), "label": label, "color": color,
            "frac": max(0.0, min(1.0, vix / 40.0)), "zones": zones, "hint": hint}


def _fng_panel(val: int) -> dict:
    if   val < 25: label, color = "Peur extrême", _RED
    elif val < 45: label, color = "Peur", _ORANGE
    elif val <= 55: label, color = "Neutre", _GRAYC
    elif val < 75: label, color = "Avidité", _LIME
    else:          label, color = "Avidité extrême", _GREEN
    hint = "Indice de peur/avidité du marché crypto (0 = peur, 100 = avidité)."
    zones = [(0.0, 0.25, _RED), (0.25, 0.45, _ORANGE), (0.45, 0.55, _GRAYC),
             (0.55, 0.75, _LIME), (0.75, 1.0, _GREEN)]
    return {"value": str(val), "label": label, "color": color,
            "frac": val / 100.0, "zones": zones, "hint": hint}


# ── Sauvegarde Supabase ────────────────────────────────────────────────────────

def _already_posted(kind: str) -> bool:
    try:
        import storage
        res = storage.supabase.table("posts").select("id").eq(
            "chart_type", kind).eq(
            "article_title", f"{_TITLES[kind]} · {TODAY}").execute()
        return len(res.data) > 0
    except Exception:
        return False


_TITLES = {
    "movers_day":  "Top/Flop du jour",
    "movers_week": "Top/Flop de la semaine",
    "sentiment":   "Sentiment des marchés",
}


def _save(kind: str, img: bytes, caption_tag: str) -> None:
    import storage
    post_id = str(uuid.uuid4())
    image_url = storage.upload_image(img, f"{kind}_{post_id}.png")
    title = f"{_TITLES[kind]} · {TODAY}"
    storage.supabase.table("posts").insert({
        "id": post_id, "article_title": title, "source": "Marchés",
        "category": "finance", "chart_type": kind, "relevance_score": 7,
        "verified": True, "status": "pending",
        "image_instagram": image_url, "image_twitter": image_url, "image_linkedin": image_url,
        "caption_instagram": f"📊 {_TITLES[kind]} — {TODAY} {caption_tag}",
        "caption_twitter": f"📊 {_TITLES[kind]} · {TODAY}",
        "caption_linkedin": f"{_TITLES[kind]} du {TODAY}",
    }).execute()
    print(f"[MARKETS+] Post créé : {title}")


def run_movers(weekly: bool):
    kind = "movers_week" if weekly else "movers_day"
    if _already_posted(kind):
        print(f"[MARKETS+] {kind} déjà posté — stop.")
        return
    gainers, losers = _movers(weekly)
    if not gainers:
        print("[MARKETS+] Aucune donnée actions — stop.")
        return
    title = "Top / Flop de la semaine" if weekly else "Top / Flop du jour"
    img = make_movers_post(gainers, losers, title, _date_label())
    _save(kind, img, "#bourse #actions #finance")


def run_sentiment():
    if _already_posted("sentiment"):
        print("[MARKETS+] sentiment déjà posté — stop.")
        return
    vix = _vix()
    fng_val, _ = _crypto_fng()
    if vix is None or fng_val is None:
        print("[MARKETS+] Données sentiment indisponibles — stop.")
        return
    img = make_sentiment_post(_vix_panel(vix), _fng_panel(fng_val), _date_label())
    _save("sentiment", img, "#VIX #crypto #sentiment")


def main():
    wd = date.today().weekday()   # 0=lundi … 6=dimanche
    print(f"=== MARCHÉS EXTRA · {TODAY} (jour {wd}) ===")
    if wd <= 4:
        run_movers(weekly=False)
    elif wd == 5:
        run_movers(weekly=True)
    else:
        run_sentiment()
    try:
        import notifier
        notifier.send("📊 Post marché (extra) publié")
    except Exception:
        pass
    print("=== FIN ===")


if __name__ == "__main__":
    main()
