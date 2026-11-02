"""Mise en forme lisible des libellés (écrits en majuscules sans accents dans les documents).

Le libellé original reste dans les fichiers de données ; cette version sert à l'affichage :
minuscules, accents rétablis pour les mots courants, sigles et noms propres conservés.
"""
import re

ACCENTS = {
    "ACCORDEONISTES": "accordéonistes", "ACTIVITES": "activités", "AINES": "aînés", "AÎNES": "aînés",
    "AMELIORATIONS": "améliorations", "ANNEE": "année", "ANTERIEURES": "antérieures", "APRES": "après",
    "ARRIERES": "arriérés", "ASSIMILES": "assimilés", "ASSOCIATION": "association", "AUTORITES": "autorités",
    "AOUT": "août", "BAT": "bât.", "BATIMENT": "bâtiment", "BATIMENTS": "bâtiments", "BENEFICE": "bénéfice",
    "BIBLIOTHEQUE": "bibliothèque", "CANTONALE": "cantonale", "CENTRE": "centre", "CHATEAU": "château",
    "CHATTONS": "chattons", "CIMETIERE": "cimetière", "CIMETIERES": "cimetières", "CITE": "cité",
    "COHESION": "cohésion", "COLLEGE": "collège", "COMMUNAUTE": "communauté", "COMPLEMENTAIRE": "complémentaire",
    "COMPTABILITE": "comptabilité", "CONFRERIE": "confrérie", "CONTROLE": "contrôle", "CREANCES": "créances",
    "CULTURELLES": "culturelles", "DEBITEURS": "débiteurs", "DECHETS": "déchets", "DECORATION": "décoration",
    "DECORATIONS": "décorations", "DEFALCATIONS": "défalcations", "DEFENSE": "défense", "DENEIGEMENT": "déneigement",
    "EDICULES": "édicules", "EGOUTS": "égouts", "ECLAIRAGE": "éclairage", "ECOLAGE": "écolage", "ECOLE": "école",
    "ECOLES": "écoles", "ECONOMIE": "économie", "ECRIRE": "écrire", "ELECTIONS": "élections",
    "ELECTRICITE": "électricité", "ELEVAGE": "élevage", "ELEVES": "élèves", "ELIMINATION": "élimination",
    "EMOLUMENTS": "émoluments", "EMPLOYES": "employés", "ENERGIE": "énergie", "ENTREES": "entrées",
    "EPURATION": "épuration", "EQUIPEMENT": "équipement", "ESPACES": "espaces", "ETABL": "établ.",
    "ETABLISSEMENT": "établissement", "ETAT": "État", "ETRANGERS": "étrangers", "ETUDES": "études",
    "EXPERTISES": "expertises", "FETE": "fête", "FÊTE": "fête", "FETONS": "fêtons", "FÊTONS": "fêtons",
    "FINANCIERS": "financiers", "FORET": "forêt", "FRANCAIS": "français", "FRANÇAIS": "français",
    "GENERALE": "générale", "GENERAUX": "généraux", "GENIE": "génie", "GERANCE": "gérance",
    "HELIOGRAPHIE": "héliographie", "HONORAIRES": "honoraires", "IDENTITE": "identité", "IMPOT": "impôt",
    "IMPOTS": "impôts", "IMPRIMES": "imprimés", "INCAPACITE": "incapacité", "INDEMNITES": "indemnités",
    "INFORMATIQUE": "informatique", "INTEGRATION": "intégration", "INTERETS": "intérêts", "ISRAELITE": "israélite",
    "LUDOTHEQUE": "ludothèque", "MANDAT": "mandat", "MARCHE": "marché", "MATERIEL": "matériel",
    "MEDECINS": "médecins", "MEDICAL": "médical", "MENAGERES": "ménagères", "MENAGERS": "ménagers",
    "MILITAIRES": "militaires", "MOBILITE": "mobilité", "MUNICIPALITE": "Municipalité", "OEUVRES": "œuvres",
    "OCTROYEES": "octroyées", "PANDEMIE": "pandémie", "PARASCOLAIRES": "parascolaires", "PATENTES": "patentes",
    "PATRIM": "patrim.", "PEDAGOGIQUE": "pédagogique", "PEDAGOGIQUES": "pédagogiques", "PEREQUATION": "péréquation",
    "PERIODE": "période", "PRE": "pré", "PRECE": "préc.", "PRECEDENTE": "précédente", "PRELEVEMENT": "prélèvement",
    "PRELEVEMENTS": "prélèvements", "PRESCOLAIRE": "préscolaire", "PRESENCE": "présence", "PRESERVATION": "préservation",
    "PREVOYANCE": "prévoyance", "PRIVEES": "privées", "PROPRIETE": "propriété", "PUBLICITE": "publicité",
    "RECEPTIONS": "réceptions", "RECETTES": "recettes", "RECREATIVES": "récréatives", "RECUPERABLE": "récupérable",
    "RECUPERATION": "récupération", "RECUPERES": "récupérés", "REFECTION": "réfection", "REFORME": "réforme",
    "REGION": "région", "REGIONAL": "régional", "REGIONAUX": "régionaux", "REMUNERATOIRES": "rémunératoires",
    "RESEAU": "réseau", "RESEAUX": "réseaux", "RÉSEAUX": "réseaux", "RESERVE": "réserve", "RESERVES": "réserves",
    "RECHERCHE": "recherche", "ROUTIERE": "routière", "SANTE": "santé", "SECONDAIRE": "secondaire",
    "SECURITE": "sécurité", "SEJOUR": "séjour", "SOCIETES": "sociétés", "SPECIALISE": "spécialisé",
    "SPECIALISTES": "spécialistes", "SPECIAL": "spécial", "SYSTEMATIQUE": "systématique", "TELEPHONE": "téléphone",
    "THEATRES": "théâtres", "UNIVERSITE": "université", "VEHICULES": "véhicules", "VENTILES": "ventilés",
    "VETEMENTS": "vêtements", "MATERIELS": "matériels", "CONTENEURS": "conteneurs", "DETTE": "dette",
    "DETTES": "dettes", "REMISES": "remises", "PREVO": "prévo", "ENFANCE": "enfance", "FACTURE": "facture",
    "INFRASTRUCTURE": "infrastructure", "CATEGORIE": "catégorie", "ENERGETIQUE": "énergétique",
    "MEZERY": "Mézery", "A": "à", "NOEL": "Noël", "REDEV": "redev.", "ADMIN": "admin.", "ETIENNE": "Étienne", "ECOLES,": "écoles,", "ELECTIONS,": "élections,",
}
SIGLES = {
    "AVS", "AF", "AC", "CIP", "FAJE", "APEMS", "ASIGOS", "TVA", "CFF", "SDOL", "SDNL", "UAPE", "AMF", "AJENOL",
    "ARASPE", "CISIP", "CVAJ", "CVE", "CRP", "EERV", "ORPC", "PGEE", "STEP", "SI", "FEE", "FDD", "FDL", "AAS",
    "CRENOL", "AIL", "CET", "COVID", "SA", "TP", "TEC", "ECA", "LAJE", "UCV", "SDIS", "RH", "EPT", "ETP", "CO2",
    "BHNS", "CAD", "SIT", "PPA", "PQ", "PGA", "CSM", "CSR", "DGEJ", "NPIV", "CC", "CAP", "OEJS", "ACMA", "CISTEP",
    "CLÉ", "SGA", "APG", "SUVA", "IJM", "BDC",
}
PROPRES = {
    "PRILLY", "MALLEY", "JOUXTENS", "LAUSANNE", "COSSONAY", "SEPEY", "CASTELMONT", "TILLEUL", "GOULIN",
    "JOLIMONT", "ACACIAS", "FONTADEL", "VIAESCOLA", "VALORSA", "EPURA", "BROYE", "VILLAMONT", "JOSEPH", "RENENS",
    "VERNAND", "CORMINJOZ", "PLANTINEL", "SORBIERS", "BRADUT", "HIRONDELLE", "LYS", "FLEUR", "MONT", "GLOBE",
    "MOBILITY", "CINEFESTIVAL", "PASTEUR", "BEL", "ORNE", "CHAVANNES", "VAUDOIS", "VAUD",
    "EPALINGES", "ÉPALINGES", "CROISETTES", "CHAUGAND", "MURAT", "GIZIAUX", "PALINZARD", "CABOLÉTAZ", "OFRÉQUAZ",
}


def lisible(lib):
    if not lib:
        return lib
    mots = re.split(r"(\W+)", lib)
    out = []
    for m in mots:
        u = m.upper()
        if not m or not re.match(r"\w", m):
            out.append(m)
        elif u in SIGLES or (1 < len(m) <= 5 and m.isupper() and not re.search(r"[AEIOUYÀ-Ü]", u)):
            out.append(u)
        elif u in PROPRES:
            out.append(u[:1] + u[1:].lower())
        elif u in ACCENTS:
            out.append(ACCENTS[u])
        else:
            out.append(m.lower())
    s = "".join(out).replace("plan-Sepey", "Plan-Sepey").replace("Plan-sepey", "Plan-Sepey")
    return s[:1].upper() + s[1:]
