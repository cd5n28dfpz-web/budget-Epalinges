"""Tests de l'assistant : outils, serveur MCP (protocole stdio) et script ask.py (avec une API simulée)."""
import http.server
import json
import os
import subprocess
import sys
import threading
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "assistant"))
import outils  # noqa: E402


class TestOutils(unittest.TestCase):
    def test_totaux_retombent_sur_le_total_officiel(self):
        t = outils.totaux(2025, sans_imputations=False)
        officiel = next(s for s in outils.series_disponibles()["series"] if s["serie"] == "C2025")
        self.assertAlmostEqual(sum(x["charges"] for x in t["totaux"]), officiel["charges"], delta=0.01)

    def test_recherche_mots_courants(self):
        r = outils.rechercher_lignes("piscine", limite=5)
        self.assertGreater(r["nombre"], 0)
        self.assertTrue(any(l["section"] == "3506" for l in r["lignes"]))

    def test_budget_vs_comptes(self):
        r = outils.budget_vs_comptes(2025, limite=3)
        self.assertEqual(r["total_budget"], 55529820.0)

    def test_erreur_lisible(self):
        self.assertIn("erreur", outils.appeler("totaux", {"annee": 1990}))

    def test_tous_les_schemas(self):
        for n in outils.OUTILS:
            s = outils.schema(n)
            self.assertTrue(s["description"])
            self.assertEqual(s["inputSchema"]["type"], "object")


class TestServeurMCP(unittest.TestCase):
    def test_echange_complet(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "fiche_service", "arguments": {"section": "7200"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "budget_epalinges"}},
            {"jsonrpc": "2.0", "id": 5, "method": "inconnue"},
        ]
        p = subprocess.run([sys.executable, os.path.join(RACINE, "assistant", "mcp_server.py")],
                           input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, timeout=60)
        rep = {r["id"]: r for r in map(json.loads, p.stdout.strip().splitlines())}
        self.assertEqual(set(rep), {1, 2, 3, 4, 5})
        self.assertIn("neutre", rep[1]["result"]["instructions"])
        self.assertEqual(len(rep[2]["result"]["tools"]), len(outils.OUTILS))
        fiche = json.loads(rep[3]["result"]["content"][0]["text"])
        self.assertEqual(fiche["service"]["nom"], "Prévoyance sociale")
        self.assertEqual(rep[5]["error"]["code"], -32601)


class FausseAPI(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        dernier = corps["messages"][-1]
        if dernier["role"] == "user":
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "type": "function",
                   "function": {"name": "fiche_service", "arguments": json.dumps({"section": "7200"})}}]}
        else:
            fiche = json.loads(dernier["content"])
            msg = {"role": "assistant", "content": f"Réponse : {fiche['service']['nom']}"}
        out = json.dumps({"choices": [{"message": msg}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a):
        pass


class TestAsk(unittest.TestCase):
    def test_boucle_avec_appel_d_outil(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), FausseAPI)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        env = dict(os.environ, LLM_BASE_URL=f"http://127.0.0.1:{srv.server_port}/v1", LLM_MODEL="test", NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
        p = subprocess.run([sys.executable, os.path.join(RACINE, "assistant", "ask.py"), "Combien coûte la prévoyance sociale ?"],
                           capture_output=True, text=True, timeout=60, env=env)
        srv.shutdown()
        self.assertIn("Prévoyance sociale", p.stdout, p.stderr)


if __name__ == "__main__":
    unittest.main()
