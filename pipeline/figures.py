"""
Figures récurrentes du média (éco / tech / IA / blockchain / quantique).

Sert à deux choses :
1. Mapper une ENTREPRISE → sa figure emblématique (fiable, vs prompt seul) pour l'image.
2. Définir qui mérite une ROTATION de plusieurs portraits (pool Commons), pour ne pas
   toujours montrer la même photo.

Clé = nom normalisé (minuscules, sans accents). Valeur = (nom affiché, organisation).
"""

import unicodedata


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


# (nom complet, organisation principale)
_FIGURES_RAW = [
    # ── IA ────────────────────────────────────────────────────────────────────
    ("Sam Altman", "OpenAI"), ("Greg Brockman", "OpenAI"), ("Mira Murati", "OpenAI"),
    ("Dario Amodei", "Anthropic"), ("Daniela Amodei", "Anthropic"),
    ("Arthur Mensch", "Mistral AI"), ("Demis Hassabis", "Google DeepMind"),
    ("Sundar Pichai", "Google"), ("Jensen Huang", "Nvidia"),
    ("Mark Zuckerberg", "Meta"), ("Yann LeCun", "Meta"),
    ("Satya Nadella", "Microsoft"), ("Mustafa Suleyman", "Microsoft AI"),
    ("Elon Musk", "xAI / Tesla / SpaceX"), ("Andrej Karpathy", "IA"),
    ("Fei-Fei Li", "IA"), ("Aravind Srinivas", "Perplexity"),
    ("Alexandr Wang", "Scale AI"), ("Emad Mostaque", "Stability AI"),
    ("Clement Delangue", "Hugging Face"), ("Liang Wenfeng", "DeepSeek"),
    # ── Tech ──────────────────────────────────────────────────────────────────
    ("Tim Cook", "Apple"), ("Andy Jassy", "Amazon"), ("Jeff Bezos", "Amazon"),
    ("Lisa Su", "AMD"), ("Pat Gelsinger", "Intel"), ("Cristiano Amon", "Qualcomm"),
    ("Michael Dell", "Dell"), ("Bill Gates", "Microsoft"),
    ("Larry Page", "Google"), ("Sergey Brin", "Google"),
    ("Sam Altman", "OpenAI"), ("Marc Benioff", "Salesforce"),
    ("Shou Zi Chew", "TikTok"), ("Evan Spiegel", "Snap"),
    ("Brian Chesky", "Airbnb"), ("Dara Khosrowshahi", "Uber"),
    ("Jack Dorsey", "Block"), ("Reid Hoffman", "LinkedIn"),
    ("Pavel Durov", "Telegram"), ("Daniel Ek", "Spotify"),
    # ── Crypto / Blockchain ────────────────────────────────────────────────────
    ("Michael Saylor", "Strategy"), ("Brian Armstrong", "Coinbase"),
    ("Changpeng Zhao", "Binance"), ("Vitalik Buterin", "Ethereum"),
    ("Cathie Wood", "ARK Invest"), ("Arthur Hayes", "BitMEX"),
    ("Tyler Winklevoss", "Gemini"), ("Cameron Winklevoss", "Gemini"),
    ("Jeremy Allaire", "Circle"), ("Charles Hoskinson", "Cardano"),
    # ── Finance / Marchés ──────────────────────────────────────────────────────
    ("Jerome Powell", "Réserve fédérale"), ("Christine Lagarde", "BCE"),
    ("Jamie Dimon", "JPMorgan"), ("Warren Buffett", "Berkshire Hathaway"),
    ("Larry Fink", "BlackRock"), ("David Solomon", "Goldman Sachs"),
    ("Bernard Arnault", "LVMH"), ("Ray Dalio", "Bridgewater"),
    ("Janet Yellen", "Trésor américain"), ("Bruno Le Maire", "Économie (France)"),
    # ── Politique tech / divers ────────────────────────────────────────────────
    ("Donald Trump", "États-Unis"), ("Emmanuel Macron", "France"),
    ("Eric Schmidt", "ex-Google"), ("Peter Thiel", "Founders Fund"),
    ("Marc Andreessen", "a16z"), ("Masayoshi Son", "SoftBank"),
]

# Map normalisé : nom → (affichage, org). Le 1er gagne en cas de doublon.
FIGURES: dict[str, tuple[str, str]] = {}
for name, org in _FIGURES_RAW:
    FIGURES.setdefault(_norm(name), (name, org))


def is_known(name: str) -> bool:
    return _norm(name) in FIGURES


def org_of(name: str) -> str | None:
    e = FIGURES.get(_norm(name))
    return e[1] if e else None
