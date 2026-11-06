#!/usr/bin/env python3
"""Projet de budget 2027 de la Commune d'Épalinges (plan comptable MCH2).

1. `extraire()` lit le texte du PDF (pdftotext -layout) : tableaux par nature, marge d'autofinancement,
   endettement prévisionnel et emprunts. Résultat : sources/extraits/projet-2027.json.
2. `fusionner(ctrl)` reprend ce fichier et l'extraction par compte (sources/extraits/budget-2027.csv, produite
   par extract.py), contrôle les chiffres et prépare l'onglet « Projet 2027 » du site.

Le budget 2027 est le premier au plan comptable MCH2 : les services, les comptes et les natures changent de numéro,
et la Municipalité reclasse son budget 2026 dans ce plan (colonne « Budget 2026 » du document). Le projet 2027
est donc comparé à ce budget 2026 retraité, pas aux séries du budget 2026 voté en plan MCH1.

Utilisation : python3 pipeline/projet2027.py
"""
import csv
import json
import os
import re
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(RACINE, "sources", "pdf", "budget-2027.pdf")
EXTRAITS = os.path.join(RACINE, "sources", "extraits")
SORTIE = os.path.join(EXTRAITS, "projet-2027.json")
MONTANT = r"-?\d{1,3}(?:'\d{3})*(?:\.\d\d)?"


def nb(s):
    s = s.replace("’", "'")
    return float(re.sub(r"['\s]", "", s))


def texte():
    return subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True, text=True, check=True).stdout.split("\n")


def ligne_apres(lignes, debut, regex, borne=6000):
    for i in range(debut, min(len(lignes), debut + borne)):
        if re.search(regex, lignes[i]):
            return i
    sys.exit(f"projet 2027 : « {regex} » introuvable")


def signes(txt):
    """Montants d'une ligne ; un « - » séparé devant un nombre le rend négatif."""
    out = []
    for m in re.finditer(r"(-\s+)?(\d{1,3}(?:'\d{3})+|\d+)(?![\d'])", txt):
        v = nb(m.group(2))
        out.append(-v if m.group(1) else v)
    return out


AMT = r"(?:\d{1,3}(?:'\d{3})*)?\.\d\d"


