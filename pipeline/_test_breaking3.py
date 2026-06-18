import urllib.request, os
import breaking, image_fetch

TEST_PHOTO = "https://images.pexels.com/photos/534216/pexels-photo-534216.jpeg"
req = urllib.request.Request(TEST_PHOTO, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    photo_bytes = r.read()

tests = [
    ({"title_fr": "Guerre en Ukraine : l'attaque massive des drones sur Moscou met à mal les promesses de victoire de Vladimir Poutine",
      "source": "Le Monde", "category": "general"}, "test_ukraine.png"),
    ({"title_fr": "EN DIRECT, canicule : une vague de chaleur étendue, durable et intense sur la France",
      "source": "Le Monde", "category": "general"}, "test_canicule.png"),
    ({"title_fr": "Decathlon va offrir 2 000 € en actions gratuites à ses 105 000 salariés dans le monde",
      "source": "Les Échos", "category": "finance"}, "test_decathlon_long.png"),
]

print("=== KEYWORDS ===")
for art, fname in tests:
    kw = image_fetch._keywords(art)
    print(f"{fname}: {kw!r}")

print("\n=== RENDU ===")
for art, fname in tests:
    img = breaking.make_breaking_image(art, photo_bytes)
    with open(fname, "wb") as f: f.write(img)
    print(f"OK -> {fname}")
