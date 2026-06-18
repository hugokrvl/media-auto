"""Test du renderer breaking avec une image de test Pexels."""
import urllib.request
import breaking

# Photo test publique (finance / Bloomberg-style)
TEST_PHOTO_URL = "https://images.pexels.com/photos/534216/pexels-photo-534216.jpeg"

req = urllib.request.Request(TEST_PHOTO_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    photo_bytes = r.read()

article = {
    "title_fr": "K. Warsh laisse les taux inchangés pour sa 1ère réunion à la tête de la Fed, malgré la pression de D. Trump",
    "source": "Bloomberg",
    "category": "finance",
    "score": 9,
    "verified": True,
}

img = breaking.make_breaking_image(article, photo_bytes)
with open("test_breaking.png", "wb") as f:
    f.write(img)
print(f"OK -> test_breaking.png ({len(img)//1024} KB)")
