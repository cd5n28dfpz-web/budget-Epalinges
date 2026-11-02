#!/usr/bin/env python3
"""Extraction des budgets et des comptes de la Commune d'Épalinges.

Pour chaque document de sources/documents.json :
  - lit la position de chaque mot avec `pdftotext -bbox` (poppler-utils) ;
  - repère les pages du « détail par service » : un tableau de 3 ou 6 colonnes d'années
    (Charges / Revenus pour chacune), avec les niveaux direction (1 chiffre), groupe (2),
    fonction (3), service (4) et compte (3011.000, ou 1100 3011.000 selon les années) ;
  - pour les pages enregistrées sans texte (dessin), utilise la reconnaissance de caractères
    (tesseract) ; le résultat est conservé dans sources/ocr/ pour ne pas dépendre de tesseract
    lors des reconstructions suivantes.

Résultat : sources/extraits/<document>.csv et sources/extraits/<document>.json
Usage : python3 pipeline/extract.py [id_document ...]
"""
import csv
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RACINE, "sources")
MONTANT = re.compile(r"^-?(?:\d{1,3}(?:['’]\d{3})+|\d{1,7})[.,]\d\d$")
CODE = re.compile(r"^\d{4}\.\d{3}$")
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)
PIED = re.compile(r"^(?:-\s*\d{1,3}\s*-|\d{1,3}|Page \d+.*)$")
CHAMPS = ["document", "page", "source", "type", "section", "code", "libelle", "commentaire"]


def montant(t):
    return round(float(t.replace("'", "").replace("’", "").replace(",", ".")), 2)


def mots_pdf(chemin):
    """Liste des pages : (largeur, hauteur, [mots]) avec mot = dict x0, top, x1, bottom, text."""
    out = subprocess.run(["pdftotext", "-bbox", chemin, "-"], capture_output=True, text=True, check=True).stdout
    pages = []
    for w, h, corps in PAGE.findall(out):
        mots = [{"x0": float(a), "top": float(b), "x1": float(c), "bottom": float(d),
                 "text": re.sub(r"^[\u2010-\u2015\u2212](?=\d)", "-", html.unescape(t))}  # tirets typographiques
                for a, b, c, d, t in WORD.findall(corps)]
        pages.append((float(w), float(h), mots))
    return pages


def corrige_ocr(t):
    """Nettoie les artefacts de lecture (bordures du tableau lues comme des caractères)."""
    t = t.replace("’", "'").replace("‘", "'").replace("`", "'").replace("´", "'").replace("''", "'")
    t = re.sub(r"(?<=\d)[°*](?=\d{3})", "'", t)
    if re.fullmatch(r"[§$]\d[\d'.,]*", t):  # « §4'748.31 » pour « 54'748.31 »
        t = "5" + t[1:]
    m = re.match(r"^(-?\d{1,3}(?:'\d{3})*[.,]\d\d)[^\d]{1,2}$", t.lstrip("|[]{}()!_—"))
    if m:  # montant suivi d'un bout de bordure (« 1'000.00; », « 15.00) »)
        return m.group(1)
    core = t.strip("|[]{}()!_—-").strip()
    if re.fullmatch(r"-?[\dOoIl'.,:/_]+", core) and re.search(r"\d", core):
        neg = t.lstrip("|[]{}()!_—").startswith("-")
        core = core.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")
        core = re.sub(r"(\d)[:/_](\d\d)$", r"\1.\2", core)
        return ("-" if neg and not core.startswith("-") else "") + core
    return t


