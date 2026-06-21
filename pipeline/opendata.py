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
import xml.etree.ElementTree as ET
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

# Pays UE (codes Eurostat = ISO2). Pas d'agrégat UE27 dans les classements (il écraserait tout).
_EU_FR = {"FR": "France", "DE": "Allemagne", "IT": "Italie", "ES": "Espagne", "NL": "Pays-Bas",
          "BE": "Belgique", "PL": "Pologne", "SE": "Suède", "AT": "Autriche", "PT": "Portugal",
          "IE": "Irlande", "GR": "Grèce", "FI": "Finlande", "DK": "Danemark"}
_EU = list(_EU_FR.keys())

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

    # ── Eurostat (UE, SANS clé) — classements de pays européens, données fraîches. ──
    {"id": "eu_gdp", "provider": "eurostat", "kind": "compare", "dataset": "nama_10_gdp",
     "geos": _EU, "filters": {"freq": "A", "unit": "CP_MEUR", "na_item": "B1GQ"},
     "top": 6, "scale": 1e3, "unit": "Md€", "category": "finance",
     "title": "Les plus grandes économies d'Europe",
     "subtitle": "PIB en milliards d'euros · Eurostat {year}"},
    {"id": "eu_inflation", "provider": "eurostat", "kind": "compare", "dataset": "prc_hicp_aind",
     "geos": _EU, "filters": {"freq": "A", "unit": "RCH_A_AVG", "coicop": "CP00"},
     "top": 6, "scale": 1, "unit": "%", "category": "finance",
     "title": "Inflation en Europe : où les prix flambent",
     "subtitle": "Hausse des prix (IPCH) · Eurostat {year}"},
    {"id": "eu_unemp", "provider": "eurostat", "kind": "compare", "dataset": "une_rt_a",
     "geos": _EU, "filters": {"freq": "A", "age": "Y15-74", "sex": "T", "unit": "PC_ACT"},
     "top": 6, "scale": 1, "unit": "%", "category": "finance",
     "title": "Le chômage en Europe : le classement",
     "subtitle": "Taux de chômage · Eurostat {year}"},

    # ── INSEE · BDM (données FRANÇAISES, SANS clé, XML SDMX) — séries par idBank. ──
    {"id": "fr_inflation_insee", "provider": "insee", "kind": "series", "idbank": "001761313",
     "years": 12, "scale": 1, "unit": "%", "country_fr": "L'inflation en France", "category": "finance",
     "title": "L'inflation en France sur 12 ans",
     "subtitle": "Glissement annuel des prix · INSEE"},
    {"id": "fr_chomage_insee", "provider": "insee", "kind": "series", "idbank": "001688370",
     "years": 12, "scale": 1, "unit": "%", "country_fr": "Le chômage en France", "category": "finance",
     "title": "Le chômage en France sur 12 ans",
     "subtitle": "Taux de chômage (BIT), moyenne annuelle · INSEE"},
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
    provider = defn.get("provider", "wb")
    if provider == "fred":
        source = "FRED · Fed de St. Louis"
        url = f"https://fred.stlouisfed.org/series/{defn.get('series_id', '')}"
    elif provider == "eurostat":
        source = "Eurostat"
        url = f"https://ec.europa.eu/eurostat/databrowser/view/{defn.get('dataset', '')}"
    elif provider == "insee":
        source = "INSEE"
        url = f"https://www.insee.fr/fr/statistiques/serie/{defn.get('idbank', '')}"
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


def _build_compare(defn, recs, labels=None, home="FRA"):
    labels = labels or _FR
    scale, unit = defn.get("scale", 1), defn.get("unit", "")
    rows = []
    year = None
    for r in recs:
        if r.get("value") is None:
            continue
        rows.append({"iso3": r["iso3"], "label": labels.get(r["iso3"], r["iso3"]),
                     "value": round(r["value"] / scale, 2)})
        year = r.get("year")
    if len(rows) < 3:
        return None
    rows.sort(key=lambda x: x["value"], reverse=True)
    top = rows[:defn.get("top", 6)]
    chart = [{"label": x["label"], "value": x["value"]} for x in top]
    fr_rank = next((i + 1 for i, x in enumerate(rows) if x["iso3"] == home), None)
    fr_val = next((x["value"] for x in rows if x["iso3"] == home), None)
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


