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
    a_anchors = _anchors(article.get("title_fr") or article.get("title", ""))

    best, best_sim = None, 0.0
    for h in history:
        # 1. Même URL = même article -> doublon, sauf si les chiffres ont bougé
        if url and (h.get("article_url") or "").strip() == url:
            return ("update" if _figures_changed(ds, h.get("data_sig", "")) else "duplicate"), h
        # 1bis. MÊME INFO, SOURCE DIFFÉRENTE : ≥2 ancres partagées (dont ≥1 nom propre)
        #       → même sujet même si le titre est formulé tout autrement (multi-sources/langue).
        if len(a_anchors) >= 2:
            shared = a_anchors & _anchors(h.get("article_title", ""))
            if len(shared) >= 2 and any(not _is_num(s) for s in shared):
                return ("update" if _figures_changed(ds, h.get("data_sig", "")) else "duplicate"), h
        # 2. Similarité de sujet (petit bonus si même catégorie)
        h_tokens = set((h.get("topic_key") or "").split())
        sim = _jaccard(a_tokens, h_tokens)
        if h.get("category") and h.get("category") == article.get("category"):
            sim += 0.05
        if sim > best_sim:
            best_sim, best = sim, h

    if best is not None and best_sim >= SIM_THRESHOLD:
        return ("update" if _figures_changed(ds, best.get("data_sig", "")) else "duplicate"), best
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