def effacer_traits(chemin_png):
    """Efface les traits longs (bordures du tableau) avant la lecture : un trait épais collé à la dernière
    décimale d'un montant la fait lire de travers (« 2'061.8 » pour « 2'061.85 »). Nécessite opencv ;
    sans lui, l'image est lue telle quelle."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("opencv absent : lecture sans effacement des traits (résultats moins fiables)", file=sys.stderr)
        return
    im = cv2.imread(chemin_png, cv2.IMREAD_GRAYSCALE)
    noir = (im < 140).astype(np.uint8) * 255
    vert = cv2.morphologyEx(noir, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 120)))
    horiz = cv2.morphologyEx(noir, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (120, 1)))
    traits = cv2.dilate(cv2.bitwise_or(vert, horiz), np.ones((3, 3), np.uint8))
    im[traits > 0] = 255
    cv2.imwrite(chemin_png, im)


def mots_ocr(chemin_pdf, doc_id, no_page):
    """Mots d'une page sans texte, par OCR (résultat mis en cache dans sources/ocr)."""
    cache = os.path.join(SRC, "ocr", f"{doc_id}-p{no_page}.tsv")
    if not os.path.exists(cache):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            img = os.path.join(tmp, "p")
            subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(no_page), "-l", str(no_page),
                            "-singlefile", chemin_pdf, img], check=True)
            effacer_traits(img + ".png")
            subprocess.run(["tesseract", img + ".png", os.path.join(tmp, "o"), "--psm", "6", "tsv"],
                           check=True, capture_output=True)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(os.path.join(tmp, "o.tsv"), encoding="utf-8") as f, open(cache, "w", encoding="utf-8") as g:
                g.write(f.read())
    echelle = 72 / 300
    mots = []
    with open(cache, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            t = (r.get("text") or "").strip()
            if not t or r["conf"] == "-1":
                continue
            l, tp, w, h = (int(r[k]) for k in ("left", "top", "width", "height"))
            mots.append({"x0": l * echelle, "top": tp * echelle, "x1": (l + w) * echelle,
                         "bottom": (tp + h) * echelle, "text": corrige_ocr(t), "ligne": (r["block_num"], r["par_num"], r["line_num"])})
    # montant coupé en deux (« 44'994 » + « 45 ») : recollé
    fus = []
    for m in mots:
        a = fus[-1] if fus else None
        if a and a["ligne"] == m["ligne"] and re.fullmatch(r"-?\d{1,3}(?:'\d{3})+", a["text"]) \
                and re.fullmatch(r"\d\d", m["text"]) and -20 <= m["x0"] - a["x1"] < 12:
            a["text"] += "." + m["text"]
            a["x1"] = max(a["x1"], m["x1"])
        else:
            fus.append(m)
    return fus


def lignes_de(mots, tol=2.5):
    """Regroupe les mots en lignes selon leur position verticale (milieu du mot)."""
    lignes = []
    for m in sorted(mots, key=lambda m: ((m["top"] + m["bottom"]) / 2, m["x0"])):
        c = (m["top"] + m["bottom"]) / 2
        if lignes and abs(lignes[-1][0] - c) <= tol:
            lignes[-1][1].append(m)
            lignes[-1][0] = sum((w["top"] + w["bottom"]) / 2 for w in lignes[-1][1]) / len(lignes[-1][1])
        else:
            lignes.append([c, [m]])
    return [(t, sorted(ws, key=lambda w: w["x0"])) for t, ws in lignes]


def est_detail(mots, n):
    """Page de détail : au moins trois comptes et l'en-tête « Charges / Revenus » de chaque colonne."""
    codes = sum(1 for w in mots if CODE.match(w["text"]))
    entetes = sum(1 for w in mots if w["text"] in ("Charges", "Revenus"))
    return codes >= 3 and entetes >= 2 * n


def pics_colonnes(pages, n):
    """Bords droits des 2n colonnes de montants, déduits des montants de toutes les pages de détail."""
    xs = sorted(w["x1"] for _, _, mots in pages for w in mots if MONTANT.match(w["text"]))
    groupes = []
    for x in xs:
        if groupes and x - groupes[-1][-1] <= 5:
            groupes[-1].append(x)
        else:
            groupes.append([x])
    groupes.sort(key=len, reverse=True)
    pics = sorted(sum(g) / len(g) for g in groupes[:2 * n])
    if len(pics) != 2 * n:
        sys.exit(f"{len(pics)} colonnes trouvées au lieu de {2 * n}")
    return pics


def amas(mots, ecart=5):
    """Regroupe les bords droits des montants d'une page : liste de (position moyenne, effectif)."""
    xs = sorted(w["x1"] for w in mots if MONTANT.match(w["text"]))
    groupes = []
    for x in xs:
        if groupes and x - groupes[-1][-1] <= ecart:
            groupes[-1].append(x)
        else:
            groupes.append([x])
    return [(sum(g) / len(g), len(g)) for g in groupes]


def modele_colonnes(pages, n):
    """Positions relatives des 2n colonnes (0 = première, 1 = dernière) et position moyenne des deux bords,
    d'après les pages numérisées qui ont tous leurs amas."""
    rel, bords = [], []
    for mots in pages:
        a = sorted(sorted(amas(mots), key=lambda c: -c[1])[:2 * n])
        if len(a) == 2 * n and all(c[1] >= 2 for c in a):
            x0, x1 = a[0][0], a[-1][0]
            rel.append([(c[0] - x0) / (x1 - x0) for c in a])
            bords.append((x0, x1))
    if not rel:
        sys.exit("pages numérisées : colonnes introuvables")
    mod = [sorted(r[j] for r in rel)[len(rel) // 2] for j in range(2 * n)]
    return mod, (sorted(b[0] for b in bords)[len(bords) // 2], sorted(b[1] for b in bords)[len(bords) // 2])


def pics_page_ocr(mots, mod, bords):
    """Colonnes d'une page numérisée : la position et l'échelle varient d'une page à l'autre ;
    on cherche le décalage qui colle le mieux au modèle."""
    cl = amas(mots)
    if not cl:
        return None
    meilleur = None
    for a in range(int(bords[0]) - 30, int(bords[0]) + 31):
        for b in range(int(bords[1]) - 30, int(bords[1]) + 31):
            pos = [a + u * (b - a) for u in mod]
            cout = sum(c[1] * min(abs(c[0] - p) for p in pos) for c in cl) \
                + 0.5 * (abs(a - bords[0]) + abs(b - bords[1])) * 0.2
            if meilleur is None or cout < meilleur[0]:
                meilleur = (cout, pos)
    return meilleur[1]


def extraire(doc, chemin):
    n = len(doc["colonnes"])
    pages = mots_pdf(chemin)
    ocr_pages = {}
    debut, fin = doc.get("pages_ocr", [0, 0])
    for i, (w, h, mots) in enumerate(pages):
        if debut <= i + 1 <= fin and len(mots) < 10:  # page enregistrée sans texte (dessin)
            ocr_pages[i] = mots_ocr(chemin, doc["id"], i + 1)
    plage = doc.get("pages_detail")
    detail = []
    for i, (w, h, mots) in enumerate(pages):
        mots = ocr_pages.get(i, mots)
        if plage and not (plage[0] <= i + 1 <= plage[1]):
            continue
        if est_detail(mots, n) or (i in ocr_pages and sum(1 for x in mots if CODE.match(x["text"])) >= 3):
            detail.append((i, w, h, mots))
    if not detail:
        sys.exit(f"{doc['id']} : pages de détail introuvables")
    # les pages courtes (moins de trois comptes) entre la première et la dernière page de détail en font partie
    premiere, derniere = detail[0][0], detail[-1][0]
    deja = {i for i, _, _, _ in detail}
    for i, (w, h, mots) in enumerate(pages):
        if premiere < i < derniere and i not in deja and i not in ocr_pages:
            codes = sum(1 for x in mots if CODE.match(x["text"]))
            entetes = sum(1 for x in mots if x["text"] in ("Charges", "Revenus"))
            if codes >= 1 and entetes >= 2 * n:
                detail.append((i, w, h, mots))
    detail.sort(key=lambda d: d[0])
    texte = [(w, h, m) for i, w, h, m in detail if i not in ocr_pages]
    pics_texte = pics_colonnes(texte, n) if texte else None
    if ocr_pages:
        mod, bords = modele_colonnes([m for i, _, _, m in detail if i in ocr_pages], n)
    lignes_out = []
    section_cour = None
    ignorees = []
    corriges = []
    for i, w, h, mots in detail:
        source = "ocr" if i in ocr_pages else "texte"
        pics = pics_page_ocr(mots, mod, bords) if source == "ocr" else pics_texte
        if pics is None:
            continue
        pas = min(b - a for a, b in zip(pics, pics[1:]))
        tol = pas * 0.45
        ent = [m for m in mots if m["text"] in ("Charges", "Revenus")]
        ht = min(m["top"] for m in ent) if ent else 0
        corps = [m for m in mots if m["top"] > ht + 4]
        for top, ws in lignes_de(corps, tol=2.5 if source == "texte" else 3.5):
            while ws and not re.search(r"[A-Za-zÀ-ÿ0-9]", ws[0]["text"]):  # bordure lue comme un caractère
                ws = ws[1:]
            if source == "ocr" and ws and re.fullmatch(r"\d{4}\d{4}\.\d{3}", ws[0]["text"]):  # « 35113154.000 » : service et compte collés
                ws = [dict(ws[0], text=ws[0]["text"][:4]), dict(ws[0], text=ws[0]["text"][4:])] + ws[1:]
            if source == "ocr":  # bordure du tableau lue comme un ou deux mots (« (ee) », « iN », « Oo} »)
                k = next((j for j, x in enumerate(ws) if re.fullmatch(r"\d{1,4}(?:\.\d{3})?", x["text"])), None)
                if k and k <= 2 and all(len(x["text"]) <= 4 for x in ws[:k]):
                    ws = ws[k:]
            if not ws:
                continue
            txt = " ".join(x["text"] for x in ws)
            if PIED.match(txt):
                continue
            # numéro de note en marge (« 15 1000 3151.000 … ») : retiré
            if len(ws) > 2 and re.fullmatch(r"\d{1,2}", ws[0]["text"]) and ws[0]["x1"] < ws[1]["x0"] - 5 and (
                    CODE.match(ws[1]["text"]) or re.fullmatch(r"\d{2,4}", ws[1]["text"])):
                ws = ws[1:]
            # montants sans centimes (« 45000 ») dans la zone des colonnes, sur une ligne de compte
            if any(CODE.match(x["text"]) for x in ws[:2]):
                ws = [dict(x, text=f"{int(x['text'])}.00") if re.fullmatch(r"\d{3,7}", x["text"])
                      and x["x0"] >= pics[0] - 60 else x for x in ws]
            # code de compte tronqué dans le document (« 4500 4812.00 » pour 4812.000), lu comme un montant
            if len(ws) > 2 and re.fullmatch(r"\d{4}", ws[0]["text"]) and re.fullmatch(r"\d{4}\.\d\d", ws[1]["text"]) \
                    and ws[1]["x1"] < pics[0] - 100:
                ws[1] = dict(ws[1], text=ws[1]["text"] + "0")
                corriges.append((i + 1, ws[0]["text"], ws[1]["text"]))
            nums = [x for x in ws if MONTANT.match(x["text"])]
            vals = [""] * (2 * n)
            for x in nums:
                j = min(range(2 * n), key=lambda k: abs(pics[k] - x["x1"]))
                if abs(pics[j] - x["x1"]) > tol:
                    sys.exit(f"{doc['id']} p.{i + 1} : montant hors colonne : {txt}")
                vals[j] = f"{montant(x['text']):.2f}"
            mots_txt = [x["text"] for x in ws if x not in nums]
            premier = mots_txt[0] if mots_txt else ""
            if len(mots_txt) > 1 and re.fullmatch(r"\d{4}", premier) and CODE.match(mots_txt[1]):
                typ, code, section_ligne, reste = "compte", mots_txt[1], premier, mots_txt[2:]
            elif CODE.match(premier):
                typ, code, section_ligne, reste = "compte", premier, section_cour, mots_txt[1:]
            elif re.fullmatch(r"\d{1,4}", premier) and (len(mots_txt) > 1 or len(nums) >= 2) and (
                    nums or premier == "0" or (len(premier) < 4 and " ".join(mots_txt[1:]).isupper())):
                typ = {1: "direction", 2: "groupe", 3: "fonction", 4: "section"}[len(premier)]
                code, section_ligne, reste = premier, "", mots_txt[1:]
                if typ == "section":
                    section_cour = code
            else:
                der = lignes_out[-1] if lignes_out else None
                if premier and nums and der and der["type"] != "compte" and der["page"] == i + 1 \
                        and not any(der[f"v{j}"] for j in range(2 * n)):
                    # suite du libellé d'un titre coupé sur deux lignes, avec les montants
                    der["libelle"] = (der["libelle"] + " " + " ".join(mots_txt)).strip()
                    for j, v in enumerate(vals):
                        der[f"v{j}"] = v
                    continue
                if premier and not nums and lignes_out and lignes_out[-1]["page"] == i + 1:
                    lignes_out[-1]["commentaire"] = (lignes_out[-1]["commentaire"] + " " + txt).strip()
                else:
                    ignorees.append((i + 1, txt))
                continue
            if typ == "compte" and not section_ligne:
                sys.exit(f"{doc['id']} p.{i + 1} : compte {code} avant toute section")
            lignes_out.append({"document": doc["id"], "page": i + 1, "source": source, "type": typ,
                               "section": section_ligne if typ == "compte" else "", "code": code,
                               "libelle": " ".join(reste).strip(), "commentaire": "",
                               **{f"v{j}": v for j, v in enumerate(vals)}})
    for p, sec, code in corriges:
        print(f"     code tronqué corrigé p.{p} : {sec} {code}")
    return lignes_out, ignorees, [i + 1 for i, _, _, _ in detail]


def totaux_document(chemin, n):
    """Totaux officiels : ligne « TOTAUX » du tableau récapitulatif (charges et revenus de chaque colonne),
    lue dans le texte du document, donc indépendante du détail par compte. Renvoie (charges, revenus, arrondi) ;
    `arrondi` vaut vrai quand le tableau est arrondi au franc. Une ligne avec centimes est préférée."""
    txt = subprocess.run(["pdftotext", "-layout", chemin, "-"], capture_output=True, text=True, check=True).stdout
    precis, arrondis = None, None
    for ln in txt.split("\n"):
        m = re.match(r"^\s*(?:0\s+)?(?:TOTAUX|TOTAL|Fonctionnement)\s{2,}(.*)$", ln)
        if not m:
            continue
        dec = [t.replace("\u2010", "-") for t in re.findall(r"[-\u2010]?\d{1,3}(?:['’]\d{3})*\.\d\d", m.group(1))]
        if len(dec) >= 2 * n and precis is None:
            v = [float(re.sub(r"['’]", "", t)) for t in dec[:2 * n]]
            if min(v) > 1e6:  # un total communal, pas une petite ligne
                precis = (v[0::2], v[1::2], False)
        jetons = [re.sub(r"[\s'’]", "", t.replace("\u2010", "-")) for t in re.split(r"\s{2,}", m.group(1).strip())]
        if len(jetons) >= 2 * n and all(re.fullmatch(r"-?\d+", t) for t in jetons[:2 * n]) and arrondis is None:
            v = [float(t) for t in jetons[:2 * n]]
            if min(v) > 1e6:
                arrondis = (v[0::2], v[1::2], True)
    return precis or arrondis


def appliquer_corrections(doc_id, lignes):
    """Corrections manuelles (sources/corrections.csv) d'erreurs de lecture vérifiées sur l'image du PDF."""
    chemin = os.path.join(SRC, "corrections.csv")
    n = 0
    if os.path.exists(chemin):
        for c in csv.DictReader(open(chemin, encoding="utf-8")):
            if c["document"] != doc_id:
                continue
            cible = [l for l in lignes if l["type"] == c["type"] and l["code"] == c["code"] and l["section"] == c["section"]]
            if len(cible) != 1:
                sys.exit(f"Correction introuvable ou ambiguë : {c}")
            cible[0][c["colonne"]] = f"{float(c['valeur']):.2f}"
            n += 1
    return n


def noms_natures(chemin):
    """Noms des natures (30, 300, 31, …) lus dans le tableau des charges et revenus par nature."""
    txt = subprocess.run(["pdftotext", "-layout", chemin, "-"], capture_output=True, text=True, check=True).stdout
    res = {}
    for ln in txt.split("\n"):
        m = re.match(r"^\s*(\d{2,3})\s+([A-ZÀ-Üa-zà-ü][^\d]*?)\s{2,}(?:-?\d)", ln)
        if m and m.group(1)[0] in "34" and m.group(1) not in res:
            res[m.group(1)] = m.group(2).strip()
    return res


def main():
    cfg = json.load(open(os.path.join(SRC, "documents.json"), encoding="utf-8"))
    choix = set(sys.argv[1:])
    os.makedirs(os.path.join(SRC, "extraits"), exist_ok=True)
    for doc in cfg["documents"]:
        if choix and doc["id"] not in choix:
            continue
        chemin = os.path.join(SRC, "pdf", doc["fichier"])
        if not os.path.exists(chemin):
            print(f"{doc['id']} : PDF absent ({chemin}), extraction existante conservée")
            continue
        lignes, ignorees, pages = extraire(doc, chemin)
        nc = appliquer_corrections(doc["id"], lignes)
        if nc:
            print(f"{doc['id']} : {nc} corrections manuelles (sources/corrections.csv)")
        n = len(doc["colonnes"])
        champs = CHAMPS[:7] + [f"v{j}" for j in range(2 * n)] + ["commentaire"]
        with open(os.path.join(SRC, "extraits", doc["id"] + ".csv"), "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=champs)
            wr.writeheader()
            wr.writerows(lignes)
        totaux = {"charges": [None] * n, "revenus": [None] * n}
        arrondi = False
        t = totaux_document(chemin, n)
        if t:
            totaux["charges"], totaux["revenus"], arrondi = t
        annexes = {"colonnes": doc["colonnes"], "totaux": totaux, "arrondi": arrondi, "natures": noms_natures(chemin), "directions": {}}
        with open(os.path.join(SRC, "extraits", doc["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(annexes, f, ensure_ascii=False, indent=1, sort_keys=True)
        c = Counter(l["type"] for l in lignes)
        ocr = sum(1 for l in lignes if l["source"] == "ocr")
        print(f"{doc['id']} : pages {pages[0]}-{pages[-1]} ({len(pages)}), {c['compte']} comptes, {c['section']} services, "
              f"{c['fonction']} fonctions, {c['groupe']} groupes, {c['direction']} directions, {ocr} lignes par OCR ; "
              f"{len(ignorees)} lignes ignorées")
        for p, t in ignorees[:8]:
            print(f"     ignorée p.{p} : {t[:110]}")


if __name__ == "__main__":
    main()
