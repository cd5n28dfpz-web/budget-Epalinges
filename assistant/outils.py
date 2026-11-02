"""Outils de requête sur les données du budget de la Commune d'Épalinges.

Ces fonctions lisent uniquement les fichiers CSV du dossier data/ et renvoient des
résultats compacts (dictionnaires et listes), prêts à être transmis à une IA.
Elles sont partagées par le serveur MCP (mcp_server.py) et le script ask.py.

Séries : C<année> = comptes, B<année> = budget voté, P<année> = projet de la Municipalité.
Bibliothèque standard uniquement. Montants en francs.
"""
import csv
import os
import unicodedata
from functools import lru_cache

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TYPES = {"C": "comptes", "B": "budget voté", "P": "projet de budget"}
SYNONYMES = {
    "ecole": ["ecole", "enseignement", "scolaire", "apems", "asigos", "classes", "eleves"],
    "creche": ["accueil", "prescolaire", "ajenol", "uape", "mamans d'accueil", "faje", "enfance"],
    "impot": ["impot"], "dechets": ["dechets", "ordures", "valorsa", "ramassage"],
    "salaire": ["traitements", "personnel"], "transport": ["transports"], "bus": ["transports"],
    "social": ["social", "sociale", "facture sociale", "araspe", "prevoyance sociale"],
    "sport": ["sport", "piscine", "malley", "patinoire", "football"], "culture": ["culture", "theatre", "bibliotheque"],
    "subvention": ["subvention", "aides"], "energie": ["energie", "electricite", "chauffage", "gaz"],
}


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def donnees():
    lignes = _read("lignes_large.csv")
    base = {"direction", "direction_nom", "groupe", "groupe_nom", "section", "section_nom", "compte", "nature",
            "nature_nom", "sens", "libelle", "libelle_lisible"}
    series = [c for c in lignes[0] if c not in base]
    comm = {}
    for c in _read("commentaires.csv"):
        comm.setdefault((c["section"], c["compte"]), []).append(c)
    for l in lignes:
        l["cle"] = norm(" ".join([l["section"], l["compte"], l["section"] + "." + l["compte"], l["libelle"],
                                  l["section_nom"], l["groupe_nom"]] +
                                 [c["texte"] for c in comm.get((l["section"], l["compte"]), [])]))
    return {"lignes": lignes, "series": series, "comm": comm, "resultats": _read("resultats.csv"),
            "amendements": _read("amendements.csv"), "sections": _read("sections.csv")}


def _serie(annee=None, type_="comptes"):
    t = norm(type_ or "comptes")
    p = "P" if t.startswith("p") else "B" if t.startswith("b") else "C"
    dispo = [s for s in donnees()["series"] if s[0] == p]
    if annee is None:
        return dispo[-1]
    s = f"{p}{int(annee)}"
    if s not in donnees()["series"]:
        raise ValueError(f"Série {s} indisponible. Disponibles : {', '.join(donnees()['series'])}")
    return s


def _nom(s):
    return f"{TYPES[s[0]]} {s[1:]}"


def _ligne(l, series):
    return {"section": l["section"], "service": l["section_nom"], "compte": l["compte"], "libelle": l["libelle_lisible"],
            "sens": l["sens"], **{_nom(s): _f(l[s]) for s in series if _f(l[s]) is not None}}


def series_disponibles():
    """Liste des séries disponibles (comptes, budgets votés, projets) avec leurs totaux officiels et leur source."""
    return {"series": [{"serie": r["serie"], "type": r["type"], "annee": int(r["annee"]), "charges": float(r["charges"]),
                        "revenus": float(r["revenus"]), "resultat_revenus_moins_charges": float(r["resultat"]),
                        "documents": r["documents"]} for r in donnees()["resultats"]],
            "note": "Résultat négatif = excédent de charges (déficit). Totaux officiels, imputations internes comprises."}


def rechercher_lignes(texte, annee=None, type="comptes", sens=None, limite=20):
    """Cherche des lignes du budget de fonctionnement par mots courants, numéro de compte ou de service. Renvoie les montants de la série demandée et de toutes les autres."""
    t = norm(texte).strip()
    termes = SYNONYMES.get(t) or SYNONYMES.get(t.rstrip("s")) or [t.rstrip("s") if len(t) > 3 else t]
    s = _serie(annee, type)
    res = [l for l in donnees()["lignes"] if any(x in l["cle"] for x in termes)
           and (not sens or l["sens"] == ("charge" if norm(sens).startswith("c") else "revenu"))]
    res.sort(key=lambda l: -abs(_f(l[s]) or 0))
    return {"serie_de_tri": _nom(s), "termes": termes, "nombre": len(res),
            "lignes": [_ligne(l, donnees()["series"]) for l in res[:int(limite)]]}


