#!/usr/bin/env python3
"""Fusion des extractions en séries pluriannuelles, contrôles et fichiers de données.

Séries :
  C<année>  comptes (réalisé)
  B<année>  budget voté par le Conseil communal (avec ses amendements)
  P<année>  projet de budget présenté par la Municipalité
Chaque document contient trois colonnes (voir sources/documents.json). Le budget voté d'une
année se lit dans le document suivant (budget de l'année d'après ou états financiers).

Entrée : sources/extraits/*.csv|json   Sortie : data/*.csv et site/data.json
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libelles import lisible  # noqa: E402
import numerotation as num  # noqa: E402
from collections import defaultdict

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RACINE, "sources")
DATA = os.path.join(RACINE, "data")
TOL = 0.005
CONFIG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
RECLASSE = CONFIG.get("reclassements_nature", {})


def nature_de(code):
    """Nature à trois chiffres, avec les reclassements de l'annexe 10 (voir config.json)."""
    return RECLASSE.get(code, code[:3])
PREF = {"projet": "P", "budget": "B", "comptes": "C"}
NOM_TYPE = {"P": "Projet de budget", "B": "Budget voté", "C": "Comptes"}


def f(x):
    return float(x) if x not in ("", None) else None


def sans_initiales(lib):
    """Retire les initiales de l'élu·e responsable en fin de libellé (« - MAA », « - RJO/IKU »)."""
    lib = re.sub(r"\s*-\s*[A-Z]{2,3}(?:\s*/\s*[A-Z]{2,3})*\s*$", "", lib.strip())
    lib = re.sub(r"\s*-\s*(?:[A-Z]\s){1,2}[A-Z]\s*$", "", lib)  # libellés abîmés « - I U »
    lib = re.sub(r"\s*\([A-Z]{2,3}(?:\s*/\s*[A-Z]{2,3})*\)\s*$", "", lib)  # « (AGI) »
    return lib.strip(" -")


def titre(s):
    petits = {"de", "des", "du", "et", "la", "le", "les", "à", "a", "aux", "au", "d", "l", "en", "sur", "pour"}
    mots = re.split(r"(\s+|-|')", s.lower())
    out = []
    for i, m in enumerate(mots):
        out.append(m if (m in petits and i > 0) else m[:1].upper() + m[1:])
    return "".join(out)


def charger():
    cfg = json.load(open(os.path.join(SRC, "documents.json"), encoding="utf-8"))
    docs = []
    for d in cfg["documents"]:
        p = os.path.join(SRC, "extraits", d["id"] + ".csv")
        if not os.path.exists(p):
            continue
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        ann = json.load(open(os.path.join(SRC, "extraits", d["id"] + ".json"), encoding="utf-8"))
        docs.append((d, rows, ann))
    return cfg, docs


def priorite(doc, serie):
    """Source préférée d'une série : texte > document scanné ; comptes > budget ; puis le plus récent."""
    return (0 if doc.get("ocr") or doc.get("pages_ocr") else 1, 1 if doc["type"] == "comptes" else 0, doc["annee"])


def preparer(docs):
    """Retire les sous-totaux de l'ancienne numérotation et calcule la nouvelle clé de chaque ligne."""
    par_id = {d["id"]: rows for d, rows, _ in docs}
    for d, rows, _ in docs:
        comptes = [r for r in rows if r["type"] == "compte"]
        if any(num.ancien(r["code"]) for r in comptes):
            garde = {id(r) for r in num.sans_sous_totaux(comptes)}
            rows[:] = [r for r in rows if r["type"] != "compte" or id(r) in garde]
    p = CONFIG.get("passage_numerotation")
    if not p:
        for d, rows, _ in docs:
            for r in rows:
                if r["type"] == "compte":
                    r["cle"] = f"{r['section']}|{r['code']}"
        return {}
    vieux = [r for r in par_id.get(p["ancien"], []) if r["type"] == "compte"]
    neufs = [r for r in par_id.get(p["nouveau"], []) if r["type"] == "compte"]
    res, nv, pris = num.correspondance(vieux, neufs, p["colonnes_ancien"], p["colonnes_nouveau"])
    for d, rows, _ in sorted(docs, key=lambda x: -x[0]["annee"]):
        for r in rows:
            if r["type"] == "compte" and num.ancien(r["code"]):
                r["cle"] = "|".join(num.completer((r["section"], r["code"]), r["libelle"], res, nv, pris)[:2])
            elif r["type"] == "compte":
                r["cle"] = f"{r['section']}|{r['code']}"
    return res


