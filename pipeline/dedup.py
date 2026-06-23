"""
Dédup intelligent — évite les vrais doublons MAIS suit l'actualité quand elle bouge.

Trois verdicts :
  • new        : sujet jamais traité            -> on publie
  • duplicate  : même sujet, mêmes chiffres     -> on jette
  • update     : même sujet, un chiffre/fait a changé -> on republie en "MISE À JOUR"

Mémoire = table Supabase `posts` (historique des N derniers jours) via deux empreintes :
  • topic_key : tokens significatifs du titre FR (de quoi on parle)
  • data_sig  : empreinte des chiffres clés / points clés (ce que dit l'info)

Dégradation gracieuse : si l'historique est injoignable, tout est "new"
(on ne bloque JAMAIS le pipeline pour un problème de dédup).
"""

import re
import unicodedata

# Mots-outils français à ignorer dans la signature de sujet
STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a",
    "au", "aux", "en", "dans", "sur", "sous", "par", "pour", "avec", "sans", "vers",
    "ce", "cet", "cette", "ces", "son", "sa", "ses", "leur", "leurs", "se", "qui",
    "que", "quoi", "dont", "ne", "pas", "plus", "moins", "tres", "est", "sont",
    "ete", "etre", "fait", "faire", "selon", "apres", "avant", "entre", "chez",
    "the", "of", "to", "in", "on", "for", "and", "is", "are", "new",
}

# Seuil de similarité de sujet (Jaccard sur les tokens) au-delà duquel on considère
# que deux articles parlent de la même chose.
SIM_THRESHOLD = 0.55
# Tolérance de variation relative d'un chiffre en dessous de laquelle on considère
# qu'il n'a PAS bougé (bruit d'arrondi). 0.02 = 2 %.
FIGURE_TOLERANCE = 0.02


