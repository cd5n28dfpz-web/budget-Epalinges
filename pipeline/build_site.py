#!/usr/bin/env python3
"""Assemble le tableau de bord : site/template.html + site/data.json -> site/index.html.

La page est autonome (données incluses) : elle fonctionne hors ligne et sur GitHub Pages.
Seule la bibliothèque d3 est chargée depuis un CDN.
Mesure d'audience facultative : indiquer l'adresse GoatCounter dans pipeline/config.json (« goatcounter »).
"""
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(RACINE, "site", "template.html"), encoding="utf-8").read()
data = open(os.path.join(RACINE, "site", "data.json"), encoding="utf-8").read()
cfg = json.load(open(os.path.join(RACINE, "pipeline", "config.json"), encoding="utf-8"))
assert "/*DATA*/null" in html, "Le gabarit doit contenir le marqueur /*DATA*/null"
gc = cfg.get("goatcounter")
mesure = (f'<script data-goatcounter="{gc}" async src="https://gc.zgo.at/count.js"></script>\n' if gc else "")
page = ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Budgets et comptes de la Commune d&#39;Épalinges, ligne par ligne, en données ouvertes.">\n'
        '<style>body{margin:0;font-size:14px}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        + mesure + '</head>\n<body>\n' + html.replace("/*DATA*/null", data) + "\n</body>\n</html>\n")
open(os.path.join(RACINE, "site", "index.html"), "w", encoding="utf-8").write(page)
print("site/index.html généré")
