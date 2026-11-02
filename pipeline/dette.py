#!/usr/bin/env python3
"""Dette, ratios financiers et échéancier des emprunts.

Lit les tableaux de texte des PDF (comptes 2024 et 2025, budget 2026) et écrit
sources/extraits/dette.json. Le module fournit aussi `fusionner()`, appelé par merge.py,
qui contrôle les données et prépare data/dette.csv, data/emprunts.csv et l'onglet du site.

Utilisation : python3 pipeline/dette.py   (nécessite pdftotext et les PDF dans sources/pdf/)
"""
import json
import os
import re
import subprocess

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(RACINE, "sources", "pdf")
SORTIE = os.path.join(RACINE, "sources", "extraits", "dette.json")

# (clé, libellé, unité, expression du libellé dans le PDF)
INDICATEURS = [
    ("dette_court", "Dettes à court terme (921)", "CHF", r"^Dettes à court terme \(921\)"),
    ("dette_longue", "Emprunts à moyen et long terme (922)", "CHF", r"^Emprunts à moyen et long terme \(922\)"),
    ("dette_brute", "Dette brute (D1)", "CHF", r"^Total de la dette brute \(D1\)"),
    ("engagements_propres", "Engagements envers des propres établissements et fonds (923)", "CHF",
     r"^Engagements envers des propres établissements"),
    ("dette_brute_d2", "Dette brute (D2, selon MCH1)", "CHF", r"^Total de la dette brute \(D2"),
    ("engagements_bruts", "Total des engagements bruts", "CHF", r"^Total des engagements bruts"),
    ("patrimoine_financier", "Patrimoine financier", "CHF", r"^Total du patrimoine financier"),
    ("endettement_net", "Endettement net (statistiques cantonales)", "CHF",
     r"^Endettements nets ou Engagements nets \(EN\)(?: selon Statistiques cantonales)?$"),
    ("endettement_net_mmfc", "Endettement net (MMFC)", "CHF", r"^Endettements nets ou Engagements nets \(EN\) selon MMFC"),
    ("revenus_fiscaux", "Revenus fiscaux (MMFC)", "CHF", r"^Total des Revenus fiscaux"),
    ("taux_net", "Taux d'endettement net (endettement net / revenus fiscaux)", "%",
     r"^Taux d'endettement net \(EN/RF[) ]+selon MMFC"),
    ("taux_brut", "Taux d'endettement brut (dette brute D2 / revenus courants)", "%", r"^Taux d'endettement brut"),
    ("marge_autofinancement", "Marge d'autofinancement", "CHF", r"^Marge d'autofinancement \(MA\)"),
    ("investissements_nets", "Dépenses nettes d'investissement", "CHF", r"^Total Dépenses nettes d'investissement"),
    ("degre_autofinancement", "Degré d'autofinancement", "%", r"^Degré d'autofinancement"),
    ("plafond", "Plafond d'endettement brut (début de législature 2021-2026)", "CHF",
     r"^Plafond d'endettement brut début"),
]
ANNEES_DOC = {"comptes-2024": 2024, "comptes-2025": 2025}
SEG = re.compile(r"^-?\s*\d[\d' ]*(?:\.\d+)?%?$")


def pages(nom):
    """Texte de chaque page du PDF (mise en page conservée)."""
    out = subprocess.run(["pdftotext", "-layout", os.path.join(PDF, nom + ".pdf"), "-"],
                         capture_output=True, text=True, check=True).stdout
    return out.split("\f")


def nombre(seg):
    pct = seg.endswith("%")
    v = float(seg.rstrip("%").replace("'", "").replace(" ", ""))
    return v


def valeurs(ligne, tiret_zero=False):
    """(libellé, [valeurs]) d'une ligne de tableau : colonnes séparées par 2 espaces ou plus."""
    segs = [s.strip() for s in re.split(r"\s{2,}", ligne.strip()) if s.strip()]
    while segs and re.match(r"^\(\d+\)(=\S+)?$", segs[0]):
        segs.pop(0)
    if not segs:
        return "", []
    label, vals, i = re.sub(r"^\(\d+\)(=\S+)?\s+", "", segs[0]), [], 1
    while i < len(segs):
        s = segs[i]
        if s == "-":
            if tiret_zero or i + 1 >= len(segs) or not SEG.match(segs[i + 1]):
                vals.append(0.0)
            else:  # signe moins séparé du nombre
                i += 1
                vals.append(-nombre(segs[i]))
        elif SEG.match(s):
            vals.append(nombre(s))
        else:
            break
        i += 1
    return label, vals


