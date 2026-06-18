# -*- coding: utf-8 -*-
"""
Test de connexion RÉELLE à la boîte newsletters.
Charge media-auto/.env, se connecte en IMAP, liste les mails trouvés.
N'affiche JAMAIS le mot de passe ni le corps des mails — juste titres + expéditeurs.

Lancer :  cd pipeline && python _test_email_live.py
"""

import os

# Charge le .env du dossier parent (media-auto/.env) sans dépendance externe
here = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(here, "..", ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import email_sources as E

addr = os.environ.get("NEWSLETTER_EMAIL", "(non défini)")
print(f"Boîte    : {addr}")
print(f"Serveur  : {E._imap_host(addr)}")
print(f"Mot de passe défini : {'oui' if os.environ.get('NEWSLETTER_PASSWORD') else 'NON'}")
print("-" * 55)

# Fenêtre large (72h) pour être sûr d'attraper quelque chose
arts = E.fetch_newsletters(hours_back=72)
print("-" * 55)
print(f"{len(arts)} newsletter(s) exploitable(s) :")
for a in arts:
    print(f"  • [{a['source']}] {a['title'][:60]}")
if not arts:
    print("  (rien — soit la boîte est vide sur 72h, soit la connexion a échoué :")
    print("   vérifie le message [EMAIL] ci-dessus)")
