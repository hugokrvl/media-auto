"""
Teste en réel chaque source de sources.py et affiche un rapport.
À lancer EN LOCAL (avec accès internet) :  python validate_sources.py

Pour chaque source :
  • rss     -> nb d'entrées trouvées
  • youtube -> résolution du flux + nb de vidéos
  • email   -> ignorée ici (testée par le pipeline si secrets configurés)

Les sources à 0 entrée / en erreur sont à corriger ou retirer de sources.py.
"""

import feedparser
import youtube
from sources import SOURCES


def main():
    ok, dead = [], []
    print(f"{'SOURCE':28} {'TYPE':8} {'N':>4}  ÉTAT")
    print("-" * 60)
    for s in SOURCES:
        name = s["name"]
        stype = s.get("type", "rss")
        if stype == "email":
            print(f"{name:28} {stype:8} {'-':>4}  (testé par le pipeline)")
            continue
        try:
            if stype == "youtube":
                feed_url = youtube.resolve_feed(s["url"])
                if not feed_url:
                    print(f"{name:28} {stype:8} {'ERR':>4}  channelId introuvable")
                    dead.append(name)
                    continue
                f = feedparser.parse(feed_url)
            else:
                f = feedparser.parse(s["url"])
            n = len(f.entries)
            state = "OK" if n else "VIDE — à corriger"
            print(f"{name:28} {stype:8} {n:>4}  {state}")
            (ok if n else dead).append(name)
        except Exception as e:
            print(f"{name:28} {stype:8} {'ERR':>4}  {type(e).__name__}: {str(e)[:30]}")
            dead.append(name)

    print("-" * 60)
    print(f"✅ {len(ok)} source(s) OK   ❌ {len(dead)} à corriger/retirer")
    if dead:
        print("À revoir :", ", ".join(dead))


if __name__ == "__main__":
    main()
