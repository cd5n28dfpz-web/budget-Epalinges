#!/usr/bin/env python3
"""Serveur MCP (Model Context Protocol) pour interroger le budget d'Épalinges avec votre IA.

Il expose les outils de assistant/outils.py (recherche de lignes, comparaisons,
budget vs comptes, bénéficiaires…) à tout client MCP : Claude Desktop, Claude Code,
Cursor, LM Studio, etc. Transport stdio, bibliothèque standard uniquement.

Lancement (normalement fait par le client MCP) :  python assistant/mcp_server.py
Voir docs/assistant.md pour la configuration.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outils  # noqa: E402

VERSION_PROTOCOLE = "2025-06-18"
CONSIGNES = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "consignes.md"), encoding="utf-8").read()


def reponse(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def traiter(msg):
    methode, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if id_ is None:  # notification : pas de réponse
        return
    if methode == "initialize":
        reponse(id_, {"protocolVersion": params.get("protocolVersion", VERSION_PROTOCOLE),
                      "capabilities": {"tools": {}, "prompts": {}},
                      "serverInfo": {"name": "budget-epalinges", "version": "1.0.0"},
                      "instructions": CONSIGNES})
    elif methode == "ping":
        reponse(id_, {})
    elif methode == "tools/list":
        reponse(id_, {"tools": [outils.schema(n) for n in outils.OUTILS]})
    elif methode == "tools/call":
        res = outils.appeler(params.get("name"), params.get("arguments"))
        texte = json.dumps(res, ensure_ascii=False)
        reponse(id_, {"content": [{"type": "text", "text": texte}],
                      "isError": isinstance(res, dict) and "erreur" in res})
    elif methode == "prompts/list":
        reponse(id_, {"prompts": [{"name": "budget_epalinges",
                                   "description": "Consignes de neutralité et de méthode pour interroger le budget d'Épalinges"}]})
    elif methode == "prompts/get":
        reponse(id_, {"description": "Consignes pour interroger le budget d'Épalinges",
                      "messages": [{"role": "user", "content": {"type": "text", "text": CONSIGNES}}]})
    elif methode in ("resources/list", "resources/templates/list"):
        reponse(id_, {"resources": []} if methode == "resources/list" else {"resourceTemplates": []})
    else:
        reponse(id_, error={"code": -32601, "message": f"Méthode inconnue : {methode}"})


def main():
    print("Serveur MCP budget-epalinges prêt (stdio).", file=sys.stderr)
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            msg = json.loads(ligne)
        except json.JSONDecodeError:
            reponse(None, error={"code": -32700, "message": "JSON invalide"})
            continue
        try:
            traiter(msg)
        except Exception as e:  # ne jamais interrompre le serveur
            reponse(msg.get("id"), error={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
