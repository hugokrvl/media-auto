"""
Études « data » issues de DONNÉES OUVERTES officielles — complément du flux articles.

Contrairement aux articles (texte → l'IA extrait les chiffres), ici les chiffres sont
DÉJÀ propres et vérifiés : on les récupère d'une API publique et on construit directement
une étude prête (chart_data + titre + sous-titre + verdict + points clés, 100 % templatés,
ZÉRO token IA). L'étude entre ensuite dans le même moteur que les articles : dédup (ne
repostera pas une donnée inchangée) → carrousel → captions → Supabase.

v1 : **Banque mondiale** (JSON, sans clé, très riche). Extensible : ajouter Eurostat / FRED /
INSEE = écrire un fetcher et l'ajouter au registre STUDIES (kind = compare | series).

Réglages env : OPENDATA_ENABLED (1/0), OPENDATA_TIMEOUT.
Robuste : toute erreur réseau/API → l'étude est ignorée (le flux articles continue seul).
"""

import datetime
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import brand as B

ENABLED = os.environ.get("OPENDATA_ENABLED", "1") != "0"
TIMEOUT = int(os.environ.get("OPENDATA_TIMEOUT", "15"))
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()   # gratuit ; sans clé, FRED reste dormant
_UA = "Mozilla/5.0 (compatible; HKMediaBot/1.0)"

# Pays suivis (grandes économies) + libellés FR. iso3 World Bank.
_FR = {"USA": "États-Unis", "CHN": "Chine", "DEU": "Allemagne", "JPN": "Japon",
       "FRA": "France", "GBR": "Royaume-Uni", "ITA": "Italie", "ESP": "Espagne",
       "IND": "Inde", "BRA": "Brésil", "CAN": "Canada", "KOR": "Corée du Sud"}
_BIG = list(_FR.keys())

# Registre des études (chacune = 1 visuel). compare = classement de pays ; series = courbe FR.
STUDIES = [
    {"id": "pib", "kind": "compare", "indicator": "NY.GDP.MKTP.CD", "countries": _BIG,
     "top": 6, "scale": 1e9, "unit": "Md$", "category": "finance",
     "title": "Les plus grandes économies du monde",
     "subtitle": "PIB en milliards de dollars · Banque mondiale {year}"},
    {"id": "pibhab", "kind": "compare", "indicator": "NY.GDP.PCAP.CD", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "$", "category": "finance",
     "title": "PIB par habitant : le classement",
     "subtitle": "En dollars · Banque mondiale {year}"},
    {"id": "croissance", "kind": "compare", "indicator": "NY.GDP.MKTP.KD.ZG", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "%", "category": "finance",
     "title": "Croissance économique : qui accélère ?",
     "subtitle": "Croissance du PIB · Banque mondiale {year}"},
    {"id": "inflation", "kind": "compare", "indicator": "FP.CPI.TOTL.ZG", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "%", "category": "finance",
     "title": "Inflation : où la hausse des prix frappe le plus",
     "subtitle": "Hausse annuelle des prix · Banque mondiale {year}"},
    {"id": "chomage", "kind": "compare", "indicator": "SL.UEM.TOTL.ZS", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "%", "category": "finance",
     "title": "Le chômage dans les grandes économies",
     "subtitle": "Taux de chômage · Banque mondiale {year}"},
    {"id": "pop", "kind": "compare", "indicator": "SP.POP.TOTL", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "hab.", "category": "general",
     "title": "Les pays les plus peuplés du monde",
     "subtitle": "Population totale · Banque mondiale {year}"},
    {"id": "internet", "kind": "compare", "indicator": "IT.NET.USER.ZS", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "%", "category": "tech",
     "title": "Accès à internet : le classement mondial",
     "subtitle": "% de la population connectée · Banque mondiale {year}"},
    {"id": "rd", "kind": "compare", "indicator": "GB.XPD.RSDV.GD.ZS", "countries": _BIG,
     "top": 6, "scale": 1, "unit": "%", "category": "tech",
     "title": "Qui investit le plus dans la recherche ?",
     "subtitle": "Dépenses R&D, % du PIB · Banque mondiale {year}"},
    {"id": "pib_fr", "kind": "series", "indicator": "NY.GDP.MKTP.CD", "country": "FRA",
     "years": 15, "scale": 1e9, "unit": "Md$", "category": "finance",
     "title": "Le PIB de la France sur 15 ans",
     "subtitle": "En milliards de dollars · Banque mondiale"},
    {"id": "inflation_fr", "kind": "series", "indicator": "FP.CPI.TOTL.ZG", "country": "FRA",
     "years": 12, "scale": 1, "unit": "%", "category": "finance",
     "title": "L'inflation en France sur 12 ans",
     "subtitle": "Hausse annuelle des prix · Banque mondiale"},

    # ── FRED (Fed de St. Louis) — séries éco US. Nécessite FRED_API_KEY (gratuit) ; ──
    # ── sans clé, ces études sont simplement ignorées (la Banque mondiale continue). ──
    {"id": "fed", "provider": "fred", "kind": "series", "series_id": "FEDFUNDS", "years": 12,
     "scale": 1, "unit": "%", "country_fr": "Le taux directeur de la Fed", "category": "finance",
     "title": "Le taux directeur de la Fed sur 12 ans",
     "subtitle": "Taux effectif, moyenne annuelle · FRED"},
    {"id": "us_unemp", "provider": "fred", "kind": "series", "series_id": "UNRATE", "years": 12,
     "scale": 1, "unit": "%", "country_fr": "Le chômage américain", "category": "finance",
     "title": "Le chômage aux États-Unis sur 12 ans",
     "subtitle": "Taux de chômage, moyenne annuelle · FRED"},
    {"id": "us_10y", "provider": "fred", "kind": "series", "series_id": "DGS10", "years": 12,
     "scale": 1, "unit": "%", "country_fr": "Le taux à 10 ans américain", "category": "finance",
     "title": "Le taux à 10 ans américain sur 12 ans",
     "subtitle": "Rendement du Trésor 10 ans, moyenne annuelle · FRED"},
]


