"""
Client Mistral AI (La Plateforme, free tier) — via API REST, sans SDK ni dépendance.
Interface identique à gemini.py → interchangeable (rigueur d'analyse, titres, légendes).

Clé gratuite : https://console.mistral.ai → API Keys (plan « Experiment » gratuit).
Sans MISTRAL_API_KEY, le module est inerte (available() == False) → repli sur Groq.
"""

import os
import json
import time
import urllib.request
import urllib.error

API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MODEL   = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
_URL    = "https://api.mistral.ai/v1/chat/completions"


def available() -> bool:
    return bool(API_KEY)


def _call(prompt: str, system: str, *, as_json: bool,
          max_tokens: int, temperature: float, retries: int = 3) -> str | None:
    if not API_KEY:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body: dict = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if as_json:
        body["response_format"] = {"type": "json_object"}

    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(_URL, data=data, headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            return resp["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            # 429 (quota/débit) → back-off ; sinon abandon (repli Groq)
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            print(f"[MISTRAL] HTTP {e.code} — repli")
            return None
        except Exception as e:
            print(f"[MISTRAL] {type(e).__name__}: {e} — repli")
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
        s = raw.strip().lstrip("`").lstrip("json").strip().rstrip("`").strip()
        try:
            return json.loads(s)
        except Exception:
            print("[MISTRAL] JSON invalide — repli")
            return None


if __name__ == "__main__":
    if not available():
        print("MISTRAL_API_KEY absente — module inerte.")
    else:
        print("Modèle :", MODEL)
        out = generate_json(
            "Réponds en JSON : {\"ok\": true, \"modele\": \"mistral\"} et rien d'autre.",
            "Tu réponds uniquement en JSON valide.")
        print("Réponse test :", out)
