"""
Client Gemini (Google AI Studio, free tier) — via API REST, sans SDK ni dépendance.

Usage : rigueur d'analyse, vérification, titres qui collent à l'image, légendes pro.
Gratuit : ~15 req/min, 1500 req/jour sur Gemini Flash → largement suffisant.

Sans GEMINI_API_KEY, le module est inerte (available() == False) : le pipeline
retombe proprement sur Groq.
"""

import os
import json
import time
import urllib.request
import urllib.error

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"


def available() -> bool:
    return bool(API_KEY)


def _call(prompt: str, system: str, *, as_json: bool,
          max_tokens: int, temperature: float, retries: int = 3) -> str | None:
    if not API_KEY:
        return None
    url = f"{_BASE}/{MODEL}:generateContent?key={API_KEY}"
    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    if as_json:
        body["generationConfig"]["responseMimeType"] = "application/json"

    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            cands = resp.get("candidates", [])
            if not cands:
                return None
            parts = cands[0].get("content", {}).get("parts", [{}])
            return "".join(p.get("text", "") for p in parts).strip()
        except urllib.error.HTTPError as e:
            # 429 (quota) / 503 (surcharge) → back-off ; sinon on abandonne (repli Groq)
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            print(f"[GEMINI] HTTP {e.code} — repli")
            return None
        except Exception as e:
            print(f"[GEMINI] {type(e).__name__}: {e} — repli")
            return None
    return None


def generate_text(prompt: str, system: str = "", *,
                  max_tokens: int = 512, temperature: float = 0.7) -> str | None:
    return _call(prompt, system, as_json=False,
                 max_tokens=max_tokens, temperature=temperature)


def generate_json(prompt: str, system: str = "", *,
                  max_tokens: int = 1024, temperature: float = 0.4) -> dict | None:
    raw = _call(prompt, system, as_json=True,
                max_tokens=max_tokens, temperature=temperature)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # parfois entouré de ```json ... ``` malgré responseMimeType
        s = raw.strip().lstrip("`").lstrip("json").strip().rstrip("`").strip()
        try:
            return json.loads(s)
        except Exception:
            print("[GEMINI] JSON invalide — repli")
            return None


if __name__ == "__main__":
    if not available():
        print("GEMINI_API_KEY absente — module inerte.")
    else:
        print("Modèle :", MODEL)
        out = generate_json(
            "Donne un objet JSON {\"ok\": true, \"modele\": \"gemini\"} et rien d'autre.",
            "Tu réponds uniquement en JSON.")
        print("Réponse test :", out)
