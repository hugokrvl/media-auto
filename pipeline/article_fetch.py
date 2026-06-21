"""
Récupération best-effort du TEXTE COMPLET d'un article (zéro dépendance, stdlib only).

But : donner à l'analyzer le corps entier de l'article (et pas seulement le résumé RSS)
pour capter les chiffres enfouis. Le texte est ensuite « digéré » par le modèle pas cher
(8b) avant d'atteindre le 70b → quota préservé (voir analyzer._digest_text).

Bascule automatique et SANS avantage de score :
  - la récupération a lieu APRÈS le triage → le score ne dépend QUE du résumé (équité) ;
  - si l'article est bloqué (paywall, anti-bot), trop court, non-HTML, ou passe par
    Google News (URL opaque) → on renvoie None → l'analyzer retombe sur le résumé RSS.

Réglages env : FULLTEXT_FETCH (1/0), FULLTEXT_MIN_CHARS, FULLTEXT_MAX_CHARS, FULLTEXT_TIMEOUT.
"""

import os
import re
import urllib.request
from html.parser import HTMLParser

FETCH_ENABLED = os.environ.get("FULLTEXT_FETCH", "1") != "0"
MIN_CHARS = int(os.environ.get("FULLTEXT_MIN_CHARS", "800"))    # en-dessous = paywall/échec
MAX_CHARS = int(os.environ.get("FULLTEXT_MAX_CHARS", "20000"))  # borne le digest
TIMEOUT = int(os.environ.get("FULLTEXT_TIMEOUT", "12"))

# Hôtes à NE PAS tenter : redirections opaques / pages non lisibles directement.
_SKIP_HOSTS = ("news.google.com", "google.com/url", "youtube.com", "youtu.be")
_UA = "Mozilla/5.0 (compatible; HKMediaBot/1.0; +veille éditoriale)"


class _Extractor(HTMLParser):
    """Extrait le texte des paragraphes <p>, en ignorant scripts/nav/aside…"""
    _SKIP = {"script", "style", "noscript", "nav", "header", "footer",
             "aside", "form", "figure", "figcaption", "button", "svg"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._in_p = 0
        self._buf = []
        self.paras = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "p" and self._skip_depth == 0:
            self._in_p += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "p" and self._in_p:
            self._in_p -= 1
            txt = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(txt) > 40:                      # ignore les <p> de chrome (boutons, dates…)
                self.paras.append(txt)
            self._buf = []

    def handle_data(self, data):
        if self._in_p and self._skip_depth == 0:
            self._buf.append(data)


def extract_text(html: str) -> str:
    """Texte des paragraphes d'une page HTML (sans réseau — testable hors-ligne)."""
    ex = _Extractor()
    try:
        ex.feed(html)
    except Exception:
        pass
    return "\n".join(ex.paras).strip()


def fetch_fulltext(url: str) -> str | None:
    """Texte complet de l'article, ou None si impossible (→ repli résumé RSS)."""
    if not FETCH_ENABLED or not url:
        return None
    if any(h in url for h in _SKIP_HOSTS):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                                   "Accept-Language": "fr,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if "html" not in (r.headers.get("Content-Type", "") or "").lower():
                return None
            raw = r.read(2_000_000)                # cap 2 Mo
        text = extract_text(raw.decode("utf-8", errors="ignore"))
        if len(text) < MIN_CHARS:                  # paywall / extraction trop maigre → repli
            return None
        return text[:MAX_CHARS]
    except Exception:
        return None


if __name__ == "__main__":
    sample = """<html><head><title>x</title><style>.a{}</style></head><body>
      <nav><p>Menu accueil contact</p></nav>
      <article>
        <p>La start-up a levé 40 millions d'euros en série B, portant sa valorisation à 300 millions.</p>
        <script>var x = 1;</script>
        <p>Le chiffre d'affaires a bondi de 120 % sur un an, pour atteindre 18 millions d'euros.</p>
        <p>ok</p>
      </article>
      <footer><p>Tous droits réservés 2026</p></footer>
    </body></html>"""
    print(extract_text(sample))