def detail_ligne(section, compte):
    """Historique complet d'une ligne (tous les comptes, budgets et projets) et commentaires de la commune."""
    for l in donnees()["lignes"]:
        if l["section"] == str(section) and l["compte"] in (str(compte), str(compte).replace(".", "")[:4] + "." + str(compte).replace(".", "")[4:]):
            return {**_ligne(l, donnees()["series"]), "direction": l["direction_nom"], "nature": l["nature_nom"],
                    "commentaires": [{"document": c["document"], "texte": c["texte"]}
                                     for c in donnees()["comm"].get((l["section"], l["compte"]), [])]}
    return {"erreur": f"Ligne {section}.{compte} introuvable"}


def lister_services(direction=None):
    """Liste des services (sections) avec leur groupe et leur direction."""
    return [s for s in donnees()["sections"] if not direction or s["direction"] == str(direction)
            or norm(direction) in norm(s["direction_nom"])]


def fiche_service(section, annee=None):
    """Montants d'un service (section à 4 chiffres ou nom) pour toutes les séries, et ses principales lignes."""
    secs = [s for s in donnees()["sections"] if s["section"] == str(section) or norm(section) in norm(s["nom"])]
    if not secs:
        return {"erreur": f"Service {section} introuvable"}
    sec = secs[0]
    ls = [l for l in donnees()["lignes"] if l["section"] == sec["section"]]
    tot = {}
    for s in donnees()["series"]:
        ch = sum(_f(l[s]) or 0 for l in ls if l["sens"] == "charge")
        rv = sum(_f(l[s]) or 0 for l in ls if l["sens"] == "revenu")
        if any(_f(l[s]) is not None for l in ls):
            tot[_nom(s)] = {"charges": round(ch, 2), "revenus": round(rv, 2), "cout_net": round(ch - rv, 2)}
    s = _serie(annee, "comptes")
    top = sorted(ls, key=lambda l: -abs(_f(l[s]) or 0))[:15]
    return {"service": sec, "totaux": tot, "principales_lignes": [_ligne(l, [s, _serie(None, "budget")]) for l in top],
            "autres_services_correspondants": [x["section"] + " " + x["nom"] for x in secs[1:6]]}


def totaux(annee=None, type="comptes", par="direction", sans_imputations=True):
    """Totaux d'une série par direction, groupe, service ou nature, en charges, revenus et coût net."""
    s = _serie(annee, type)
    cle = {"direction": ("direction", "direction_nom"), "groupe": ("groupe", "groupe_nom"),
           "service": ("section", "section_nom"), "nature": ("nature", "nature_nom")}[par if par in ("groupe", "service", "nature") else "direction"]
    agg = {}
    for l in donnees()["lignes"]:
        v = _f(l[s])
        if v is None or (sans_imputations and l["compte"][:2] in ("39", "49")):
            continue
        a = agg.setdefault(l[cle[0]], {"code": l[cle[0]], "nom": l[cle[1]], "charges": 0.0, "revenus": 0.0})
        a["charges" if l["sens"] == "charge" else "revenus"] += v
    out = sorted(agg.values(), key=lambda a: -a["charges"])
    for a in out:
        a["cout_net"] = round(a["charges"] - a["revenus"], 2)
    return {"serie": _nom(s), "imputations_internes_exclues": bool(sans_imputations), "par": par, "totaux": out}


def comparer(annee_a, annee_b, type_a="comptes", type_b="comptes", niveau="service", sens="charges", limite=15):
    """Plus fortes hausses et baisses entre deux séries, par service ou par ligne (hors imputations internes)."""
    a, b = _serie(annee_a, type_a), _serie(annee_b, type_b)
    sn = "charge" if norm(sens).startswith("c") else "revenu"
    agg = {}
    for l in donnees()["lignes"]:
        if l["sens"] != sn or l["compte"][:2] in ("39", "49"):
            continue
        k = l["section"] if niveau == "service" else l["section"] + "." + l["compte"]
        n = l["section_nom"] if niveau == "service" else f"{l['libelle_lisible']} ({l['section_nom']})"
        x = agg.setdefault(k, {"code": k, "nom": n, "avant": 0.0, "apres": 0.0})
        x["avant"] += _f(l[a]) or 0
        x["apres"] += _f(l[b]) or 0
    it = [dict(x, ecart=round(x["apres"] - x["avant"], 2)) for x in agg.values() if abs(x["apres"] - x["avant"]) >= 1]
    it.sort(key=lambda x: x["ecart"])
    return {"de": _nom(a), "a": _nom(b), "sens": sn, "hausses": it[::-1][:int(limite)], "baisses": it[:int(limite)],
            "attention": "Une ligne qui apparaît ou disparaît peut refléter une réorganisation des services."}


