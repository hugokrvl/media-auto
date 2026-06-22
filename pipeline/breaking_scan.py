"""
Moteur de BREAKING NEWS quasi temps réel — éco / tech / IA / blockchain / quantique.
Lancé toutes les ~20 min par breaking_scan.yml.

Pipeline rapide :
  1. Récupère les articles TRÈS récents (≤ BREAKING_RECENT_MIN) des flux RSS directs
     des verticales (pas de Google News : on veut la vitesse).
  2. Dédoublonne vs l'historique (dedup.classify) → jamais 2× la même info.
  3. Jugement IA EN LOT (Mistral/Gemini) : ne garde que le fort impact + fiable.
  4. Pour les retenus (cap BREAKING_MAX_PER_SCAN) : titre FR qui colle au sujet,
     entités clés → PHOTO réelle, ou MONTAGE si 2+ dirigeants identifiés.
  5. Légende + sauvegarde Supabase (pending). Rien n'est publié sans validation.

Sans fournisseur IA qualité (Mistral/Gemini), on s'abstient de juger (sécurité :
mieux vaut ne rien poster qu'un breaking non vérifié).
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from calendar import timegm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import feedparser
import llm
import mistral
import image_fetch
import breaking as breaking_renderer
import montage as montage_renderer
import dedup

RECENT_MIN     = int(os.environ.get("BREAKING_RECENT_MIN", "45"))
MAX_PER_SCAN   = int(os.environ.get("BREAKING_MAX_PER_SCAN", "2"))
SCORE_MIN      = int(os.environ.get("BREAKING_SCORE_MIN", "7"))
COHERENCE_MIN  = int(os.environ.get("BREAKING_COHERENCE_MIN", "6"))
MAX_ATTEMPTS   = int(os.environ.get("BREAKING_MAX_ATTEMPTS", "3"))   # essais image avant abandon
VERTICALS      = {"ia", "crypto", "quantique", "tech", "finance"}


# ── 1. Candidats récents ───────────────────────────────────────────────────────

def fetch_candidates() -> list[dict]:
    from sources import SOURCES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RECENT_MIN)
    cutoff_ts = cutoff.timestamp()
    out, seen = [], set()
    for s in SOURCES:
        if s.get("type", "rss") != "rss" or s.get("category") not in VERTICALS:
            continue
        if "news.google.com" in s.get("url", ""):     # flux directs uniquement (vitesse)
            continue
        try:
            feed = feedparser.parse(s["url"])
        except Exception:
            continue
        for e in feed.entries[:20]:
            pub = e.get("published_parsed") or e.get("updated_parsed")
            if pub and timegm(pub) < cutoff_ts:
                continue
            link = e.get("link", "")
            title = (e.get("title") or "").strip()
            if not title or link in seen:
                continue
            seen.add(link)
            summary = (e.get("summary") or "")[:400]
            out.append({"title": title, "title_fr": title, "url": link,
                        "source": s["name"], "category": s["category"],
                        "summary": summary})
    return out


# ── 2. Dédoublonnage vs historique ─────────────────────────────────────────────

def dedupe(cands: list[dict]) -> list[dict]:
    try:
        import storage
        history = storage.get_recent_history(days=3)
    except Exception:
        history = []
    seen_urls = {h.get("article_url", "") for h in history}
    kept = []
    for a in cands:
        if a["url"] in seen_urls:
            continue
        dedup.annotate(a)
        status, _ = dedup.classify(a, history)
        if status == "duplicate":
            continue
        kept.append(a)
        history.append(dedup.as_history_row(a))
    return kept


# ── 3. Jugement IA en lot ──────────────────────────────────────────────────────

_JUDGE_SYS = ("Tu es rédacteur en chef d'un média ÉCONOMIE / TECH / IA / BLOCKCHAIN / "
              "QUANTIQUE, rigoureux et orienté vérité. Tu réponds UNIQUEMENT en JSON valide.")

def judge(cands: list[dict]) -> list[dict]:
    """Note chaque candidat en un seul appel. Garde breaking==true & score≥SCORE_MIN."""
    if not llm.provider() or not cands:
        return []
    lines = "\n".join(f'{i}. [{a["category"]}] {a["title"]}' for i, a in enumerate(cands[:25]))
    prompt = (
        "Voici des titres d'actualité très récents. Pour CHACUN, juge s'il mérite un "
        "post BREAKING (fort impact, fiable, pertinent pour un média éco/tech/IA/"
        "blockchain/quantique). Rejette le promotionnel, l'anecdotique, le non vérifiable.\n\n"
        f"{lines}\n\n"
        'Réponds en JSON : {"items":[{"i":<index>,"breaking":<bool>,'
        '"score":<0-10>,"category":"<finance|tech|ia|crypto|quantique>"}]}'
    )
    res = llm.generate_json(prompt, _JUDGE_SYS, max_tokens=1200, temperature=0.2)
    if not res or "items" not in res:
        return []
    kept = []
    for it in res["items"]:
        try:
            i = int(it["i"])
        except Exception:
            continue
        if 0 <= i < len(cands) and it.get("breaking") and int(it.get("score", 0)) >= SCORE_MIN:
            a = cands[i]
            a["score"] = int(it.get("score", 0))
            a["category"] = it.get("category", a["category"])
            a["verified"] = True
            kept.append(a)
    kept.sort(key=lambda x: -x["score"])
    return kept[:MAX_PER_SCAN]


# ── 4. Enrichissement : titre qui colle + entités pour montage ─────────────────

_ENRICH_SYS = ("Tu es rédacteur en chef. Titre PERCUTANT, FACTUEL, en FRANÇAIS, qui "
               "colle exactement au sujet (≤ 90 caractères). Réponds UNIQUEMENT en JSON.")

def enrich(a: dict) -> dict:
    prompt = (
        f"Article : {a['title']}\nSource : {a['source']}\nRésumé : {a['summary'][:300]}\n\n"
        "Donne en JSON :\n"
        '{"title_fr":"<titre FR percutant ≤90 car., colle EXACTEMENT au sujet>",'
        '"subtitle_fr":"<angle en 4-6 mots>",'
        '"people":[{"name":"<personne réelle, nom complet>","org":"<société>"}],'
        '"image_query":"<scène concrète EN, 3-5 mots, à utiliser si people est VIDE>"}\n\n'
        "RÈGLE people (CRUCIAL — éviter de mettre un MAUVAIS visage) :\n"
        "- Une personne SEULEMENT si elle est VRAIMENT au cœur de CETTE actu : soit nommée "
        "dans le titre/résumé, soit le dirigeant emblématique de L'ENTREPRISE précise dont "
        "parle le sujet (OpenAI→Sam Altman, Tesla→Elon Musk, Nvidia→Jensen Huang, "
        "Apple→Tim Cook, Palantir→Alex Karp, MicroStrategy→Michael Saylor…).\n"
        "- N'ajoute JAMAIS quelqu'un juste parce qu'il est connu du secteur. Si le sujet est "
        "un PAYS, un MARCHÉ, une TENDANCE, une techno, ou plusieurs entreprises non liées → "
        "people: [] (on prendra une photo concept).\n"
        "- Mets 2+ personnes SEULEMENT si elles sont TOUTES protagonistes du MÊME événement "
        "(deux dirigeants qui négocient, un rachat A↔B, un face-à-face). Sinon UNE seule.\n\n"
        "RÈGLE image_query (si people vide) : une scène CONCRÈTE qui colle au sujet ET à son "
        "TON. Ex : chute du pétrole→'oil price crash red chart' ; pénurie→'empty gas station' ; "
        "JAMAIS le sens contraire (pas de flèche verte/croissance pour une baisse). Évite les "
        "clichés génériques (poignée de main, pièces de monnaie, ampoule)."
    )
    res = llm.generate_json(prompt, _ENRICH_SYS, max_tokens=600, temperature=0.4)
    if res:
        a["title_fr"] = (res.get("title_fr") or a["title"]).strip()[:120]
        a["subtitle_fr"] = (res.get("subtitle_fr") or "").strip()[:50]
        a["people"] = [p for p in (res.get("people") or []) if p.get("name")][:3]
        a["image_query"] = res.get("image_query", "")
    else:
        a["people"] = []
    return a


# ── 5. Image (montage si 2+ portraits) + rendu ─────────────────────────────────

def image_candidates(a: dict):
    """Génère (PAR ORDRE de préférence, LAZY) des visuels candidats (png, type, desc).
    On ne calcule le suivant que si le précédent a raté la barrière QA → auto-correction."""
    people = a.get("people", [])
    seed = abs(hash(a.get("url") or a.get("title", "")))

    # Portraits CANONIQUES (infobox Wikipédia) → fiables, pour le montage.
    canon = []
    for p in people:
        url = image_fetch.portrait_canonical(p["name"])
        data = image_fetch.download_image(url) if url else None
        if data:
            canon.append({"name": p["name"], "label": p.get("org", ""), "photo_bytes": data})

    # 1) MONTAGE (≥2 portraits canoniques)
    if len(canon) >= 2:
        names = ", ".join(p["name"] for p in canon[:4])
        yield (montage_renderer.make_montage_image(a, canon, badge="BREAKING"),
               "montage", f"un montage des portraits officiels de {names}")

    # 2) PORTRAIT UNIQUE (rotation pour la variété, repli sur le canonique)
    if people:
        p0 = people[0]
        url = image_fetch.portrait_for(p0["name"], seed=seed)
        data = image_fetch.download_image(url) if url else None
        if not data and canon:
            data, p0 = canon[0]["photo_bytes"], {"name": canon[0]["name"], "org": canon[0]["label"]}
        if data:
            label = p0.get("org", "")
            desc = f"un portrait de {p0['name']}" + (f" ({label})" if label else "")
            yield (breaking_renderer.make_breaking_image(a, data, badge="BREAKING"), "breaking", desc)

    # 3) PHOTO CONCEPT (requête IA) — propre et sûre, AVANT la cascade par mots du titre
    seen = None
    if a.get("image_query"):
        url = (image_fetch._fetch_unsplash(a["image_query"])
               or image_fetch._fetch_pexels(a["image_query"]))
        data = image_fetch.download_image(url) if url else None
        if data:
            seen = url
            yield (breaking_renderer.make_breaking_image(a, data, badge="BREAKING"),
                   "breaking", f"une photo d'illustration sur le thème « {a['image_query']} »")

    # 4) REPLI : cascade Wikipédia (entités) → Unsplash (titre)
    url = image_fetch.fetch_photo_url(a)
    if url and url != seen:
        data = image_fetch.download_image(url)
        if data:
            yield (breaking_renderer.make_breaking_image(a, data, badge="BREAKING"),
                   "breaking", "une image d'illustration (origine variable)")


# ── Vérification de cohérence (vision) ─────────────────────────────────────────

def verify_coherence(img_bytes: bytes, a: dict, image_desc: str) -> tuple[bool, int, str]:
    """L'IMAGE illustre-t-elle vraiment le sujet ? (via Mistral vision). Retourne
    (coherent, score 0-10, raison). Si Mistral indispo → ne bloque pas (coherent=True)."""
    if not mistral.available():
        return True, 10, "(vérif désactivée)"
    title = a.get("title_fr") or a.get("title", "")
    prompt = (
        "Tu es DIRECTEUR ARTISTIQUE d'un média sérieux. Juge si cette image est DIGNE D'ÊTRE "
        f'PUBLIÉE pour ce post.\nTITRE : "{title}"\nImage censée montrer : {image_desc}.\n'
        "REGARDE vraiment l'image et note-la de 0 à 10. Mets coherent=false (note basse) si :\n"
        "- la/les PERSONNE(S) montrée(s) ne sont PAS le vrai sujet du titre ;\n"
        "- l'image CONTREDIT le sens (ex : flèche verte / hausse pour une chute ou un péril) ;\n"
        "- l'image n'est PAS professionnelle : torse nu, meme, photo de GROUPE floue, "
        "déguisement/cosplay, capture d'écran, image cassée ou trop sombre/illisible ;\n"
        "- le TEXTE incrusté est illisible, coupé, déborde, se chevauche, ou contient des "
        "carrés vides (glyphes manquants) / un layout cassé ;\n"
        "- cliché 100 % générique sans lien précis avec ce sujet.\n"
        "coherent=true (note haute) SEULEMENT si l'image est PRO et colle au sujet ET au ton : "
        "le portrait de LA bonne personne, ou une photo concept précise et cohérente avec l'angle.\n"
        'JSON : {"coherent":<bool>,"score":<0-10>,"raison":"<courte>"}'
    )
    res = mistral.generate_json_image(prompt, img_bytes)
    if not res:
        return True, 10, "(vérif indispo)"
    return bool(res.get("coherent", True)), int(res.get("score", 10)), str(res.get("raison", ""))


def _save(a: dict, img: bytes, chart_type: str, attempts: list = None) -> None:
    import storage
    from generator import generate_captions
    captions = generate_captions(a)
    post_id = str(uuid.uuid4())
    slug = chart_type
    image_urls = {net: storage.upload_image(img, f"{slug}_{post_id}_{net}.png")
                  for net in ("instagram", "twitter", "linkedin")}
    storage.save_post({**a, "chart_type": chart_type}, captions, image_urls, attempts=attempts)


# ── Orchestrateur ──────────────────────────────────────────────────────────────

def main():
    print(f"=== BREAKING SCAN · {datetime.now(timezone.utc).isoformat(timespec='minutes')} ===")
    if not llm.provider():
        print("⚠️  Aucun fournisseur IA qualité (Mistral/Gemini) — scan annulé (sécurité).")
        return
    print(f"[SCAN] Fournisseur IA : {llm.name()}")

    cands = fetch_candidates()
    print(f"[SCAN] {len(cands)} article(s) récent(s) (≤ {RECENT_MIN} min)")
    cands = dedupe(cands)
    print(f"[SCAN] {len(cands)} après dédoublonnage")
    if not cands:
        print("=== rien de neuf ===")
        return

    kept = judge(cands)
    print(f"[SCAN] {len(kept)} breaking retenu(s) par l'IA")

    posted = 0
    for a in kept:
        try:
            enrich(a)
            # BARRIÈRE QA + AUTO-CORRECTION : on essaie les visuels candidats l'un après
            # l'autre ; chacun doit passer la vérif vision. Les ratés sont GARDÉS (trace).
            attempts, chosen = [], None
            for img, ctype, desc in image_candidates(a):
                coherent, score, reason = verify_coherence(img, a, desc)
                if coherent and score >= COHERENCE_MIN:
                    chosen = (img, ctype, desc, score)
                    break
                try:
                    import storage
                    rej = storage.upload_image(img, f"rejet_{uuid.uuid4().hex[:8]}.png")
                except Exception:
                    rej = ""
                attempts.append({"image": rej, "type": ctype, "score": score,
                                 "raison": reason or "image jugée non conforme"})
                print(f"[SCAN] ↻ essai raté ({ctype}, {score}/10 : {reason}) → on refait")
                if len(attempts) >= MAX_ATTEMPTS:
                    break
            if not chosen:
                print(f"[SCAN] ⊘ aucun visuel valide ({len(attempts)} essai(s)) : {a['title'][:40]}")
                continue
            img, ctype, _, score = chosen
            _save(a, img, ctype, attempts=attempts or None)
            posted += 1
            tag = f" après {len(attempts)} essai(s) raté(s)" if attempts else ""
            print(f"[SCAN] ✓ {ctype.upper()} (QA {score}/10{tag}) : {a['title_fr'][:46]}")
        except Exception as e:
            print(f"[SCAN] ✗ {type(e).__name__} sur '{a['title'][:40]}': {e}")

    if posted:
        try:
            import notifier
            notifier.send(f"⚡ {posted} breaking publié(s)")
        except Exception:
            pass
    print(f"=== FIN : {posted} post(s) ===")


if __name__ == "__main__":
    main()
