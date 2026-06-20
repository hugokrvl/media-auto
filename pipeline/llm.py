"""
Sélecteur de fournisseur IA pour les tâches QUALITÉ (rigueur, titres, légendes).
Ordre : Mistral → Gemini → (None → l'appelant retombe sur Groq).

Interface unifiée generate_json / generate_text. Permet d'améliorer la qualité
là où ça compte sans dépendre d'un seul fournisseur ni casser le pipeline si une
clé manque (tout repli proprement sur Groq).
"""

import mistral
import gemini

_PROVIDERS = (mistral, gemini)


def provider():
    """Premier fournisseur disponible, ou None (→ repli Groq côté appelant)."""
    for p in _PROVIDERS:
        if p.available():
            return p
    return None


def name() -> str | None:
    p = provider()
    return p.__name__ if p else None


def generate_json(prompt: str, system: str = "", *,
                  max_tokens: int = 1024, temperature: float = 0.4) -> dict | None:
    p = provider()
    return p.generate_json(prompt, system, max_tokens=max_tokens,
                           temperature=temperature) if p else None


def generate_text(prompt: str, system: str = "", *,
                  max_tokens: int = 512, temperature: float = 0.7) -> str | None:
    p = provider()
    return p.generate_text(prompt, system, max_tokens=max_tokens,
                           temperature=temperature) if p else None