# ── Récupération World Bank (réseau) ─────────────────────────────────────────
def _wb_get(path: str, params: dict) -> list:
    q = urlencode({**params, "format": "json", "per_page": params.get("per_page", 1000)})
    req = Request(f"https://api.worldbank.org/v2/{path}?{q}", headers={"User-Agent": _UA})
    with urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    return data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []


def _wb_compare(indicator: str, isos: list) -> list:
    """Dernière valeur connue par pays (mrnev=1)."""
    recs = _wb_get(f"country/{';'.join(isos)}/indicator/{indicator}", {"mrnev": 1})
    return [{"iso3": r.get("countryiso3code"), "value": r.get("value"), "year": r.get("date")}
            for r in recs]


def _wb_series(indicator: str, country: str, years: int) -> list:
    end = datetime.date.today().year
    recs = _wb_get(f"country/{country}/indicator/{indicator}", {"date": f"{end - years}:{end}"})
    return [{"year": int(r["date"]), "value": r.get("value")} for r in recs if r.get("date")]


# ── Construction de l'étude (PUR — testable hors-ligne) ──────────────────────
def _study_dict(defn, chart_type, chart_data, key_points, insight, year):
    sub = defn["subtitle"].replace("{year}", str(year) if year else "").strip(" ·")
    if defn.get("provider") == "fred":
        source = "FRED · Fed de St. Louis"
        url = f"https://fred.stlouisfed.org/series/{defn.get('series_id', '')}"
    else:
        source = "Banque mondiale"
        url = f"https://data.worldbank.org/indicator/{defn.get('indicator', '')}"
    return {
        "title": defn["title"], "title_fr": defn["title"], "subtitle_fr": sub,
        "chart_type": chart_type, "chart_data": chart_data, "key_points": key_points,
        "insight": insight, "source": source, "category": defn.get("category", "finance"),
        "url": url, "score": 9, "verified": True, "is_opendata": True,
    }


def _u(unit):
    return f" {unit}" if unit else ""


def _build_compare(defn, recs):
    scale, unit = defn.get("scale", 1), defn.get("unit", "")
    rows = []
    year = None
    for r in recs:
        if r.get("value") is None:
            continue
        rows.append({"iso3": r["iso3"], "label": _FR.get(r["iso3"], r["iso3"]),
                     "value": round(r["value"] / scale, 2)})
        year = r.get("year")
    if len(rows) < 3:
        return None
    rows.sort(key=lambda x: x["value"], reverse=True)
    top = rows[:defn.get("top", 6)]
    chart = [{"label": x["label"], "value": x["value"]} for x in top]
    fr_rank = next((i + 1 for i, x in enumerate(rows) if x["iso3"] == "FRA"), None)
    fr_val = next((x["value"] for x in rows if x["iso3"] == "FRA"), None)
    leader = top[0]
    insight = f"{leader['label']} en tête avec {B.fr(leader['value'])}{_u(unit)}."
    if fr_rank:
        insight += f" La France est {fr_rank}e sur {len(rows)}."
    key_points = [f"{i + 1}. {x['label']} — {B.fr(x['value'])}{_u(unit)}" for i, x in enumerate(top[:3])]
    if fr_rank and fr_rank > 3 and fr_val is not None:
        key_points.append(f"France : {fr_rank}e ({B.fr(fr_val)}{_u(unit)})")
    return _study_dict(defn, "bar", chart, key_points, insight, year)


