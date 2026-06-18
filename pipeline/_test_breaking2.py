import urllib.request
import breaking

TEST_PHOTO_URL = "https://images.pexels.com/photos/3184292/pexels-photo-3184292.jpeg"
req = urllib.request.Request(TEST_PHOTO_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    photo_bytes = r.read()

tests = [
    {"title_fr": "Decathlon va offrir 2 000 € en actions gratuites à ses salariés",
     "source": "Les Échos", "category": "finance"},
    {"title_fr": "90 000 patients : le plus gros contrat de l'histoire d'Air Liquide",
     "source": "Bloomberg", "category": "finance"},
    {"title_fr": "L'IA a déjà conquis 6 Français sur 10",
     "source": "Ipsos", "category": "tech"},
]

for i, art in enumerate(tests):
    img = breaking.make_breaking_image(art, photo_bytes)
    fname = f"test_breaking_style{i+1}.png"
    with open(fname, "wb") as f:
        f.write(img)
    print(f"OK -> {fname}")
