# -*- coding: utf-8 -*-
"""Teste la résolution chaîne YouTube -> flux RSS (urllib stdlib, pas de lib externe)."""
import youtube

CHANNELS = [
    "https://www.youtube.com/@NCheron_bourse",
    "https://www.youtube.com/@matthiasbaccino",
    "https://www.youtube.com/c/MatthieuStefani",
    "https://www.youtube.com/@Hasheur",
]

for url in CHANNELS:
    handle = url.rstrip("/").split("/")[-1]
    feed = youtube.resolve_feed(url)
    print(f"{handle:22} -> {feed or 'ÉCHEC (channelId introuvable)'}")