# ── Eurostat (JSON-stat 2.0) ─────────────────────────────────────────────────
def _eurostat_get(dataset: str, geos: list, filters: dict) -> dict:
    q = [("format", "JSON")]
    for k, v in filters.items():
        q.append((k, v))
    for g in geos:
        q.append(("geo", g))
    q.append(("lastTimePeriod", "3"))          # 3 dernières périodes → repli par pays si trou
    url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
           f"{dataset}?{urlencode(q)}")
    req = Request(url, headers={"User-Agent": _UA})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _js_strides(size: list) -> list:
    """Pas (row-major) pour convertir des indices de catégorie en indice plat JSON-stat."""
    strides = [1] * len(size)
    for i in range(len(size) - 2, -1, -1):
        strides[i] = strides[i + 1] * size[i + 1]
    return strides


def _js_latest_by_geo(js: dict, prefer: dict) -> tuple:
    """{code_pays: valeur} pour la dernière période dispo PAR pays. prefer fixe les autres
    dimensions (unit, na_item…) par code ; à défaut, indice 0."""
    ids, size, dims, values = js["id"], js["size"], js["dimension"], js["value"]
    strides = _js_strides(size)
    geo_pos, time_pos = ids.index("geo"), ids.index("time")
    time_desc = sorted(dims["time"]["category"]["index"].items(),
                       key=lambda kv: kv[1], reverse=True)          # (code, idx) décroissant
    base = 0
    for pos, dim in enumerate(ids):
        if dim in ("geo", "time"):
            continue
        idx = dims[dim]["category"]["index"]
        code = prefer.get(dim)
        base += (idx.get(code, 0) if code else 0) * strides[pos]
    out, year = {}, None
    for gcode, gi in dims["geo"]["category"]["index"].items():
        for tcode, ti in time_desc:
            v = values.get(str(base + gi * strides[geo_pos] + ti * strides[time_pos]))
            if v is not None:
                out[gcode] = v
                year = year or tcode
                break
    return out, year


# ── INSEE · BDM (XML SDMX 2.1, sans clé) ─────────────────────────────────────
def _insee_obs(raw: bytes) -> list:
    """Observations (period, valeur) d'une réponse SDMX-ML : <Obs TIME_PERIOD=.. OBS_VALUE=../>."""
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    out = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "Obs":          # tag local "Obs" (avec ou sans namespace)
            t, v = el.attrib.get("TIME_PERIOD"), el.attrib.get("OBS_VALUE")
            if t and v not in (None, ""):
                try:
                    out.append((t, float(v)))
                except Exception:
                    pass
    return out


def _insee_series(idbank: str, years: int) -> list:
    """Série INSEE par idBank → moyenne ANNUELLE (gère mensuel/trimestriel via l'année period[:4])."""
    start = datetime.date.today().year - years
    url = f"https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbank}?startPeriod={start}"
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/xml"})
    with urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    by_year = {}
    for period, val in _insee_obs(raw):
        y = str(period)[:4]
        if y.isdigit():
            by_year.setdefault(y, []).append(val)
    return [{"year": int(y), "value": sum(vs) / len(vs)} for y, vs in sorted(by_year.items())]


def build_study(defn):
    provider = defn.get("provider", "wb")
    if provider == "fred":
        if not FRED_KEY:                       # pas de clé → étude dormante (la Banque mondiale tourne)
            return None
        return _build_series(defn, _fred_series(defn["series_id"], defn.get("years", 12)))
    if provider == "eurostat":
        js = _eurostat_get(defn["dataset"], defn["geos"], defn.get("filters", {}))
        by_geo, year = _js_latest_by_geo(js, defn.get("filters", {}))
        recs = [{"iso3": c, "value": v, "year": year} for c, v in by_geo.items()]
        return _build_compare(defn, recs, labels=_EU_FR, home="FR")
    if provider == "insee":
        return _build_series(defn, _insee_series(defn["idbank"], defn.get("years", 12)))
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