def _build_series(defn, pts):
    scale, unit = defn.get("scale", 1), defn.get("unit", "")
    pts = [p for p in pts if p.get("value") is not None]
    if len(pts) < 4:
        return None
    pts.sort(key=lambda p: p["year"])
    chart = [{"label": str(p["year"]), "value": round(p["value"] / scale, 2)} for p in pts]
    first, last = chart[0]["value"], chart[-1]["value"]
    pays = defn.get("country_fr") or _FR.get(defn.get("country", ""), "La France")
    # Un TAUX (%) qui passe de 0,1 à 5,3 n'a pas fait « +5200 % » → variation en POINTS.
    # Un NIVEAU (PIB en Md$…) → variation en pourcentage.
    if unit == "%":
        d = last - first
        change = (f"{'+' if d >= 0 else '−'}{abs(d):.1f} pt").replace(".", ",")
    else:
        pct = (last - first) / abs(first) * 100 if first else 0
        change = f"{'+' if pct >= 0 else '−'}{abs(pct):.0f} %"
    insight = (f"{pays} : de {B.fr(first)}{_u(unit)} à {B.fr(last)}{_u(unit)} "
               f"en {len(chart)} ans ({change}).")
    key_points = [f"Début ({chart[0]['label']}) : {B.fr(first)}{_u(unit)}",
                  f"Fin ({chart[-1]['label']}) : {B.fr(last)}{_u(unit)}",
                  f"Évolution : {change}"]
    return _study_dict(defn, "courbe", chart, key_points, insight, chart[-1]["label"])


def _fred_series(series_id: str, years: int) -> list:
    """Série FRED en fréquence ANNUELLE (moyenne) → ~12 points propres. [] sans clé/échec."""
    start = f"{datetime.date.today().year - years}-01-01"
    q = urlencode({"series_id": series_id, "api_key": FRED_KEY, "file_type": "json",
                   "observation_start": start, "frequency": "a",
                   "aggregation_method": "avg", "sort_order": "asc"})
    req = Request(f"https://api.stlouisfed.org/fred/series/observations?{q}",
                  headers={"User-Agent": _UA})
    with urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    out = []
    for o in data.get("observations", []):
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            out.append({"year": int(str(o["date"])[:4]), "value": float(v)})
        except Exception:
            pass
    return out


def build_study(defn):
    provider = defn.get("provider", "wb")
    if provider == "fred":
        if not FRED_KEY:                       # pas de clé → étude dormante (la Banque mondiale tourne)
            return None
        return _build_series(defn, _fred_series(defn["series_id"], defn.get("years", 12)))
    if defn["kind"] == "compare":
        return _build_compare(defn, _wb_compare(defn["indicator"], defn["countries"]))
    return _build_series(defn, _wb_series(defn["indicator"], defn["country"], defn.get("years", 12)))


def fetch_studies(max_n: int = 2) -> list:
    """Jusqu'à `max_n` études prêtes, en ROTATION quotidienne dans le registre (variété).
    Le dédup en aval écarte les données inchangées → pas de répétition."""
    if not ENABLED:
        return []
    n = len(STUDIES)
    doy = datetime.date.today().toordinal()
    order = [STUDIES[(doy * 7 + i) % n] for i in range(n)]  # rotation déterministe par jour
    out = []
    for defn in order:
        if len(out) >= max_n:
            break
        try:
            s = build_study(defn)
            if s:
                out.append(s)
        except Exception as e:
            print(f"[OPENDATA] {defn['id']} KO ({type(e).__name__}: {e})")
    return out


if __name__ == "__main__":
    # Test OFFLINE : on alimente les builders PURS avec des données simulées (pas de réseau),
    # puis on rend les carrousels pour vérifier le visuel.
    comp = _build_compare(STUDIES[0], [
        {"iso3": "USA", "value": 2.7e13, "year": "2024"}, {"iso3": "CHN", "value": 1.8e13, "year": "2024"},
        {"iso3": "DEU", "value": 4.5e12, "year": "2024"}, {"iso3": "JPN", "value": 4.2e12, "year": "2024"},
        {"iso3": "FRA", "value": 3.0e12, "year": "2024"}, {"iso3": "GBR", "value": 3.3e12, "year": "2024"},
        {"iso3": "ITA", "value": 2.1e12, "year": "2024"}])
    ser = _build_series(STUDIES[8], [{"year": y, "value": 2.0e12 + (y - 2010) * 9e10}
                                     for y in range(2010, 2025)])
    # Série de TAUX (FRED) → la variation doit être en POINTS, pas en % (anti +5200 %).
    rate = _build_series(
        {"kind": "series", "scale": 1, "unit": "%", "provider": "fred",
         "country_fr": "Le taux directeur de la Fed", "series_id": "FEDFUNDS",
         "title": "Le taux directeur de la Fed sur 12 ans",
         "subtitle": "Taux effectif, moyenne annuelle · FRED"},
        [{"year": y, "value": v} for y, v in zip(range(2013, 2025),
         [0.1, 0.1, 0.1, 0.4, 1.0, 1.8, 2.2, 0.4, 0.1, 1.7, 5.0, 5.3])])
    for s in (comp, ser, rate):
        print(f"\n{s['title']} | {s['subtitle_fr']} | {s['source']}")
        print(f"  insight : {s['insight']}")
        print(f"  points  : {s['key_points']}")
    import carousel
    for s, name in ((comp, "compare"), (ser, "series"), (rate, "rate")):
        for i, png in enumerate(carousel.generate_carousel(s), 1):
            open(f"test_od_{name}_{i}.png", "wb").write(png)
        print(f"{name} : carrousel rendu")
