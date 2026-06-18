# -*- coding: utf-8 -*-
import dedup

# Historique : un post sur l'inflation a 3.2%
hist_art = {"title_fr": "L'inflation ralentit a 3,2 % en zone euro", "category": "finance",
            "chart_data": [{"label": "Inflation", "value": "3.2"}, {"label": "Taux", "value": "4.0"}],
            "url": "http://a/1"}
dedup.annotate(hist_art)
history = [dict(dedup.as_history_row(hist_art), id="ID1")]


def show(name, art, expected):
    dedup.annotate(art)
    st, _ = dedup.classify(art, history)
    flag = "OK " if st == expected else "XX "
    print(f"{flag}{name:42} -> {st:9} (attendu {expected})")


show("Meme article identique", {
    "title_fr": "L'inflation ralentit a 3,2 % en zone euro", "category": "finance",
    "chart_data": [{"label": "Inflation", "value": "3.2"}, {"label": "Taux", "value": "4.0"}],
    "url": "http://a/1"}, "duplicate")

show("Meme sujet autre source, 3.2%", {
    "title_fr": "Zone euro : inflation stable a 3,2 %", "category": "finance",
    "chart_data": [{"label": "Inflation", "value": "3.2"}], "url": "http://b/9"}, "duplicate")

show("Meme sujet, inflation 2.9% (bouge)", {
    "title_fr": "Zone euro : l'inflation recule a 2,9 %", "category": "finance",
    "chart_data": [{"label": "Inflation", "value": "2.9"}], "url": "http://c/3"}, "update")

show("Meme url, chiffre revise 3.5%", {
    "title_fr": "L'inflation ralentit a 3,2 % en zone euro", "category": "finance",
    "chart_data": [{"label": "Inflation", "value": "3.5"}], "url": "http://a/1"}, "update")

show("Sujet different (Bitcoin)", {
    "title_fr": "Le Bitcoin franchit les 105 000 dollars", "category": "finance",
    "chart_data": [{"label": "BTC", "value": "105000"}], "url": "http://d/4"}, "new")

show("Variation sous tolerance 3.2 -> 3.22", {
    "title_fr": "Zone euro : inflation a 3,22 %", "category": "finance",
    "chart_data": [{"label": "Inflation", "value": "3.22"}], "url": "http://e/5"}, "duplicate")