def diagnose():
    """Vérif LIVE : tente de construire CHAQUE étude du registre et rapporte par fournisseur
    OK / vide / erreur. Sert à confirmer les codes Eurostat + idBanks INSEE + clé FRED en réel.
    Usage CI : python -c "import opendata; opendata.diagnose()" — ne publie RIEN."""
    print(f"FRED_API_KEY : {'présente' if FRED_KEY else 'ABSENTE (études FRED ignorées)'}\n")
    ok = 0
    for d in STUDIES:
        prov = d.get("provider", "wb")
        try:
            s = build_study(d)
            if s and s.get("chart_data"):
                print(f"[OK]   {prov:9} {d['id']:20} {len(s['chart_data'])} pts · {s['source']}"
                      f"  « {s['insight'][:60]} »")
                ok += 1
            else:
                print(f"[VIDE] {prov:9} {d['id']:20} aucune donnée (seuil/clé/code ?)")
        except Exception as e:
            print(f"[ERR]  {prov:9} {d['id']:20} {type(e).__name__}: {str(e)[:80]}")
    print(f"\n→ {ok}/{len(STUDIES)} études construites en live.")


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
    # Eurostat : test du parseur JSON-stat (indice plat row-major + repli de période/pays).
    # IT n'a pas 2024 ici → doit retomber sur 2023 ; FR/DE en 2024. Vérifie aussi le rang FR.
    js = {
        "id": ["freq", "unit", "na_item", "geo", "time"], "size": [1, 1, 1, 3, 2],
        "dimension": {
            "freq": {"category": {"index": {"A": 0}}},
            "unit": {"category": {"index": {"CP_MEUR": 0}}},
            "na_item": {"category": {"index": {"B1GQ": 0}}},
            "geo": {"category": {"index": {"DE": 0, "FR": 1, "IT": 2}}},
            "time": {"category": {"index": {"2023": 0, "2024": 1}}},
        },
        "value": {"1": 4_200_000, "3": 2_900_000, "4": 2_000_000},  # DE2024, FR2024, IT2023(repli)
    }
    by_geo, yr = _js_latest_by_geo(js, {"freq": "A", "unit": "CP_MEUR", "na_item": "B1GQ"})
    assert by_geo == {"DE": 4_200_000, "FR": 2_900_000, "IT": 2_000_000}, by_geo
    assert yr == "2024", yr
    eu_defn = next(s for s in STUDIES if s["id"] == "eu_gdp")
    eu = _build_compare(eu_defn, [{"iso3": c, "value": v, "year": yr} for c, v in by_geo.items()],
                        labels=_EU_FR, home="FR")
    print(f"\n[JSON-stat OK] by_geo={by_geo} year={yr}")

    # INSEE : test du parseur XML SDMX (Obs namespacé, attributs TIME_PERIOD/OBS_VALUE).
    insee_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<StructureSpecificData xmlns="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/structurespecific">
  <DataSet><Series IDBANK="001761313">
    <Obs TIME_PERIOD="2020-06" OBS_VALUE="0.2"/><Obs TIME_PERIOD="2020-12" OBS_VALUE="0.0"/>
    <Obs TIME_PERIOD="2021-06" OBS_VALUE="1.5"/><Obs TIME_PERIOD="2021-12" OBS_VALUE="2.8"/>
    <Obs TIME_PERIOD="2022-06" OBS_VALUE="5.8"/><Obs TIME_PERIOD="2022-12" OBS_VALUE="5.9"/>
    <Obs TIME_PERIOD="2023-06" OBS_VALUE="4.5"/><Obs TIME_PERIOD="2023-12" OBS_VALUE="3.7"/>
    <Obs TIME_PERIOD="2024-06" OBS_VALUE="2.1"/><Obs TIME_PERIOD="2024-12" OBS_VALUE="1.3"/>
  </Series></DataSet>
</StructureSpecificData>"""
    obs = _insee_obs(insee_xml)
    assert len(obs) == 10 and obs[0] == ("2020-06", 0.2), obs[:2]
    by_year = {}
    for p, v in obs:
        by_year.setdefault(p[:4], []).append(v)
    pts = [{"year": int(y), "value": sum(vs) / len(vs)} for y, vs in sorted(by_year.items())]
    insee = _build_series(next(s for s in STUDIES if s["id"] == "fr_inflation_insee"), pts)
    print(f"[INSEE OK] {len(obs)} obs → {len(pts)} ans annualisés")

    for s in (comp, ser, rate, eu, insee):
        print(f"\n{s['title']} | {s['subtitle_fr']} | {s['source']}")
        print(f"  insight : {s['insight']}")
        print(f"  points  : {s['key_points']}")
    import carousel
    for s, name in ((comp, "compare"), (ser, "series"), (rate, "rate"),
                    (eu, "eurostat"), (insee, "insee")):
        for i, png in enumerate(carousel.generate_carousel(s), 1):
            open(f"test_od_{name}_{i}.png", "wb").write(png)
        print(f"{name} : carrousel rendu")