def main():
    cfg, docs = charger()
    passage = preparer(docs)
    os.makedirs(DATA, exist_ok=True)
    controles = []
    connus = {(e["document"], e["controle"]) for e in CONFIG.get("ecarts_connus", [])}

    def ctrl(doc, objet, attendu, obtenu, bloquant=True, tol=TOL):
        if attendu is None:
            return True
        if (doc, objet) in connus:
            bloquant = False
        ok = abs((attendu or 0) - (obtenu or 0)) < tol
        controles.append({"document": doc, "controle": objet, "attendu": f"{attendu:.2f}",
                          "obtenu": f"{obtenu:.2f}", "ecart": f"{(obtenu or 0) - (attendu or 0):.2f}",
                          "ok": "oui" if ok else "non", "bloquant": "oui" if bloquant else "non"})
        return ok

    sources = defaultdict(dict)       # serie -> clé -> (priorité, montant, doc)
    libelles = {}                     # clé -> (rang doc, libellé)
    sections = {}                     # code -> (rang doc, libellé)
    groupes, directions = {}, {}
    natures = {}
    commentaires = []
    series_docs = defaultdict(list)
    for rang, (doc, rows, ann) in enumerate(sorted(docs, key=lambda x: (x[0]["annee"], x[0]["type"] == "comptes"))):
        cols = [(PREF[c.split(":")[0]] + c.split(":")[1]) for c in doc["colonnes"]]
        for s in cols:
            series_docs[s].append(doc["id"])
        for k, v in ann.get("natures", {}).items():
            natures[k] = CONFIG["noms_natures"].get(k) or titre(v)
        for k, v in ann.get("directions", {}).items():
            directions[k] = v if not v.isupper() else lisible(v)
        # Totaux officiels
        for i, s in enumerate(cols):
            for j, sens in enumerate(("charges", "revenus")):
                tot = sum(f(r[f"v{2 * i + j}"]) or 0 for r in rows if r["type"] == "compte")
                ctrl(doc["id"], f"{s} total des {sens} (tableau récapitulatif)", ann["totaux"][sens][i], tot,
                     tol=1.0 if ann.get("arrondi") else TOL)
        # Natures (annexe 10, niveau à trois chiffres)
        for nat, vals in ann.get("natures_montants", {}).items():
            for i, s in enumerate(cols):
                tot = sum((f(r[f"v{2 * i}"]) or 0) + (f(r[f"v{2 * i + 1}"]) or 0)
                          for r in rows if r["type"] == "compte" and nature_de(r["code"]) == nat)
                ctrl(doc["id"], f"{s} nature {nat}", vals[i] if nat[0] == "3" else -vals[i], tot, bloquant=False)
        # Sous-totaux par section, groupe, direction
        nv = 2 * len(cols)
        cumul = defaultdict(lambda: [0.0] * nv)
        entetes = {}
        for r in rows:
            if r["type"] in ("section", "fonction", "groupe", "direction"):
                if r["type"] == "section":
                    lib = sans_initiales(r["libelle"])
                    if lib:
                        sections[r["code"] + ("0" if len(r["code"]) == 3 else "")] = (rang, lib)
                elif r["type"] == "groupe":
                    groupes[r["code"]] = lisible(sans_initiales(r["libelle"]))
                elif r["type"] == "direction" and r["code"] != "0" and r["code"] not in directions:
                    directions[r["code"]] = lisible(sans_initiales(r["libelle"]))
                if r["code"] != "0":
                    entetes[(r["type"], r["code"])] = [f(r[f"v{j}"]) or 0 for j in range(nv)]
                continue
            section = r["section"]
            if not section:
                raise SystemExit(f"{doc['id']} : compte {r['code']} avant toute section")
            vals = [f(r[f"v{j}"]) for j in range(nv)]
            for niveau, code in (("section", section), ("fonction", section[:3]),
                                 ("groupe", section[:2]), ("direction", section[0])):
                for j in range(nv):
                    cumul[(niveau, code)][j] += vals[j] or 0
            cle = r["cle"]
            if cle in libelles and libelles[cle][0] == rang:
                raise SystemExit(f"{doc['id']} : compte en double {cle}")
            libelles[cle] = (rang, r["libelle"])
            if r["commentaire"]:
                commentaires.append({"cle": cle, "document": doc["id"], "annee": doc["annee"],
                                     "type": doc["type"], "texte": r["commentaire"], "source": r["source"]})
            for i, s in enumerate(cols):
                c, rv = vals[2 * i], vals[2 * i + 1]
                if c is None and rv is None:
                    continue
                m = (c or 0) + (rv or 0)
                old = sources[s].get(cle)
                pr = priorite(doc, s)
                if old and abs(old[1] - m) >= TOL:
                    controles.append({"document": doc["id"], "controle": f"{s} {cle} diffère de {old[2]}",
                                      "attendu": f"{old[1]:.2f}", "obtenu": f"{m:.2f}",
                                      "ecart": f"{m - old[1]:.2f}", "ok": "non", "bloquant": "non"})
                if not old or pr >= old[0]:
                    sources[s][cle] = (pr, m, doc["id"])
        for (niveau, code), vals in entetes.items():
            got = cumul.get((niveau, code), [0.0] * nv)
            for i, s in enumerate(cols):
                for j, sens in enumerate(("charges", "revenus")):
                    ctrl(doc["id"], f"{s} {niveau} {code} {sens}", vals[2 * i + j], got[2 * i + j])

    # Séries finales
    series = sorted(sources, key=lambda s: (int(s[1:]), "CBP".index(s[0])))
    cles = sorted({c for s in series for c in sources[s]}, key=lambda c: (c.split("|")[0], c.split("|")[1]))
    val = {s: {c: v[1] for c, v in sources[s].items()} for s in series}

    def sens(cle):
        return "charge" if cle.split("|")[1][0] == "3" else "revenu"

    resultats = []
    for s in series:
        ch = sum(v for c, v in val[s].items() if sens(c) == "charge")
        rv = sum(v for c, v in val[s].items() if sens(c) == "revenu")
        resultats.append({"serie": s, "type": NOM_TYPE[s[0]], "annee": s[1:], "charges": f"{ch:.2f}",
                          "revenus": f"{rv:.2f}", "resultat": f"{rv - ch:.2f}",
                          "documents": " ; ".join(sorted({v[2] for v in sources[s].values()}))})
    # Contrôle contre les budgets amendés scannés
    for dc in cfg.get("documents_de_controle", []):
        for col, att in dc["controles"].items():
            s = PREF[col.split(":")[0]] + col.split(":")[1]
            if s not in val:
                continue
            r = next(x for x in resultats if x["serie"] == s)
            ctrl(dc["id"], f"{s} charges (document scanné)", att["charges"], float(r["charges"]))
            ctrl(dc["id"], f"{s} revenus (document scanné)", att["revenus"], float(r["revenus"]))
            ctrl(dc["id"], f"{s} résultat (document scanné)", -att["resultat"], float(r["resultat"]))

    # Amendements : projet de la Municipalité vs budget voté
    amendements = []
    for s in series:
        if s[0] != "P" or ("B" + s[1:]) not in val:
            continue
        b = "B" + s[1:]
        for c in sorted(set(val[s]) | set(val[b])):
            p, v = val[s].get(c), val[b].get(c)
            if abs((p or 0) - (v or 0)) >= TOL:
                amendements.append({"annee": s[1:], "section": c.split("|")[0], "compte": c.split("|")[1],
                                    "libelle": libelles[c][1], "sens": sens(c),
                                    "projet": f"{p or 0:.2f}", "vote": f"{v or 0:.2f}",
                                    "difference": f"{(v or 0) - (p or 0):.2f}"})

    sec_lib = {k: lisible(v[1]) for k, v in sections.items()}

    def ecrire(nom, lignes, champs):
        with open(os.path.join(DATA, nom), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=champs)
            w.writeheader()
            w.writerows(lignes)

    large = []
    for c in cles:
        sec, cpt = c.split("|")
        row = {"direction": sec[0], "direction_nom": directions.get(sec[0], ""), "groupe": sec[:2],
               "groupe_nom": groupes.get(sec[:2], ""), "section": sec, "section_nom": sec_lib.get(sec, ""),
               "compte": cpt, "nature": nature_de(cpt), "nature_nom": natures.get(nature_de(cpt), ""),
               "sens": sens(c), "libelle": libelles[c][1], "libelle_lisible": lisible(libelles[c][1])}
        for s in series:
            row[s] = "" if c not in val[s] else f"{val[s][c]:.2f}"
        large.append(row)
    base = ["direction", "direction_nom", "groupe", "groupe_nom", "section", "section_nom", "compte",
            "nature", "nature_nom", "sens", "libelle", "libelle_lisible"]
    ecrire("lignes_large.csv", large, base + series)
    longues = [{"section": r["section"], "compte": r["compte"], "libelle": r["libelle"], "sens": r["sens"],
                "serie": s, "type": NOM_TYPE[s[0]], "annee": s[1:], "montant": r[s]}
               for r in large for s in series if r[s] != ""]
    ecrire("lignes.csv", longues, ["section", "compte", "libelle", "sens", "serie", "type", "annee", "montant"])
    ecrire("sections.csv", [{"section": k, "nom": sec_lib[k], "groupe": k[:2], "groupe_nom": groupes.get(k[:2], ""),
                             "direction": k[0], "direction_nom": directions.get(k[0], "")} for k in sorted(sec_lib)],
           ["section", "nom", "groupe", "groupe_nom", "direction", "direction_nom"])
    ecrire("natures.csv", [{"nature": k, "nom": v} for k, v in sorted(natures.items())], ["nature", "nom"])
    ecrire("resultats.csv", resultats, ["serie", "type", "annee", "charges", "revenus", "resultat", "documents"])
    ecrire("amendements.csv", amendements, ["annee", "section", "compte", "libelle", "sens", "projet", "vote", "difference"])
    ecrire("commentaires.csv", [{"section": x["cle"].split("|")[0], "compte": x["cle"].split("|")[1],
                                 "document": x["document"], "texte": x["texte"], "source": x["source"]}
                                for x in commentaires], ["section", "compte", "document", "texte", "source"])
    ecrire("controles.csv", controles, ["document", "controle", "attendu", "obtenu", "ecart", "ok", "bloquant"])

    # Données du site
    idx = {c: i for i, c in enumerate(cles)}
    com = defaultdict(list)
    for x in commentaires:
        com[idx[x["cle"]]].append([x["document"], x["texte"]])
    docs_info = {d["id"]: {"titre": d["titre"], "url": d["url"], "annee": d["annee"], "type": d["type"],
                           "note": d.get("note", ""), "colonnes": d["colonnes"]} for d, _, _ in docs}
    site = {
        "series": [{"id": s, "type": s[0], "annee": int(s[1:]), "nom": f"{NOM_TYPE[s[0]]} {s[1:]}",
                    "docs": series_docs[s]} for s in series],
        "lignes": [[c.split("|")[0], c.split("|")[1], lisible(libelles[c][1]),
                    [None if c not in val[s] else round(val[s][c], 2) for s in series]] for c in cles],
        "sections": sec_lib, "groupes": groupes, "directions": directions, "natures": natures,
        "commentaires": {str(k): v for k, v in com.items()},
        "resultats": resultats, "amendements": amendements, "documents": docs_info,
        "controles": {"total": len(controles), "ok": sum(1 for c in controles if c["ok"] == "oui"),
                      "bloquants_ko": sum(1 for c in controles if c["ok"] == "non" and c["bloquant"] == "oui")},
        "page_source": cfg["page_source"],
    }
    with open(os.path.join(RACINE, "site", "data.json"), "w", encoding="utf-8") as fh:
        json.dump(site, fh, ensure_ascii=False, separators=(",", ":"))
    ko = [c for c in controles if c["ok"] == "non"]
    print(f"{len(cles)} lignes, séries {', '.join(series)}")
    print(f"{len(controles)} contrôles, {len(ko)} écarts ({sum(1 for c in ko if c['bloquant'] == 'oui')} bloquants)")
    for c in ko[:30]:
        print("  ", c)
    for r in resultats:
        print(f"  {r['serie']}: charges {float(r['charges']):>15,.2f} revenus {float(r['revenus']):>15,.2f} "
              f"résultat {float(r['resultat']):>14,.2f}")
    print(f"{len(amendements)} différences projet / budget voté")
    from collections import Counter
    print("Passage de numérotation :", dict(Counter(v[2] for v in passage.values())))


if __name__ == "__main__":
    main()
