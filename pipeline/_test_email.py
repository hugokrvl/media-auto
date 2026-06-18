# -*- coding: utf-8 -*-
import email_sources as E

print("=== Auto-detection serveur IMAP ===")
for addr, exp in [("assistant_hk@outlook.fr", "outlook.office365.com"),
                  ("x@gmail.com", "imap.gmail.com"),
                  ("y@yahoo.fr", "imap.mail.yahoo.com"),
                  ("z@icloud.com", "imap.mail.me.com")]:
    got = E._imap_host(addr)
    print(f"  {'OK' if got == exp else 'XX'} {addr:28} -> {got}")

print("\n=== Filtre anti-pub (True = pub ecartee) ===")
cases = [
    # (sujet, expediteur, corps, attendu_pub?)
    ("Black Friday : -50% sur tout le site !", "promo@boutique.com",
     "Profitez de nos soldes, livraison gratuite, code promo HK50", True),
    ("Vente privee exclusive, derniere chance", "deals@shop.fr",
     "Jusqu'a -40% reduction, achetez maintenant", True),
    ("Inflation zone euro : recul a 2,9% en mai", "newsletter@lesechos.fr",
     "La BCE temporise. Le taux directeur reste a 4%. Analyse complete des chiffres.", False),
    ("Le point marche : Nvidia franchit 4000 Mds$", "redaction@zonebourse.com",
     "Les actions technologiques poursuivent leur hausse. Le Nasdaq gagne 1,2%.", False),
    ("🔥💰 Offre flash 24h seulement 🎁", "marketing@vente.com",
     "Ne ratez pas nos best-sellers, commandez vite", True),
    ("Bitcoin : pourquoi la hausse continue", "matthias@newsletter.io",
     "Decryptage des flux institutionnels et de la demande ETF sur le marche crypto.", False),
]
for subj, snd, body, exp in cases:
    got = E._is_promotional(subj, snd, body)
    flag = "OK" if got == exp else "XX"
    label = "PUB " if got else "GARDE"
    print(f"  {flag} [{label}] {subj[:42]}")