def budget_vs_comptes(annee, niveau="ligne", sens="charges", limite=20):
    """Écarts entre le budget voté et les comptes d'une même année, avec les commentaires de la commune."""
    b, c = _serie(annee, "budget"), _serie(annee, "comptes")
    sn = "charge" if norm(sens).startswith("c") else "revenu"
    it = []
    for l in donnees()["lignes"]:
        if l["sens"] != sn:
            continue
        vb, vc = _f(l[b]) or 0, _f(l[c]) or 0
        if abs(vc - vb) >= 1:
            it.append({"section": l["section"], "service": l["section_nom"], "compte": l["compte"],
                       "libelle": l["libelle_lisible"], "budget": vb, "comptes": vc, "ecart": round(vc - vb, 2),
                       "commentaires": [x["texte"] for x in donnees()["comm"].get((l["section"], l["compte"]), [])
                                        if x["document"].startswith("comptes")]})
    if niveau == "service":
        agg = {}
        for x in it:
            a = agg.setdefault(x["section"], {"section": x["section"], "service": x["service"], "budget": 0.0, "comptes": 0.0})
            a["budget"] += x["budget"]
            a["comptes"] += x["comptes"]
        it = [dict(a, ecart=round(a["comptes"] - a["budget"], 2)) for a in agg.values()]
    it.sort(key=lambda x: -abs(x["ecart"]))
    r = {x["serie"]: x for x in donnees()["resultats"]}
    return {"budget": _nom(b), "comptes": _nom(c), "sens": sn,
            "total_budget": float(r[b]["charges" if sn == "charge" else "revenus"]),
            "total_comptes": float(r[c]["charges" if sn == "charge" else "revenus"]),
            "resultat_budget": float(r[b]["resultat"]), "resultat_comptes": float(r[c]["resultat"]),
            "ecarts": it[:int(limite)]}


def amendements(annee=None):
    """Lignes modifiées entre le projet de la Municipalité et le budget voté par le Conseil communal."""
    am = donnees()["amendements"]
    if annee:
        am = [a for a in am if a["annee"] == str(annee)]
    return {"nombre": len(am), "lignes": [dict(a, projet=float(a["projet"]), vote=float(a["vote"]),
                                               difference=float(a["difference"])) for a in am],
            "note": "Le budget 2025 « version 2 » intégrait déjà les amendements votés sur la première version ; "
                    "les différences 2025 sont celles votées sur la version 2."}


OUTILS = {
    "series_disponibles": (series_disponibles, {}),
    "rechercher_lignes": (rechercher_lignes, {"texte": ("string", "Mots, numéro de compte ou de service", True),
                                              "annee": ("integer", "Année (par défaut : derniers comptes)", False),
                                              "type": ("string", "'comptes', 'budget' (voté) ou 'projet'", False),
                                              "sens": ("string", "'charges' ou 'revenus' (facultatif)", False),
                                              "limite": ("integer", "Nombre de lignes renvoyées (défaut 20)", False)}),
    "detail_ligne": (detail_ligne, {"section": ("string", "Numéro de service à 4 chiffres", True),
                                    "compte": ("string", "Numéro de compte, ex. 3011.000", True)}),
    "lister_services": (lister_services, {"direction": ("string", "Numéro (1 à 7) ou nom de direction (facultatif)", False)}),
    "fiche_service": (fiche_service, {"section": ("string", "Numéro ou nom du service", True),
                                      "annee": ("integer", "Année des principales lignes (comptes)", False)}),
    "totaux": (totaux, {"annee": ("integer", "Année", False), "type": ("string", "'comptes', 'budget' ou 'projet'", False),
                        "par": ("string", "'direction', 'groupe', 'service' ou 'nature'", False),
                        "sans_imputations": ("boolean", "Exclure les imputations internes (défaut oui)", False)}),
    "comparer": (comparer, {"annee_a": ("integer", "Première année", True), "annee_b": ("integer", "Seconde année", True),
                            "type_a": ("string", "'comptes', 'budget' ou 'projet'", False),
                            "type_b": ("string", "'comptes', 'budget' ou 'projet'", False),
                            "niveau": ("string", "'service' ou 'ligne'", False), "sens": ("string", "'charges' ou 'revenus'", False),
                            "limite": ("integer", "Nombre de résultats", False)}),
    "budget_vs_comptes": (budget_vs_comptes, {"annee": ("integer", "Année (budget voté et comptes disponibles)", True),
                                              "niveau": ("string", "'ligne' ou 'service'", False),
                                              "sens": ("string", "'charges' ou 'revenus'", False),
                                              "limite": ("integer", "Nombre de résultats", False)}),
    "amendements": (amendements, {"annee": ("integer", "Année du budget (facultatif)", False)}),
}


def schema(nom):
    fn, params = OUTILS[nom]
    props = {k: {"type": t, "description": desc} for k, (t, desc, _) in params.items()}
    req = [k for k, (_, _, r) in params.items() if r]
    return {"name": nom, "description": " ".join(fn.__doc__.split()),
            "inputSchema": {"type": "object", "properties": props, "required": req}}


def appeler(nom, arguments):
    if nom not in OUTILS:
        return {"erreur": f"Outil inconnu : {nom}"}
    fn, params = OUTILS[nom]
    args = {k: v for k, v in (arguments or {}).items() if k in params and v not in (None, "")}
    try:
        return fn(**args)
    except Exception as e:  # message clair renvoyé à l'IA plutôt qu'un plantage
        return {"erreur": str(e)}