def cherche(pgs, regex, n, tiret_zero=False, apres=None):
    """Première ligne dont le libellé correspond et qui porte au moins n valeurs."""
    for p, txt in enumerate(pgs, 1):
        if apres and p < apres:
            continue
        for ln in txt.split("\n"):
            label, vals = valeurs(ln, tiret_zero)
            if label and re.search(regex, label) and len(vals) >= n:
                return p, vals[:n]
    return None, None


def echeancier(pgs):
    p = next(i for i, t in enumerate(pgs, 1) if "ÉCHÉANCIER DES EMPRUNTS" in t)
    lignes = pgs[p - 1].split("\n")
    ent = next(l for l in lignes if re.search(r"\b2026\b", l) and re.search(r"\b2035\b", l))
    cols = [(int(m.group()), m.end()) for m in re.finditer(r"\b20\d\d\b", ent)]
    emprunts, total = [], None
    for k, ln in enumerate(lignes):
        if ln.strip().startswith("Total dette"):
            nums = [(m.end(), nombre(m.group())) for m in re.finditer(r"\d[\d']*(?:\.\d+)?", ln)]
            tx = nums[0][1]
            reste = nums[1:]
            total = {"taux": tx, "montant": reste[0][1],
                     "annees": {str(a): v for (e, v), (a, _) in zip(reste[1:], cols)}}
            continue
        m = re.match(r"^\s*(\d\d\.\d\d\.\d{4})\s+(.*?)\s{2,}(\d\.\d{4})\s+(\d[\d']*)(.*)$", ln)
        if not m:
            continue
        debut, nom, taux, montant, reste = m.groups()
        if not nom.strip():  # nom coupé sur la ligne d'avant et d'après
            avant = lignes[k - 1].strip()
            apres_ = next((l.strip() for l in lignes[k + 1:] if l.strip()), "")
            nom = f"{avant} {apres_}"
        compte, prete = re.match(r"^(\d{4}\.\d{2}\.\d{3})\s*-?\s*(.*)$", nom.strip()).groups()
        deb = len(ln) - len(reste)
        rep = {}
        for mm in re.finditer(r"\d[\d']*", re.sub(r"Échu \d\d\.\d\d\.\d{4}", lambda z: " " * len(z.group()), reste)):
            fin = deb + mm.end()
            a = min(cols, key=lambda c: abs(c[1] - fin))[0]
            rep[str(a)] = rep.get(str(a), 0) + nombre(mm.group())
        ech = re.search(r"Échu (\d\d\.\d\d\.\d{4})", reste)
        emprunts.append({"debut": debut, "preteur": prete.strip(), "compte": compte, "taux": float(taux),
                         "montant": nombre(montant), "echeance": ech.group(1) if ech else "",
                         "repartition": rep})
    return p, emprunts, total


FLUX_LIGNES = [  # (clé, début du libellé)
    ("marge", "Marge d'autofinancement"), ("depenses_invest", "Charges d'investissements du patrimoine administratif"),
    ("fonctionnement", "Flux généré par le fonctionnement"), ("investissements", "Flux généré par les investissements"),
    ("remboursements", "Remboursement des emprunts"), ("nouveaux", "Nouveaux emprunts"),
    ("financement", "Flux généré par les activités de financement"), ("variation", "Variation nette des disponibilités"),
    ("dispo_debut", "Disponibilités au début de l'exercice"), ("dispo_fin", "Disponibilités en fin d'exercice")]
NB = re.compile(r"([-\u2010\u2011\u2212])?\s*(\d{1,3}(?: \d{3})*\.\d\d|\d[\d']*\.\d\d)")


def nombres_signes(txt):
    out = []
    for m in NB.finditer(txt):
        v = float(m.group(2).replace(" ", "").replace("'", ""))
        out.append(-v if m.group(1) else v)
    return out


