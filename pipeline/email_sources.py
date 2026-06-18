"""
Lecture des newsletters reçues sur une boîte mail dédiée, via IMAP (stdlib).

Principe : tu crées une adresse Gmail dédiée, tu y abonnes toutes tes newsletters,
et le pipeline lit les mails des dernières 24h chaque nuit. Chaque newsletter
devient un "article" passé à l'analyzer comme n'importe quelle source RSS.

Configuration (secrets / .env) :
  NEWSLETTER_EMAIL     adresse de la boîte dédiée (ex: assistant_hk@outlook.fr)
  NEWSLETTER_PASSWORD  MOT DE PASSE D'APPLICATION (PAS le mot de passe du compte)
                       — nécessite la validation en 2 étapes activée.
  NEWSLETTER_IMAP      hôte IMAP (optionnel : déduit du domaine de l'adresse)

L'hôte IMAP est déduit automatiquement du domaine (gmail/outlook/yahoo/icloud) ;
NEWSLETTER_IMAP ne sert qu'à forcer un autre serveur. Si EMAIL/PASSWORD manquent,
le module se désactive proprement (retourne []). Stdlib uniquement (imaplib/email).

Deux filtres protègent le pipeline :
  • SÉCURITÉ boîte perso : seuls les emails portant un en-tête List-Unsubscribe /
    List-Id (= vraies newsletters) sont traités ; les mails personnels (1-to-1)
    sont ignorés. On peut donc utiliser une boîte Gmail existante sans risque.
  • ANTI-PUB : un filtre heuristique écarte les emails clairement promotionnels
    avant l'analyse (l'IA Groq fait le tri sémantique final ensuite).

→ Mot de passe d'application :
  • Outlook : account.microsoft.com/security → Options de sécurité avancées →
    Vérification en 2 étapes (activer) → "Mots de passe d'application" → générer.
  • Gmail : myaccount.google.com → Sécurité → Mots de passe des applications.
"""

import os
import re
import imaplib
import email
import html as html_mod
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone


# Serveurs IMAP par domaine (déduits de l'adresse, surchargeable par NEWSLETTER_IMAP)
_IMAP_HOSTS = {
    "gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com",
    "outlook.fr": "outlook.office365.com", "outlook.com": "outlook.office365.com",
    "hotmail.fr": "outlook.office365.com", "hotmail.com": "outlook.office365.com",
    "live.fr": "outlook.office365.com", "live.com": "outlook.office365.com",
    "msn.com": "outlook.office365.com",
    "yahoo.fr": "imap.mail.yahoo.com", "yahoo.com": "imap.mail.yahoo.com",
    "icloud.com": "imap.mail.me.com", "me.com": "imap.mail.me.com",
    "zoho.eu": "imap.zoho.eu", "zoho.com": "imap.zoho.com",
}


def _imap_host(addr: str) -> str:
    """Serveur IMAP : NEWSLETTER_IMAP si défini, sinon déduit du domaine."""
    forced = os.environ.get("NEWSLETTER_IMAP")
    if forced:
        return forced
    domain = (addr or "").split("@")[-1].lower()
    return _IMAP_HOSTS.get(domain, "imap.gmail.com")


# ── Filtre anti-pub : signaux commerciaux vs. vraie actu ──────────────────────
# Signaux FORTS (poids 2) : quasi exclusivement présents dans des pubs.
_PROMO_STRONG = [
    "code promo", "vente privée", "ventes privées", "black friday", "cyber monday",
    "livraison gratuite", "livraison offerte", "soldes", "déstockage", "cashback",
    "-50%", "-40%", "-30%", "-20%", "% de réduction", "% off", "prix barré",
    "offre flash", "vente flash", "bon d'achat", "code de réduction",
]
# Signaux FAIBLES (poids 1) : fréquents en pub mais possibles ailleurs.
_PROMO_WEAK = [
    "promo", "réduction", "remise", "exclusif", "gratuit", "offre", "achetez",
    "acheter", "commandez", "boutique", "dernière chance", "dernières heures",
    "ne ratez pas", "profitez", "à saisir", "deal", "essai gratuit", "abonnez-vous",
    "shop", "best-seller", "nouveauté", "réservez", "jusqu'à -",
]
_PROMO_SENDER = ("noreply", "no-reply", "marketing", "promo", "deals", "offres",
                 "shop", "boutique", "newsletter@", "info@")


# ── Filtre "bruit" : notifications, réseaux sociaux, paris, transactionnel ─────
# Expéditeurs qui ne sont JAMAIS de l'actu éditoriale (haute précision).
_NOISE_SENDERS = (
    # Réseaux sociaux / plateformes (notifications)
    "linkedin", "github", "gitlab", "twitter", "facebookmail", "facebook",
    "instagram", "youtube", "tiktok", "reddit", "discord", "slack", "meetup",
    "trustpilot", "quora", "pinterest", "twitch",
    # Paris sportifs / casinos
    "betclic", "winamax", "unibet", "pmu", "parionssport", "betway", "bwin",
    "pokerstars", "zebet", "vbet", "feelingbet", "netbet", "genybet",
    # Streaming / divertissement
    "molotov", "netflix", "disney", "spotify", "deezer", "primevideo", "canalplus",
    # Pétitions / mobilisation (jamais de l'actu chiffrée)
    "mypetition", "change.org", "avaaz", "mesopinions", "petitions",
    # Système / robots
    "mailer-daemon", "postmaster", "notifications@", "noreply@github",
)
# Sujets de pure notification / transactionnel (sûrs, peu de faux positifs).
_NOISE_SUBJECT = (
    "run failed", "build failed", "workflow run", "déploiement", "deployment",
    "nouveau message", "new message", "vous avez 1", "vous avez un nouveau",
    "you have a new", "postes à pourvoir", "postes de", "offres d'emploi",
    "jobs for you", "ça commence dans", "commence dans", "démarre dans",
    "starts in", "réinitialis", "reset your password", "votre mot de passe",
    "code de vérification", "verification code", "confirmez votre",
    "confirm your", "votre commande", "your order", "facture", "invoice",
    "reçu de", "receipt", "a été expédié", "has shipped", "joyeux anniversaire",
)


