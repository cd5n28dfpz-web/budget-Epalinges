# Interroger le budget avec votre IA

Le dossier `assistant/` permet de poser des questions en langage courant (« Combien coûte la piscine de la Fleur-de-Lys ? ») à l'IA de votre choix. L'IA ne répond pas de mémoire : elle utilise des outils qui lisent les fichiers de `data/`, puis cite les lignes utilisées.

Les consignes données à l'IA (`assistant/consignes.md`) lui demandent de rester neutre : décrire les chiffres, sans dire ce qu'il faudrait en penser.

## 1. Télécharger le projet

Sur la page GitHub du projet : bouton **Code** → **Download ZIP**, puis décompressez. Ou en ligne de commande :

```sh
git clone https://github.com/andant89/budget-epalinges.git
```

Il faut Python 3.9 ou plus récent (installé d'office sur macOS et la plupart des Linux ; sous Windows, depuis python.org). Aucune autre installation n'est nécessaire.

## 2. Choisir comment brancher votre IA

### A. Avec une application compatible MCP (Claude Desktop, Claude Code, Cursor, LM Studio…)

MCP (Model Context Protocol) est un standard qui permet à une application d'IA d'utiliser des outils externes. Le projet fournit un serveur MCP : `assistant/mcp_server.py`.

**Claude Desktop** : menu Réglages → Développeur → Modifier la configuration, puis ajoutez (en remplaçant le chemin par celui de votre dossier) :

```json
{
  "mcpServers": {
    "budget-epalinges": {
      "command": "python3",
      "args": ["/chemin/vers/budget-epalinges/assistant/mcp_server.py"]
    }
  }
}
```

Sous Windows, utilisez `"command": "python"` et un chemin du type `"C:\\Users\\vous\\budget-epalinges\\assistant\\mcp_server.py"`. Redémarrez l'application : les outils « budget-epalinges » apparaissent.

**Claude Code** :

```sh
claude mcp add budget-epalinges -- python3 /chemin/vers/budget-epalinges/assistant/mcp_server.py
```

**Autres applications** (Cursor, LM Studio, etc.) : déclarez un serveur MCP de type « stdio » avec la commande `python3` et l'argument `chemin/vers/assistant/mcp_server.py`, selon la documentation de l'application.

### B. Avec n'importe quel modèle compatible OpenAI (local ou en ligne)

Le script `assistant/ask.py` fonctionne avec tout service qui imite l'API OpenAI, à condition que le modèle sache appeler des outils (« tool calling » ou « function calling »).

Configuration par trois variables :

| Variable | Rôle |
|---|---|
| `LLM_BASE_URL` | adresse de l'API |
| `LLM_API_KEY` | votre clé (inutile pour un modèle local) |
| `LLM_MODEL` | nom du modèle |

Exemples :

```sh
# Modèle local avec Ollama (rien ne quitte votre ordinateur)
ollama pull qwen2.5:14b
export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=qwen2.5:14b

# Service en ligne : remplacez par l'adresse, la clé et le modèle de votre fournisseur
export LLM_BASE_URL=https://api.mistral.ai/v1 LLM_API_KEY=... LLM_MODEL=...
export LLM_BASE_URL=https://api.openai.com/v1 LLM_API_KEY=... LLM_MODEL=...
export LLM_BASE_URL=https://api.anthropic.com/v1/ LLM_API_KEY=... LLM_MODEL=...

python3 assistant/ask.py "Combien coûte la police en 2025 ?"
python3 assistant/ask.py            # mode conversation
python3 assistant/ask.py -v "..."   # affiche les outils appelés
```

Sous Windows, remplacez `export X=...` par `set X=...` (invite de commandes) ou `$env:X="..."` (PowerShell).

Les petits modèles locaux appellent les outils moins bien que les grands ; si les réponses sont imprécises, essayez un modèle plus grand ou demandez plus précisément.

## 3. Outils à disposition de l'IA

| Outil | Ce qu'il fait |
|---|---|
| `series_disponibles` | comptes, budgets votés et projets disponibles, avec leurs totaux officiels |
| `rechercher_lignes` | recherche par mots courants, numéro de compte ou de service |
| `detail_ligne` | toute la série d'une ligne et les commentaires de la commune |
| `lister_services` / `fiche_service` | liste des services ; montants d'un service sur toutes les années |
| `totaux` | totaux d'une année par direction, groupe, service ou nature |
| `comparer` | plus fortes hausses et baisses entre deux années |
| `budget_vs_comptes` | écart entre budget voté et comptes, avec les explications de la commune |
| `amendements` | lignes modifiées par le Conseil communal entre le projet et le budget voté |

## Confidentialité et coûts

Les données restent sur votre ordinateur. Avec un modèle local, rien n'est envoyé ailleurs. Avec un service en ligne, vos questions et les extraits de données utilisés pour y répondre sont envoyés à ce service, selon ses conditions, et les éventuels coûts sont ceux de votre abonnement.

## Exemples de questions

- Combien coûte la facture sociale, et comment a-t-elle évolué depuis 2021 ?
- Quels services ont le plus augmenté entre les comptes 2024 et 2025 ?
- En 2025, les impôts encaissés ont-ils dépassé le budget ? De combien, et que dit la commune ?
- Qu'a modifié le Conseil communal dans le budget 2024 ?
- Combien coûte l'accueil de jour des enfants ?