def extraire():
    L = texte()
    res = {}
    # --- natures : tableau « charges et revenus par nature » (Budget 2027, Budget 2026)
    i0 = ligne_apres(L, 0, r"^\s+CHARGES\s+57'472'511\.14\s+57'345'370\.55")
    i1 = ligne_apres(L, i0, r"RÉPARTITION DES CHARGES PAR NATURE")
    nat = {}
    for ln in L[i0:i1]:
        m = re.match(r"^\s{4,}(\d{2,3})\s+(\D.*?)\s{2,}(%s)(?:\s+(%s))?\s*$" % (AMT, AMT), ln)
        if m:
            v27 = nb(m.group(3))
            v26 = nb(m.group(4)) if m.group(4) else None
            # un seul montant : colonne à déterminer lors des contrôles (None = absent)
            nat[m.group(1)] = [m.group(2).strip(), v27, v26]
    res["natures"] = nat
    # --- marge d'autofinancement (Budget 2027, 2026, Comptes 2025 à 2022)
    i = ligne_apres(L, 0, r"MARGE D’AUTOFINANCEMENT & PLAFOND")
    marge = {"colonnes": ["Budget 2027", "Budget 2026", "Comptes 2025", "Comptes 2024", "Comptes 2023", "Comptes 2022"]}
    for cle, rx in (("revenus", r"^Total des revenus\s"), ("revenus_epures", r"^Revenus épurés"),
                    ("charges", r"^Total des charges\s"), ("charges_epurees", r"^Charges épurées"),
                    ("marge", r"^Marge d'autofinancement\s")):
        j = ligne_apres(L, i, rx, 40)
        v = signes(L[j])
        if len(v) != 6:
            sys.exit(f"projet 2027 : marge « {cle} » : {len(v)} montants au lieu de 6 : {L[j]}")
        marge[cle] = v
    res["marge"] = marge
    # --- endettement prévisionnel
    i = ligne_apres(L, 0, r"^\s+Endettement brut et net prévisionnel 2026-2027")
    fin = ligne_apres(L, i, r"^Endettement net prévisionnel 2027", 60)
    endet = []
    for ln in L[i:fin + 1]:
        m = re.match(r"^(\S.*?)\s{2,}(\d{1,3}(?:'\d{3})+)\s*$", ln)
        if m:
            endet.append([m.group(1).strip(), nb(m.group(2))])
    res["endettement"] = endet
    # --- emprunts au budget 2027 : une ligne « prêteur  taux  montant », puis « début - échéance »
    i = ligne_apres(L, 0, r"TABLEAU DES EMPRUNTS 2027 À COURT, MOYEN ET LONG TERME")
    fin = ligne_apres(L, i, r"^\s+Total\s+97 458 325\.00", 120)
    emp = []
    for k in range(i, fin):
        m = re.match(r"^(\S.*?)\s{2,}(\d\.\d\d)\s+(\d{1,3}(?: \d{3})*\.\d\d)\s*$", L[k])
        d = re.match(r"^\s*(\d\d\.\d\d\.\d{4})\s*-\s*(\d\d\.\d\d\.\d{4})\s*$", L[k + 1]) if m else None
        if m and d:
            emp.append([m.group(1).strip(), float(m.group(2)), float(m.group(3).replace(" ", "")), d.group(1), d.group(2)])
    res["emprunts"] = emp
    res["emprunts_total"] = float(re.search(r"Total\s+([\d ]+\.\d\d)", L[fin]).group(1).replace(" ", ""))
    # --- plan des investissements : totaux annuels (patrimoine administratif / financier)
    res["texte_municipalite"] = [
        "Le budget 2027 est le premier établi selon le plan comptable MCH2 ; le budget 2026 a été reclassé dans ce plan par la Municipalité.",
        "La comparaison des lignes budgétaires des exercices 2025 et antérieurs (MCH1) et celles des budgets 2027 et 2026 (MCH2) n'est pas toujours pertinente, à cause des reclassements et réaffectations exigés par MCH2 et de la création de plusieurs nouveaux comptes.",
        "Le budget 2026 inclut 6,6 millions de prélèvements sur les fonds de réserve ; MCH2 interdit cette pratique au niveau du budget.",
    ]
    os.makedirs(EXTRAITS, exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(f"projet 2027 : {len(nat)} natures, {len(emp)} emprunts, {len(endet)} lignes d'endettement")
    return res


def f(x):
    return float(x) if x not in ("", None) else 0.0


def fusionner(ctrl):
    """Contrôles et données de l'onglet. `ctrl` : fonction de contrôle de merge.py."""
    doc = "budget-2027"
    rows = list(csv.DictReader(open(os.path.join(EXTRAITS, "budget-2027.csv"), encoding="utf-8")))
    ann = json.load(open(os.path.join(EXTRAITS, "budget-2027.json"), encoding="utf-8"))
    ex = json.load(open(SORTIE, encoding="utf-8"))
    comptes = [r for r in rows if r["type"] == "compte"]
    lib = ("charges 2027", "revenus 2027", "charges 2026", "revenus 2026")
    # 1. totaux du tableau récapitulatif = somme des comptes (charges : classe 3 ; revenus : classe 4)
    tot = {"charges": [0.0, 0.0], "revenus": [0.0, 0.0]}
    for r in comptes:
        for i in range(2):
            tot["charges"][i] += f(r[f"v{2 * i}"])
            tot["revenus"][i] += f(r[f"v{2 * i + 1}"])
    for sens in ("charges", "revenus"):
        for i, an in enumerate(("2027", "2026")):
            ctrl(doc, f"{an} total des {sens} (tableau récapitulatif)", ann["totaux"][sens][i], tot[sens][i])
    # 2. chaque en-tête (service, fonction, groupe, direction) = somme de ses comptes
    cumul = {}
    for r in comptes:
        sct = r["section"]
        for niveau, code in (("section", sct), ("fonction", sct[:3]), ("groupe", sct[:2]), ("direction", sct[0])):
            c = cumul.setdefault((niveau, code), [0.0] * 4)
            for j in range(4):
                c[j] += f(r[f"v{j}"])
    noms = {"direction": {}, "groupe": {}, "fonction": {}, "section": {}}
    for r in rows:
        if r["type"] in noms:
            noms[r["type"]][r["code"]] = r["libelle"].strip()
            got = cumul.get((r["type"], r["code"]), [0.0] * 4)
            for j in range(4):
                ctrl(doc, f"{r['type']} {r['code']} {lib[j]}", f(r[f"v{j}"]), got[j])
    # 3. natures : tableau officiel = somme des comptes de la nature (un seul montant : colonne 2027)
    for code, (nom, v27, v26) in ex["natures"].items():
        for i, v in ((0, v27), (1, v26)):
            s = sum(f(r[f"v{2 * i}"]) + f(r[f"v{2 * i + 1}"]) for r in comptes if r["code"].startswith(code))
            ctrl(doc, f"nature {code} {'2027' if i == 0 else '2026'} (tableau par nature)", v or 0.0, s)
    # 4. endettement : arithmétique du tableau (brut puis net)
    e = ex["endettement"]
    def val(prefixe, n=0):
        return [v for k, v in e if k.startswith(prefixe)][n]
    ctrl(doc, "endettement brut 2026 : base + investissements - marge", val("Total", 0),
         val("Endettement brut au") + val("Investissements au PA", 0) + val("Investissements au PF", 0) + val("(-) Marge", 0), tol=1.0)
    ctrl(doc, "endettement brut prévisionnel 2026 = total + cautionnements", val("Endettement brut prévisionnel 2026"),
         val("Total", 0) + val("Cautionnements", 0), tol=1.0)
    ctrl(doc, "endettement brut prévisionnel 2027", val("Endettement brut prévisionnel 2027"),
         val("Endettement brut prévisionnel 2026") + val("Investissements au PA", 1) + val("Investissements au PF", 1) + val("(-) Marge", 1), tol=1.0)
    ctrl(doc, "endettement net 2026 : base + investissements PA - marge", val("Total", 1),
         val("Endettement net au") + val("Investissements au PA", 2) + val("(-) Marge", 2), tol=1.0)
    ctrl(doc, "endettement net prévisionnel 2026 = total + cautionnements", val("Endettement net prévisionnel 2026"),
         val("Total", 1) + val("Cautionnements", 1), tol=1.0)
    ctrl(doc, "endettement net prévisionnel 2027", val("Endettement net prévisionnel 2027"),
         val("Endettement net prévisionnel 2026") + val("Investissements au PA", 3) + val("(-) Marge", 3), tol=1.0)
    # 5. marge d'autofinancement : revenus épurés - charges épurées ; la marge 2027/2026 sert à l'endettement
    m = ex["marge"]
    for i, c in enumerate(m["colonnes"]):
        ctrl(doc, f"marge d'autofinancement {c} = revenus épurés - charges épurées", m["marge"][i],
             m["revenus_epures"][i] - m["charges_epurees"][i], tol=1.5)
    ctrl(doc, "total des charges 2027 (marge) = tableau récapitulatif", m["charges"][0], tot["charges"][0], tol=1.0)
    ctrl(doc, "total des revenus 2027 (marge) = tableau récapitulatif", m["revenus"][0], tot["revenus"][0], tol=1.0)
    ctrl(doc, "marge 2027 reprise dans l'endettement", -m["marge"][0], val("(-) Marge", 1), tol=1.0)
    ctrl(doc, "marge 2026 reprise dans l'endettement", -m["marge"][1], val("(-) Marge", 0), tol=1.0)
    ctrl(doc, "emprunts 2027 : somme du tableau", ex["emprunts_total"], sum(x[2] for x in ex["emprunts"]), tol=0.01)
    return {
        "titre": "Projet de budget 2027",
        "totaux": tot, "noms": noms,
        "services": [[r["code"], r["libelle"].strip(), *[round(f(r[f"v{j}"]), 2) for j in range(4)]] for r in rows if r["type"] == "section"],
        "comptes": [[r["section"], r["code"], r["libelle"].strip(), *[round(f(r[f"v{j}"]), 2) for j in range(4)]] for r in comptes],
        "natures": {k: [v[0], v[1], v[2] or 0.0] for k, v in ex["natures"].items()},
        "marge": m, "endettement": ex["endettement"], "emprunts": ex["emprunts"],
        "emprunts_total": ex["emprunts_total"], "texte": ex["texte_municipalite"],
    }


if __name__ == "__main__":
    extraire()