def _norm(text: str) -> str:
    """Minuscule, sans accent, alphanumérique uniquement."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def _tokens(text: str) -> set:
    return {w for w in _norm(text).split() if len(w) > 2 and w not in STOPWORDS}


def topic_key(article: dict) -> str:
    """Empreinte de SUJET : tokens significatifs triés du titre FR."""
    title = article.get("title_fr") or article.get("title", "")
    return " ".join(sorted(_tokens(title)))


def _is_num(tok: str) -> bool:
    return tok.replace(".", "", 1).isdigit()


def _anchors(title: str) -> set:
    """Ancres à FORT signal, INVARIANTES à la langue / reformulation : noms propres
    (mots avec une majuscule → AbbVie, Apogee, Nvidia…) + nombres significatifs (10.9, 40…).
    Sert à reconnaître la MÊME info venue de sources différentes, là où le Jaccard du titre
    échoue (seuls les noms propres survivent à deux formulations différentes)."""
    out = set()
    for w in re.findall(r"[A-Za-zÀ-ÿ][\wÀ-ÿ'&.\-]*", title or ""):
        if any(c.isupper() for c in w):
            wn = _norm(w).strip()
            if len(wn) >= 3 and wn not in STOPWORDS:
                out.add(wn)
    for m in re.findall(r"\d+[.,]?\d*", title or ""):
        num = m.replace(",", ".").rstrip(".")
        if len(num.replace(".", "")) >= 2:      # ≥2 chiffres → écarte "3", années à part
            out.add(num)
    return out


# Mots TROP FRÉQUENTS pour identifier un sujet précis : ils ne comptent pas comme le
# 2e token distinctif partagé (sinon « Tesla + bourse » dédupliquerait trop large).
_GENERIC = {
    "bourse", "marche", "marches", "action", "actions", "prix", "hausse", "baisse", "cours",
    "dollar", "dollars", "euro", "euros", "titre", "titres", "groupe", "entreprise", "societe",
    "milliard", "milliards", "million", "millions", "record", "resultats", "resultat",
    "annonce", "annee", "semaine", "jour", "mois", "monde", "etats", "unis", "france",
    "europe", "americain", "americaine", "francais", "francaise", "chinois", "europeen",
    "nouveau", "nouvelle", "grand", "grande", "plan", "projet",
    "stock", "stocks", "market", "markets", "price", "company", "deal", "billion",
    "trillion", "news", "report", "update", "year", "week", "day", "world",
}


def data_sig(article: dict) -> str:
    """Empreinte de DONNÉES : 'label=valeur' triés (chart_data), sinon points clés."""
    parts = []
    for d in article.get("chart_data") or []:
        if isinstance(d, dict):
            lab = _norm(d.get("label", "")).strip()
            val = str(d.get("value", "")).replace(",", ".").strip()
            if lab or val:
                parts.append(f"{lab}={val}")
    if not parts:
        for p in article.get("key_points") or []:
            t = _norm(p).strip()
            if t:
                parts.append(t)
    return "|".join(sorted(parts))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_sig(sig: str) -> dict:
    """'a=3.2|b=4' -> {'a': 3.2, 'b': 4.0} (valeurs non numériques gardées en str)."""
    out = {}
    for part in (sig or "").split("|"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
        else:
            out[part] = True  # point clé textuel
    return out


def _figures_changed(new_sig: str, old_sig: str) -> bool:
    """True si l'info a matériellement bougé.

    Règle : un *chiffre partagé* (présent des deux côtés) a varié au-delà de la
    tolérance. Une métrique simplement absente du nouvel article (sous-ensemble)
    ne compte PAS comme une mise à jour — sinon on republierait pour rien.
    Pour les contenus purement textuels (points clés), on compare le texte brut.
    """
    nd, od = _parse_sig(new_sig), _parse_sig(old_sig)
    if not nd and not od:
        return False
    numeric = any(isinstance(v, float) for v in nd.values()) or \
              any(isinstance(v, float) for v in od.values())
    if not numeric:
        # Infographie / points clés : changement de texte = mise à jour
        return new_sig.strip() != old_sig.strip()
    # On ne juge que sur les métriques communes aux deux versions
    shared = [k for k in nd if k in od]
    for k in shared:
        a, b = nd[k], od[k]
        if isinstance(a, float) and isinstance(b, float):
            denom = max(abs(b), 1e-9)
            if abs(a - b) / denom > FIGURE_TOLERANCE:
                return True
        elif a != b:
            return True
    return False


def classify(article: dict, history: list[dict]) -> tuple[str, dict | None]:
    """
    Compare l'article à l'historique.

    history : liste de dicts avec au moins {article_url, topic_key, data_sig,
              category, article_title}.
    Retour : (status, matched) où status ∈ {"new", "update", "duplicate"}.
    """
    url = (article.get("url") or "").strip()
    tk = topic_key(article)
    ds = data_sig(article)
    a_tokens = set(tk.split())
    # Noms propres du titre (Trump, Bitcoin, AbbVie…), en minuscules comme les tokens.
    a_proper = {t for t in _anchors(article.get("title_fr") or article.get("title", ""))
                if not _is_num(t)}

    best, best_sim = None, 0.0
    for h in history:
        # 1. Même URL = même article -> doublon, sauf si les chiffres ont bougé
        if url and (h.get("article_url") or "").strip() == url:
            return ("update" if _figures_changed(ds, h.get("data_sig", "")) else "duplicate"), h
        h_tokens = set((h.get("topic_key") or "").split())
        # 1bis. MÊME INFO, SOURCES DIFFÉRENTES : ≥2 tokens significatifs partagés (hors mots
        #       génériques) dont AU MOINS un nom propre → même sujet même si formulé tout
        #       autrement (ex. 4 titres distincts sur « Trump + quantique »). Robuste là où
        #       le Jaccard du titre échoue.
        shared_dist = {t for t in (a_tokens & h_tokens)
                       if t not in _GENERIC and not t.isdigit()}   # exclut mots génériques + nombres nus
        if len(shared_dist) >= 2 and (shared_dist & a_proper):
            return ("update" if _figures_changed(ds, h.get("data_sig", "")) else "duplicate"), h
        sim = _jaccard(a_tokens, h_tokens)
        if h.get("category") and h.get("category") == article.get("category"):
            sim += 0.05
        if sim > best_sim:
            best_sim, best = sim, h

    if best is not None and best_sim >= SIM_THRESHOLD:
        return ("update" if _figures_changed(ds, best.get("data_sig", "")) else "duplicate"), best
    return "new", None


def semantic_duplicate(article: dict, candidates: list[dict]):
    """Demande à un PETIT modèle (Groq 8b, gros quota) si l'article parle du MÊME
    événement qu'un des candidats. Token-safe : 1 SEUL appel, titre + résumé court (≤300 car.)
    + quelques titres candidats. Renvoie le candidat matché ou None. Dégrade en None si pas
    de clé / erreur. Gère le multilingue (titre anglais vs historique français)."""
    cands = [c for c in (candidates or []) if (c.get("article_title") or "").strip()][:6]
    if not cands:
        return None
    try:
        import os
        import json as _json
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
    except Exception:
        return None
    desc = (article.get("summary") or "").strip()[:300]
    new = f"{(article.get('title_fr') or article.get('title', '')).strip()}" + (f" — {desc}" if desc else "")
    lst = "\n".join(f"{i}. {c.get('article_title', '')[:120]}" for i, c in enumerate(cands))
    prompt = (f"NOUVEL article :\n{new}\n\nArticles DÉJÀ publiés :\n{lst}\n\n"
              "L'un des articles déjà publiés parle-t-il du MÊME ÉVÉNEMENT / fait précis que "
              "le nouvel article (même annonce, même sujet, même chiffre clé) ? Les titres "
              "peuvent être formulés autrement ou dans une autre langue.\n"
              'Réponds en JSON : {"same": <true|false>, "i": <index de l\'article identique, sinon -1>}')
    try:
        model = os.environ.get("DEDUP_MODEL", "llama-3.1-8b-instant")
        r = client.chat.completions.create(
            model=model, temperature=0, max_tokens=40,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "Tu dédupliques l'actualité. JSON valide uniquement."},
                      {"role": "user", "content": prompt}])
        d = _json.loads(r.choices[0].message.content.strip())
        i = int(d.get("i", -1))
        if d.get("same") and 0 <= i < len(cands):
            return cands[i]
    except Exception as e:
        print(f"[DEDUP] juge sémantique indispo ({type(e).__name__})")
    return None


def classify_smart(article: dict, history: list[dict]) -> tuple[str, dict | None]:
    """classify() lexical (gratuit) PUIS, si « new » mais qu'il existe des candidats AMBIGUS
    (même nom propre, ou similarité moyenne), un check SÉMANTIQUE par petit modèle (1 appel)."""
    status, matched = classify(article, history)
    if status != "new":
        return status, matched
    a_proper = {t for t in _anchors(article.get("title_fr") or article.get("title", ""))
                if not _is_num(t)}
    a_tokens = set(topic_key(article).split())
    borderline = []
    for h in history:
        h_tokens = set((h.get("topic_key") or "").split())
        if (a_proper & h_tokens) or (0.30 <= _jaccard(a_tokens, h_tokens) < SIM_THRESHOLD):
            borderline.append(h)
    if borderline:
        m = semantic_duplicate(article, borderline)
        if m:
            return ("update" if _figures_changed(data_sig(article), m.get("data_sig", "")) else "duplicate"), m
    return "new", None


def annotate(article: dict) -> dict:
    """Pose les empreintes sur l'article (pour stockage / comparaison intra-run)."""
    article["topic_key"] = topic_key(article)
    article["data_sig"] = data_sig(article)
    return article


def as_history_row(article: dict) -> dict:
    """Représentation légère d'un article retenu, à empiler dans l'historique du run."""
    return {
        "article_url": (article.get("url") or "").strip(),
        "article_title": article.get("title", ""),
        "category": article.get("category", ""),
        "topic_key": article.get("topic_key") or topic_key(article),
        "data_sig": article.get("data_sig") or data_sig(article),
    }