def _is_noise(subject: str, sender: str) -> bool:
    """Vrai si l'email est une notification/réseau social/pari/transactionnel —
    jamais de l'actu. Filtre haute précision (sender + sujet) pour épargner Groq."""
    s = (subject or "").lower()
    snd = (sender or "").lower()
    if any(tok in snd for tok in _NOISE_SENDERS):
        return True
    if any(pat in s for pat in _NOISE_SUBJECT):
        return True
    return False


def _is_promotional(subject: str, sender: str, body: str) -> bool:
    """Vrai si l'email ressemble à une pub (heuristique conservatrice).
    L'IA reste le filtre sémantique final ; ici on évite juste de gaspiller du quota."""
    s = (subject or "").lower()
    head = (body or "")[:600].lower()
    snd = (sender or "").lower()
    score = 0
    for kw in _PROMO_STRONG:
        if kw in s or kw in head:
            score += 2
    for kw in _PROMO_WEAK:
        if kw in s:
            score += 1
    # Remise chiffrée explicite (-25 %, -25%, − 25 %) = signal fort
    if re.search(r"[-−]\s?\d{1,2}\s?%", s + " " + head):
        score += 2
    if any(p in snd for p in _PROMO_SENDER):
        score += 1
    # Sujet bourré d'emojis commerciaux
    if len(re.findall(r"[🔥💰🎁🛒✨⚡💥🤑👉]", s)) >= 2:
        score += 1
    return score >= 3


def _decode(value: str) -> str:
    """Décode un en-tête MIME (sujet/expéditeur encodés)."""
    if not value:
        return ""
    out = []
    for part, enc in decode_header(value):
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(part)
    return "".join(out).strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _body_text(msg) -> str:
    """Extrait le texte d'un mail (préfère text/plain, sinon convertit le HTML)."""
    plain, htmltxt = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="ignore")
            except Exception:
                continue
            if ctype == "text/plain" and not plain:
                plain = content
            elif ctype == "text/html" and not htmltxt:
                htmltxt = content
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="ignore") if payload else ""
        except Exception:
            content = ""
        if msg.get_content_type() == "text/html":
            htmltxt = content
        else:
            plain = content
    text = plain.strip() or _html_to_text(htmltxt)
    return re.sub(r"\s+\n", "\n", text).strip()


def fetch_newsletters(hours_back: int = 24, category: str = "general") -> list[dict]:
    """Retourne les newsletters reçues dans les dernières `hours_back` heures."""
    addr = os.environ.get("NEWSLETTER_EMAIL")
    pwd = os.environ.get("NEWSLETTER_PASSWORD")
    if not addr or not pwd:
        print("[EMAIL] NEWSLETTER_EMAIL/PASSWORD absents — lecture newsletters désactivée")
        return []
    host = _imap_host(addr)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []
    skipped_promo = 0
    skipped_personal = 0
    skipped_noise = 0
    skipped_dup = 0
    seen = set()  # (expéditeur, sujet) déjà vus -> évite les doublons exacts
    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(addr, pwd)
        M.select("INBOX")
        # SINCE travaille à la journée -> on prend 2 jours puis on filtre finement
        since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%d-%b-%Y")
        typ, data = M.search(None, f'(SINCE {since})')
        ids = data[0].split() if data and data[0] else []
        for num in ids:
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            # SÉCURITÉ boîte perso : on ne traite QUE les vraies newsletters.
            # Toute newsletter porte un en-tête List-Unsubscribe (lien de
            # désabonnement) ; un email personnel (1-to-1) n'en a pas -> ignoré.
            if not (msg.get("List-Unsubscribe") or msg.get("List-Id")):
                skipped_personal += 1
                continue
            try:
                pub = parsedate_to_datetime(msg.get("Date"))
                if pub and pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
            except Exception:
                pub = None
            if pub and pub < cutoff:
                continue
            subject = _decode(msg.get("Subject", ""))
            sender = _decode(msg.get("From", ""))
            name = re.sub(r"\s*<.*?>", "", sender).strip().strip('"') or sender
            # Filtre bruit : notifications réseaux sociaux / paris / transactionnel
            if _is_noise(subject, sender):
                skipped_noise += 1
                continue
            # Doublon exact (même expéditeur + même sujet) -> une seule analyse
            key = (name.lower(), subject.lower().strip())
            if key in seen:
                skipped_dup += 1
                continue
            seen.add(key)
            body = _body_text(msg)
            if not subject or len(body) < 80:
                continue
            # Filtre anti-pub : on écarte les emails clairement promotionnels
            if _is_promotional(subject, sender, body):
                skipped_promo += 1
                continue
            # Premier lien http du corps -> url de référence
            link = ""
            m = re.search(r"https?://[^\s\"'>)]+", body)
            if m:
                link = m.group(0)
            articles.append({
                "title": subject,
                "url": link,
                "summary": body[:800],
                "published": pub.isoformat() if pub else None,
                "source": f"Newsletter · {name}"[:60],
                "category": category,
            })
        M.logout()
    except Exception as e:
        print(f"[EMAIL] Erreur IMAP: {type(e).__name__}: {e}")
        return articles
    print(f"[EMAIL] {len(articles)} gardée(s) · {skipped_noise} notif/réseau · "
          f"{skipped_promo} pub · {skipped_dup} doublon(s) · {skipped_personal} perso")
    return articles