def flux():
    """Tableaux de flux de trésorerie : 2024 et 2025 (comptes 2025), 2023 (comptes 2024), 2022 (comptes 2022)."""
    res = {}
    for doc, annees in (("comptes-2024", [2024, 2023]), ("comptes-2025", [2025, 2024])):
        pgs = pages(doc)
        p = next(i for i, t in enumerate(pgs, 1) if "Tableau des flux de trésorerie" in t and "Flux généré par le fonctionnement" in t)
        cur = {a: {"document": doc, "page": p} for a in annees}
        for ln in pgs[p - 1].split("\n"):
            for cle, deb in FLUX_LIGNES:
                if ln.strip().startswith(deb):
                    v = nombres_signes(ln.strip()[len(deb):])
                    if len(v) == 2:
                        for a, x in zip(annees, v):
                            cur[a][cle] = x
        for a, r in cur.items():
            res[str(a)] = r  # le document le plus récent remplace le précédent
    pgs = pages("comptes-2022")
    p = next(i for i, t in enumerate(pgs, 1) if "TABLEAU DE FLUX DE TRÉSORERIE" in t)
    r = {"document": "comptes-2022", "page": p}
    cles = {"Autofinancement": "marge", "Flux de trésorerie lié à l'activité": "fonctionnement",
            "Flux de trésorerie lié aux opérations d'investissements": "investissements",
            "Flux de trésorerie lié aux financements à moyen et long termes": "financement",
            "Disponibilités au 1": "dispo_debut", "Disponibilités au 31": "dispo_fin"}
    for ln in pgs[p - 1].split("\n"):
        for deb, cle in cles.items():
            if ln.strip().startswith(deb):
                v = nombres_signes(re.sub(r"^.*?(\s{2,}[AB C]?\s{2,}|\s{3,})", " ", ln.strip(), count=1))
                if v:
                    r[cle] = v[-1]
        if ln.strip().startswith("Total (A + B + C)"):
            r["variation"] = nombres_signes(ln)[-1]
    res["2022"] = r
    return res


def extraire():
    res = {"indicateurs": {}, "emprunts_reels": {}, "interets": {}, "echeancier": None, "flux": flux()}
    for doc, an in ANNEES_DOC.items():
        pgs = pages(doc)
        for cle, nom, unite, rx in INDICATEURS:
            p, v = cherche(pgs, rx, 5)
            if v is None:
                continue
            for i, x in enumerate(v):
                res["indicateurs"].setdefault(cle, []).append(
                    {"document": doc, "page": p, "annee": an - i, "valeur": x})
    # Emprunts réels et intérêts passifs 2018-2026 (budget 2026)
    pgs = pages("budget-2026")
    cols = ["B2026", "B2025", "C2024", "C2023", "C2022", "C2021", "C2020", "C2019", "C2018"]
    for cle, rx in (("court", r"^Emprunts à court terme"), ("long", r"^Emprunts à moyen et long terme"),
                    ("total", r"^Total des emprunts réels")):
        p, v = cherche(pgs, rx, 9, tiret_zero=True)
        res["emprunts_reels"][cle] = {"document": "budget-2026", "page": p, "valeurs": dict(zip(cols, v))}
    p, v = cherche(pgs, r"^Intérêts passifs$", 9, tiret_zero=True)
    res["interets"]["budget-2026"] = {"document": "budget-2026", "page": p, "valeurs": dict(zip(cols, v))}
    # Intérêts passifs, détail 2021-2025 (comptes 2025)
    pgs25 = pages("comptes-2025")
    p, v = cherche(pgs25, r"^Intérêts passifs$", 6)
    res["interets"]["comptes-2025"] = {"document": "comptes-2025", "page": p,
                                       "valeurs": dict(zip(["C2025", "B2025", "C2024", "C2023", "C2022", "C2021"], v))}
    p, emp, tot = echeancier(pgs25)
    res["echeancier"] = {"document": "comptes-2025", "page": p, "date": "2025-12-31", "emprunts": emp, "total": tot}
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(f"dette : {sum(len(v) for v in res['indicateurs'].values())} valeurs, {len(emp)} emprunts -> {SORTIE}")


