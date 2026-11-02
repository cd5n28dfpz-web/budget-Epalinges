#!/usr/bin/env python3
"""Interroger le budget d'Épalinges avec n'importe quel modèle compatible avec l'API OpenAI.

Fonctionne avec un modèle local (Ollama, LM Studio) ou un service en ligne
(OpenAI, Mistral, Anthropic, Infomaniak…), à condition que le modèle sache appeler des outils.
Le modèle ne répond qu'à partir des données du dossier data/, via les outils de outils.py.

Configuration par variables d'environnement (ou options en ligne de commande) :
  LLM_BASE_URL   adresse de l'API, par exemple http://localhost:11434/v1 (Ollama)
  LLM_API_KEY    clé d'API (inutile pour un modèle local)
  LLM_MODEL      nom du modèle, par exemple qwen2.5:14b ou gpt-4o-mini

Exemples :
  python assistant/ask.py "Combien coûte la police en 2025 ?"
  python assistant/ask.py          # mode conversation
Bibliothèque standard uniquement. Voir docs/assistant.md.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outils  # noqa: E402

CONSIGNES = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "consignes.md"), encoding="utf-8").read()
MAX_ETAPES = 12
MAX_CARACTERES_RESULTAT = 12000


def outils_openai():
    return [{"type": "function", "function": {"name": s["name"], "description": s["description"], "parameters": s["inputSchema"]}}
            for s in (outils.schema(n) for n in outils.OUTILS)]


def appel_api(base, cle, modele, messages, tools):
    url = base.rstrip("/") + "/chat/completions"
    corps = json.dumps({"model": modele, "messages": messages, "tools": tools, "temperature": 0.1}).encode("utf-8")
    entetes = {"Content-Type": "application/json"}
    if cle:
        entetes["Authorization"] = f"Bearer {cle}"
    req = urllib.request.Request(url, data=corps, headers=entetes, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"Erreur de l'API ({e.code}) : {e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"Impossible de joindre {url} : {e.reason}. Vérifiez LLM_BASE_URL et que le service est démarré.")


def repondre(question, historique, base, cle, modele, verbeux=False):
    historique.append({"role": "user", "content": question})
    tools = outils_openai()
    for _ in range(MAX_ETAPES):
        rep = appel_api(base, cle, modele, historique, tools)
        msg = rep["choices"][0]["message"]
        appels = msg.get("tool_calls") or []
        historique.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls") and v is not None} | {"role": "assistant"})
        if not appels:
            return msg.get("content") or ""
        for a in appels:
            nom = a["function"]["name"]
            try:
                args = json.loads(a["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if verbeux:
                print(f"  → {nom}({json.dumps(args, ensure_ascii=False)})", file=sys.stderr)
            res = json.dumps(outils.appeler(nom, args), ensure_ascii=False)
            if len(res) > MAX_CARACTERES_RESULTAT:
                res = res[:MAX_CARACTERES_RESULTAT] + "… [résultat tronqué : affinez la demande]"
            historique.append({"role": "tool", "tool_call_id": a.get("id", nom), "content": res})
    return "Je n'ai pas pu terminer la réponse en un nombre raisonnable d'étapes. Essayez une question plus précise."


def main():
    p = argparse.ArgumentParser(description="Interroger le budget d'Épalinges avec votre modèle de langage.")
    p.add_argument("question", nargs="*", help="Question (sans question : mode conversation)")
    p.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"))
    p.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--model", default=os.environ.get("LLM_MODEL", ""))
    p.add_argument("-v", "--verbeux", action="store_true", help="Afficher les outils appelés")
    a = p.parse_args()
    if not a.model:
        sys.exit("Indiquez le modèle avec --model ou la variable LLM_MODEL (voir docs/assistant.md).")
    historique = [{"role": "system", "content": CONSIGNES}]
    if a.question:
        print(repondre(" ".join(a.question), historique, a.base_url, a.api_key, a.model, a.verbeux))
        return
    print("Posez vos questions sur le budget d'Épalinges (Entrée sur une ligne vide pour quitter).")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        print("\n" + repondre(q, historique, a.base_url, a.api_key, a.model, a.verbeux))


if __name__ == "__main__":
    main()
