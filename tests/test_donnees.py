"""Contrôles de cohérence des données : chaque série retombe sur les totaux officiels."""
import csv
import json
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RACINE, "data")


def lire(nom):
    with open(os.path.join(DATA, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Totaux officiels (charges, revenus) relevés dans les tableaux récapitulatifs « TOTAUX » des documents,
# indépendamment du détail ligne par ligne. Les comptes 2025 sont arrondis au franc dans ce tableau.
OFFICIELS = {
    "C2018": (61261994.61, 61265241.90), "B2019": (55077400.00, 54629400.00), "C2019": (53154097.57, 53156995.78),
    "B2020": (55106800.00, 54637000.00), "C2020": (55810116.07, 55813157.68), "B2021": (56255500.00, 56046300.00),
    "C2021": (58364908.99, 58224338.56), "B2022": (58047100.00, 58038300.00), "C2022": (58228732.37, 58237668.57),
    "B2023": (62691800.00, 62486100.00), "C2023": (60704570.87, 60753114.41), "B2024": (65704100.00, 65580300.00),
    "C2024": (63443406.22, 62792729.79), "B2025": (55529820.00, 55209564.00), "P2026": (57345370.55, 55345370.55),
    "C2025": (55135163.00, 54643801.00),
}
ARRONDIS = {"C2025"}


class TestRapprochement(unittest.TestCase):
    def test_series_retombent_sur_les_totaux_officiels(self):
        lignes = lire("lignes_large.csv")
        for s, (ch, rv) in OFFICIELS.items():
            if s not in lignes[0]:
                continue
            c = sum(float(l[s]) for l in lignes if l[s] and l["sens"] == "charge")
            r = sum(float(l[s]) for l in lignes if l[s] and l["sens"] == "revenu")
            d = 1.0 if s in ARRONDIS else 0.01
            self.assertAlmostEqual(c, ch, delta=d, msg=f"{s} charges")
            self.assertAlmostEqual(r, rv, delta=d, msg=f"{s} revenus")

    def test_resultats_coherents(self):
        for r in lire("resultats.csv"):
            self.assertAlmostEqual(float(r["revenus"]) - float(r["charges"]), float(r["resultat"]), delta=0.01)

    def test_aucun_controle_bloquant_en_echec(self):
        ko = [c for c in lire("controles.csv") if c["ok"] != "oui" and c["bloquant"] == "oui"]
        self.assertEqual(ko, [], ko[:5])
        self.assertGreater(len(lire("controles.csv")), 1000)

    def test_amendements_expliquent_l_ecart_projet_vote(self):
        res = {r["serie"]: r for r in lire("resultats.csv")}
        am = lire("amendements.csv")
        for an in {a["annee"] for a in am}:
            d = sum(float(a["difference"]) * (1 if a["sens"] == "revenu" else -1) for a in am if a["annee"] == an)
            self.assertAlmostEqual(float(res["P" + an]["resultat"]) + d, float(res["B" + an]["resultat"]), delta=0.01)

    def test_cles_uniques(self):
        cles = [(l["section"], l["compte"]) for l in lire("lignes_large.csv")]
        self.assertEqual(len(cles), len(set(cles)))

    def test_site_a_jour(self):
        d = json.load(open(os.path.join(RACINE, "site", "data.json"), encoding="utf-8"))
        self.assertEqual(len(d["lignes"]), len(lire("lignes_large.csv")))
        html = open(os.path.join(RACINE, "site", "index.html"), encoding="utf-8").read()
        self.assertNotIn("/*DATA*/null", html)


if __name__ == "__main__":
    unittest.main()