def fusionner(ctrl, docs_info):
    """Contrôle les données et renvoie (lignes dette.csv, lignes emprunts.csv, bloc du site)."""
    d = json.load(open(SORTIE, encoding="utf-8"))
    nomi = {k: (n, u) for k, n, u, _ in INDICATEURS}
    # Valeur retenue par (indicateur, année) : document le plus récent ; les écarts sont notés.
    val, src, revisions = {}, {}, []
    for cle, lst in d["indicateurs"].items():
        for x in sorted(lst, key=lambda z: z["document"]):
            k = (cle, x["annee"])
            if k in val and abs(val[k] - x["valeur"]) > (0.06 if nomi[cle][1] == "%" else 1.0):
                revisions.append({"indicateur": cle, "annee": x["annee"], "ancien": val[k], "nouveau": x["valeur"],
                                  "ancien_document": src[k][0], "document": x["document"]})
            val[k], src[k] = x["valeur"], (x["document"], x["page"])
    # Emprunts réels et intérêts (budget 2026 ; comptes 2025 pour 2025)
    er = d["emprunts_reels"]
    for s, an in zip(["B2026", "B2025", "C2024", "C2023", "C2022", "C2021", "C2020", "C2019", "C2018"],
                     [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]):
        ctrl("budget-2026", f"{s} emprunts : court + long = total", er["total"]["valeurs"][s],
             er["court"]["valeurs"][s] + er["long"]["valeurs"][s])
    rows = []

    def ajoute(ind, serie, valeur, doc, page):
        nom, unite = nomi.get(ind, (None, "CHF"))
        rows.append({"indicateur": ind, "serie": serie, "type": {"C": "Comptes", "B": "Budget voté"}[serie[0]],
                     "annee": serie[1:], "valeur": f"{valeur:.2f}" if unite == "CHF" else f"{valeur:.1f}",
                     "unite": unite, "document": doc, "page": page})

    for cle, lst in d["indicateurs"].items():
        for (c, an), v in sorted(val.items()):
            if c == cle:
                ajoute(c, f"C{an}", v, *src[(c, an)])
    # Contrôles arithmétiques par année de comptes
    for an in range(2020, 2026):
        g = lambda c: val.get((c, an))
        doc = src.get(("dette_brute", an), ("comptes", 0))[0]
        if g("dette_brute") is not None and g("dette_court") is not None:
            ctrl(doc, f"C{an} dette brute = court terme + moyen/long terme", g("dette_brute"),
                 g("dette_court") + g("dette_longue"))
            ctrl(doc, f"C{an} dette brute D2 = D1 + engagements propres", g("dette_brute_d2"),
                 g("dette_brute") + g("engagements_propres"), tol=0.01)
        if g("endettement_net") is not None:
            ctrl(src[("endettement_net", an)][0], f"C{an} endettement net = engagements bruts - patrimoine financier",
                 g("endettement_net"), g("engagements_bruts") - g("patrimoine_financier"), tol=0.01)
        if g("taux_net") is not None and g("endettement_net_mmfc") is not None:
            ctrl(src[("taux_net", an)][0], f"C{an} taux d'endettement net (arrondi 0,1 %)", g("taux_net"),
                 round(g("endettement_net_mmfc") / g("revenus_fiscaux") * 100, 1), tol=0.051)
        if g("taux_net") is not None and g("endettement_net_mmfc") is None and g("endettement_net") is not None \
                and g("revenus_fiscaux") is not None:
            ctrl(src[("taux_net", an)][0], f"C{an} taux d'endettement net (arrondi 0,1 %)", g("taux_net"),
                 round(g("endettement_net") / g("revenus_fiscaux") * 100, 1), tol=0.15, bloquant=False)
        if g("degre_autofinancement") is not None and g("marge_autofinancement") is not None \
                and g("investissements_nets"):
            ctrl(src[("degre_autofinancement", an)][0], f"C{an} degré d'autofinancement = marge / investissements nets",
                 g("degre_autofinancement"), round(g("marge_autofinancement") / g("investissements_nets") * 100, 1),
                 tol=0.051)
    # Emprunts réels du budget 2026 et comptes 2025 : séries propres
    for s in ["B2026", "B2025", "C2024", "C2023", "C2022", "C2021", "C2020", "C2019", "C2018"]:
        for cle, ind in (("court", "emprunts_court"), ("long", "emprunts_long"), ("total", "emprunts_total")):
            ajoute(ind, s, er[cle]["valeurs"][s], "budget-2026", er[cle]["page"])
        # Les comptes 2021-2024 se retrouvent dans les comptes 2025 : concordance
        if s[0] == "C" and int(s[1:]) >= 2021:
            ctrl("budget-2026", f"{s} emprunts réels = dette brute des comptes 2025", val[("dette_brute", int(s[1:]))],
                 er["total"]["valeurs"][s], bloquant=False)
    for cle, ind in (("dette_court", "emprunts_court"), ("dette_longue", "emprunts_long"), ("dette_brute", "emprunts_total")):
        ajoute(ind, "C2025", val[(cle, 2025)], *src[(cle, 2025)])
    it_b, it_c = d["interets"]["budget-2026"], d["interets"]["comptes-2025"]
    for s, v in it_b["valeurs"].items():
        if s != "C2025":
            ajoute("interets_passifs", s, v, it_b["document"], it_b["page"])
    ajoute("interets_passifs", "C2025", it_c["valeurs"]["C2025"], it_c["document"], it_c["page"])
    for s in ("C2024", "C2023", "C2022", "C2021"):
        ctrl("comptes-2025", f"{s} intérêts passifs (comptes 2025 = budget 2026)", it_b["valeurs"][s],
             it_c["valeurs"][s], bloquant=False, tol=1.0)
    # Tableaux de flux de trésorerie : cohérence interne et avec la dette brute
    fl = d["flux"]
    for a in sorted(fl):
        r, y = fl[a], int(a)
        ctrl(r["document"], f"Flux {a} : A + B + C = variation des disponibilités", r["variation"],
             r["fonctionnement"] + r["investissements"] + r["financement"], tol=0.01)
        ctrl(r["document"], f"Flux {a} : disponibilités fin - début = variation", r["variation"],
             r["dispo_fin"] - r["dispo_debut"], tol=0.01)
        if "nouveaux" in r:
            ctrl(r["document"], f"Flux {a} : nouveaux emprunts + remboursements = flux de financement",
                 r["financement"], r["nouveaux"] + r["remboursements"], tol=0.01)
        if (("dette_brute", y) in val) and (("dette_brute", y - 1) in val):
            ctrl(r["document"], f"Flux {a} : flux de financement = variation de la dette brute", r["financement"],
                 val[("dette_brute", y)] - val[("dette_brute", y - 1)], tol=1.0)
        if str(y - 1) in fl:
            ctrl(r["document"], f"Flux {a} : disponibilités au début = fin de l'année précédente", r["dispo_debut"],
                 fl[str(y - 1)]["dispo_fin"], tol=0.01)
        for cle in r:
            if cle not in ("document", "page"):
                rows.append({"indicateur": "flux_" + cle, "serie": f"C{a}", "type": "Comptes", "annee": a,
                             "valeur": f"{r[cle]:.2f}", "unite": "CHF", "document": r["document"], "page": r["page"]})
    # Échéancier au 31.12.2025
    e = d["echeancier"]
    emp, tot = e["emprunts"], e["total"]
    ctrl(e["document"], "Échéancier : somme des emprunts = dette brute D1 au 31.12.2025", val[("dette_brute", 2025)],
         sum(x["montant"] for x in emp))
    ctrl(e["document"], "Échéancier : total du tableau = somme des emprunts", tot["montant"], sum(x["montant"] for x in emp))
    for x in emp:
        ctrl(e["document"], f"Échéancier {x['debut']} {x['preteur']} : remboursements = montant", x["montant"],
             sum(x["repartition"].values()))
    for a, v in tot["annees"].items():
        ctrl(e["document"], f"Échéancier : total {a}", v, sum(x["repartition"].get(a, 0) for x in emp))
    lignes_emp = [{"debut": x["debut"], "preteur": x["preteur"], "compte": x["compte"], "taux": f"{x['taux']:.4f}",
                   "montant_31_12_2025": f"{x['montant']:.0f}", "echeance": x["echeance"],
                   "remboursements": ";".join(f"{a}:{v:.0f}" for a, v in sorted(x["repartition"].items()))}
                  for x in emp]
    site = {
        "indicateurs": [{"cle": k, "nom": n, "unite": u,
                         "valeurs": {str(a): v for (c, a), v in sorted(val.items()) if c == k},
                         "sources": {str(a): list(src[(c, a)]) for (c, a) in sorted(val) if c == k}}
                        for k, n, u, _ in INDICATEURS if any(c == k for c, _ in val)],
        "emprunts_reels": {s: {k: er[k]["valeurs"][s] for k in ("court", "long", "total")} for s in er["total"]["valeurs"]},
        "interets": {s: v for s, v in it_b["valeurs"].items() if s != "C2025"} | {"C2025": it_c["valeurs"]["C2025"]},
        "emprunts": [{"debut": x["debut"], "preteur": x["preteur"], "taux": x["taux"], "montant": x["montant"],
                      "echeance": x["echeance"], "remboursements": x["repartition"]} for x in emp],
        "echeancier_total": tot["annees"], "taux_moyen": tot["taux"], "date_echeancier": "31.12.2025",
        "revisions": revisions,
        "flux": {a: {k: v for k, v in r.items()} for a, r in sorted(fl.items())},
        "sources": {"echeancier": [e["document"], e["page"]], "emprunts_reels": ["budget-2026", er["total"]["page"]]},
    }
    return rows, lignes_emp, site


if __name__ == "__main__":
    extraire()
