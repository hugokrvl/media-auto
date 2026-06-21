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
COHERENCE_MIN  = int(os.environ.get("BREAKING_COHERENCE_MIN", "5"))
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
        '{"title_fr":"<titre FR percutant ≤90 car., colle au sujet>",'
        '"subtitle_fr":"<angle en 4-6 mots>",'
        '"people":[{"name":"<personne réelle, nom complet>","org":"<société>"}],'
        '"companies":[{"name":"<entreprise clé>","domain":"<domaine web, ex: tesla.com>"}],'
        '"image_query":"<2-3 mots-clés EN pour illustrer si ni personne ni entreprise>"}\n'
        "people : personnes réelles clés (max 3). IMPORTANT : si le sujet porte surtout "
        "sur une ENTREPRISE, inclus sa FIGURE EMBLÉMATIQUE même non citée — ex : "
        "Strategy/MicroStrategy→Michael Saylor, Tesla→Elon Musk, Nvidia→Jensen Huang, "
        "OpenAI→Sam Altman, Apple→Tim Cook, Meta→Mark Zuckerberg, Amazon→Andy Jassy. "
        "companies : entreprises clés du sujet avec leur domaine web (pour le logo), max 2. "
        "Sinon listes vides."
    )
    res = llm.generate_json(prompt, _ENRICH_SYS, max_tokens=600, temperature=0.4)
    if res:
        a["title_fr"] = (res.get("title_fr") or a["title"]).strip()[:120]
        a["subtitle_fr"] = (res.get("subtitle_fr") or "").strip()[:50]
        a["people"] = [p for p in (res.get("people") or []) if p.get("name")][:3]
        a["companies"] = [c for c in (res.get("companies") or []) if c.get("name")][:2]
        a["image_query"] = res.get("image_query", "")
    else:
        a["people"] = []
        a["companies"] = []
    return a


# ── 5. Image (montage si 2+ portraits) + rendu ─────────────────────────────────

def build_image(a: dict) -> tuple[bytes | None, str, str]:
    """Retourne (png_bytes, chart_type, description_image). Montage si ≥2 portraits,
    sinon portrait unique, sinon photo concept. description_image sert à la vérification."""
    people = a.get("people", [])
    seed = abs(hash(a.get("url") or a.get("title", "")))

    # MONTAGE : on n'assemble QUE des portraits CANONIQUES (infobox Wikipédia) → jamais
    # une photo de groupe / meme / cliché bizarre. La variété (rotation) est réservée au
    # portrait unique, où le risque est moindre.
    canon = []
    for p in people:
        url = image_fetch.portrait_canonical(p["name"])
        data = image_fetch.download_image(url) if url else None
        if data:
            canon.append({"name": p["name"], "label": p.get("org", ""), "photo_bytes": data})

    if len(canon) >= 2:
        names = ", ".join(p["name"] for p in canon[:4])
        return (montage_renderer.make_montage_image(a, canon, badge="BREAKING"),
                "montage", f"un montage des portraits officiels de {names}")

    # 1 dirigeant → portrait unique, en ROTATION (variété). Repli sur le canonique.
    if people:
        p0 = people[0]
        url = image_fetch.portrait_for(p0["name"], seed=seed)
        data = image_fetch.download_image(url) if url else None
        if not data and canon:
            data = canon[0]["photo_bytes"]
            p0 = {"name": canon[0]["name"], "org": canon[0]["label"]}
        if data:
            label = p0.get("org", "")
            desc = f"un portrait de {p0['name']}" + (f" ({label})" if label else "")
            return (breaking_renderer.make_breaking_image(a, data, badge="BREAKING"),
                    "breaking", desc)

    # Pas de dirigeant identifié : on privilégie la PHOTO CONCEPT de la requête IA
    # (propre et sûre) AVANT la recherche Wikipédia par mots du titre — qui peut matcher
    # un mot AMBIGU ("Codex" → manuscrit médiéval, "Vision" → œil, "Visa" → document…).
    url, desc = None, ""
    if a.get("image_query"):
        url = (image_fetch._fetch_unsplash(a["image_query"])
               or image_fetch._fetch_pexels(a["image_query"]))
        if url:
            desc = f"une photo d'illustration sur le thème « {a['image_query']} »"
    if not url:
        url = image_fetch.fetch_photo_url(a)   # repli : Wikipédia entités + Unsplash titre
        desc = "une image d'illustration (origine variable)"
    data = image_fetch.download_image(url) if url else None
    if data:
        return breaking_renderer.make_breaking_image(a, data, badge="BREAKING"), "breaking", desc
    return None, "", ""


# ── Vérification de cohérence (vision) ─────────────────────────────────────────

def verify_coherence(img_bytes: bytes, a: dict, image_desc: str) -> tuple[bool, int, str]:
    """L'IMAGE illustre-t-elle vraiment le sujet ? (via Mistral vision). Retourne
    (coherent, score 0-10, raison). Si Mistral indispo → ne bloque pas (coherent=True)."""
    if not mistral.available():
        return True, 10, "(vérif désactivée)"
    title = a.get("title_fr") or a.get("title", "")
    prompt = (
        f'Tu vérifies la cohérence d\'un post d\'actualité. SUJET du titre : "{title}". '
        f"La photo de fond est censée être : {image_desc}. REGARDE l'image. "
        "RÈGLES : un PORTRAIT d'une personne liée au sujet (dirigeant, personnalité) = COHÉRENT ; "
        "une photo CONCEPT du thème = COHÉRENT. Mets coherent=false UNIQUEMENT si l'image n'a "
        "MANIFESTEMENT RIEN à voir (ex : manuscrit/peinture ancienne pour une actu tech, "
        "animal pour la finance, paysage sans rapport). "
        'JSON : {"coherent":<bool>,"score":<0-10>,"raison":"<courte>"}'
    )
    res = mistral.generate_json_image(prompt, img_bytes)
    if not res:
        return True, 10, "(vérif indispo)"
    return bool(res.get("coherent", True)), int(res.get("score", 10)), str(res.get("raison", ""))


def _save(a: dict, img: bytes, chart_type: str) -> None:
    import storage
    from generator import generate_captions
    captions = generate_captions(a)
    post_id = str(uuid.uuid4())
    slug = chart_type
    image_urls = {net: storage.upload_image(img, f"{slug}_{post_id}_{net}.png")
                  for net in ("instagram", "twitter", "linkedin")}
    storage.save_post({**a, "chart_type": chart_type}, captions, image_urls)


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
            img, chart_type, image_desc = build_image(a)
            if not img:
                print(f"[SCAN] ⊘ pas d'image pour : {a['title'][:50]}")
                continue
            # VÉRIFICATION : l'image colle-t-elle au sujet ? (vision Mistral)
            coherent, score, reason = verify_coherence(img, a, image_desc)
            if not coherent or score < COHERENCE_MIN:
                print(f"[SCAN] ⊘ INCOHÉRENT ({score}/10 : {reason}) — ignoré : {a['title'][:42]}")
                continue
            _save(a, img, chart_type)
            posted += 1
            print(f"[SCAN] ✓ {chart_type.upper()} (cohérence {score}/10) : {a['title_fr'][:50]}")
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
