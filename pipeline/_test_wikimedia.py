import image_fetch, breaking, urllib.request

tests = [
    {"title_fr": "Guerre en Ukraine : l'attaque massive des drones sur Moscou",
     "source": "Le Monde", "category": "general"},
    {"title_fr": "EN DIRECT, canicule : une vague de chaleur sur la France",
     "source": "Le Monde", "category": "general"},
    {"title_fr": "Decathlon va offrir 2 000 € en actions à ses salariés",
     "source": "Les Échos", "category": "finance"},
    {"title_fr": "OpenAI annonce GPT-5 avec des capacités inédites",
     "source": "TechCrunch", "category": "tech"},
]

for art in tests:
    print(f"\n--- {art['title_fr'][:50]} ---")
    url = image_fetch.fetch_photo_url(art)
    if url:
        print(f"URL : {url[:80]}...")
        photo = image_fetch.download_image(url)
        if photo:
            img = breaking.make_breaking_image(art, photo)
            fname = f"test_wiki_{art['category']}_{art['title_fr'][:15].replace(' ','_')}.png"
            with open(fname, "wb") as f: f.write(img)
            print(f"OK -> {fname}")
    else:
        print("Aucune photo")
