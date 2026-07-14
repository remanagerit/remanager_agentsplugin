import importlib.util
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reman_agentic_test_plugin",
    PLUGIN_DIR / "__init__.py",
    submodule_search_locations=[str(PLUGIN_DIR)],
)
PLUGIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PLUGIN
SPEC.loader.exec_module(PLUGIN)
CLIENT = importlib.import_module("reman_agentic_test_plugin.client")
TOOLS = importlib.import_module("reman_agentic_test_plugin.tools")


class State:
    requests = []
    adversary_requests = []
    base_url = ""
    adversary_url = ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self):
        length = int(self.headers.get("content-length", "0"))
        return json.loads(self.rfile.read(length)) if length else None

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("location", location)
        self.end_headers()

    def do_GET(self):
        State.requests.append(("GET", self.path, None, dict(self.headers)))
        if self.path.startswith("/redirect-same/"):
            self._redirect(State.base_url + "/api/v1/agentic/tools")
            return
        if self.path.startswith("/redirect-cross/"):
            self._redirect(State.adversary_url + "/collect")
            return
        self._send(200, {"grantVersion": 3, "items": [
            {"name": "accounting.companies.list", "supportedModes": ["read"]},
            {"name": "accounting.partners.search", "supportedModes": ["read"]},
            {"name": "accounting.payments.search", "supportedModes": ["read"]},
            {"name": "accounting.documents.search", "supportedModes": ["read"]},
            {"name": "accounting.non_electronic_invoices.search", "supportedModes": ["read"]},
            {"name": "accounting.non_electronic_invoices.create", "supportedModes": ["read", "draft_with_confirmation", "direct"]},
            {"name": "accounting.settings.update", "supportedModes": ["direct"]},
            {"name": "tasks.search", "supportedModes": ["read"]},
        ]})

    def do_POST(self):
        payload = self._json()
        State.requests.append(("POST", self.path, payload, dict(self.headers)))
        if self.path.endswith("/accounting.payments.search/invoke"):
            self._send(200, {"result": {"items": [{"id": 41, "amount": 120}], "nextCursor": None}})
        elif self.path.endswith("/accounting.documents.search/invoke"):
            adversarial = payload.get("input", {}).get("adversarial")
            if adversarial == "error":
                self._send(500, {
                    "error": "agentic_disabled\n/private/tmp/customer.pdf secret-agent-token payload={sensitive}",
                    "requestId": "req-valid\n/private/tmp/secret-agent-token",
                    "message": "payload={customer-data}",
                    "debug": {"path": "/private/tmp/customer.pdf", "token": "secret-agent-token"},
                })
            elif adversarial == "request_id":
                self._send(503, {
                    "error": "agentic_disabled",
                    "requestId": "req-valid\n/private/tmp/secret-agent-token payload={customer-data}",
                })
            else:
                self._send(503, {"error": "agentic_disabled", "requestId": "req-policy-1"})
        else:
            self._send(404, {"error": "not_found"})


class AdversaryHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        State.adversary_requests.append((self.path, dict(self.headers)))
        self.send_response(200)
        self.end_headers()


class ConnectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adversary = ThreadingHTTPServer(("127.0.0.1", 0), AdversaryHandler)
        cls.adversary_thread = threading.Thread(target=cls.adversary.serve_forever, daemon=True)
        cls.adversary_thread.start()
        State.adversary_url = "http://127.0.0.1:{}".format(cls.adversary.server_port)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        State.base_url = "http://127.0.0.1:{}".format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        cls.adversary.shutdown()
        cls.adversary_thread.join()
        cls.adversary.server_close()

    def setUp(self):
        State.requests = []
        State.adversary_requests = []
        os.environ["REMAN_AGENT_BASE_URL"] = State.base_url
        os.environ["REMAN_AGENT_TOKEN"] = "secret-agent-token"

    def tearDown(self):
        os.environ.pop("REMAN_AGENT_BASE_URL", None)
        os.environ.pop("REMAN_AGENT_TOKEN", None)

    def test_discovery_exposes_only_accounting_read_tools(self):
        discovery = CLIENT.RemanClient().discover()
        self.assertEqual([item["name"] for item in discovery["items"]], [
            "accounting.companies.list",
            "accounting.partners.search",
            "accounting.payments.search",
            "accounting.documents.search",
            "accounting.non_electronic_invoices.search",
        ])
        self.assertTrue(all(item["supportedModes"] == ["read"] for item in discovery["items"]))

    def test_discovery_output_does_not_contain_token(self):
        output = TOOLS.available_tools({})
        self.assertNotIn("secret-agent-token", output)
        self.assertNotIn("non_electronic_invoices.create", output)
        self.assertNotIn("tasks.search", output)

    def test_generic_accounting_read_uses_discovery_and_forces_read(self):
        result = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search",
            "input": {"companyId": 7, "limit": 25, "cursor": 0},
        }))
        self.assertEqual(result["result"]["items"][0]["id"], 41)
        invoke = next(item for item in State.requests if item[1].endswith("/accounting.payments.search/invoke"))
        self.assertEqual(invoke[2], {"mode": "read", "input": {"companyId": 7, "limit": 25, "cursor": 0}})

    def test_generic_read_blocks_context_other_namespaces_and_large_input(self):
        forbidden = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search", "input": {"companyId": 7, "filter": {"teamId": 99}}
        }))
        self.assertEqual(forbidden["error"], "reman_agent_context_input_forbidden")
        outside = json.loads(TOOLS.invoke_accounting_read({"tool_name": "tasks.search", "input": {}}))
        self.assertEqual(outside["error"], "reman_accounting_tool_name_invalid")
        oversized = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search", "input": {"query": "x" * (33 * 1024)}
        }))
        self.assertEqual(oversized["error"], "reman_accounting_input_too_large")

    def test_tool_not_returned_by_discovery_is_denied_before_invoke(self):
        result = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.unknown.search", "input": {"companyId": 7}
        }))
        self.assertEqual(result["error"], "reman_tool_not_granted_or_unavailable")
        self.assertFalse(any(item[0] == "POST" for item in State.requests))

    def test_policy_error_is_non_retryable_and_redacted(self):
        output = TOOLS.invoke_accounting_read({
            "tool_name": "accounting.documents.search", "input": {"companyId": 7}
        })
        result = json.loads(output)
        self.assertEqual(result, {"error": "agentic_disabled", "retryable": False, "status": 503})
        self.assertNotIn("secret-agent-token", output)

    def test_adversarial_http_error_payload_is_not_reflected(self):
        output = TOOLS.invoke_accounting_read({
            "tool_name": "accounting.documents.search",
            "input": {"companyId": 7, "adversarial": "error"},
        })
        self.assertEqual(json.loads(output), {
            "error": "reman_http_error", "retryable": False, "status": 500
        })
        for forbidden in (
            "/private/tmp/customer.pdf",
            "secret-agent-token",
            "payload={sensitive}",
            "payload={customer-data}",
            "requestId",
            "\\n",
            "\n",
        ):
            self.assertNotIn(forbidden, output)

        request_id_output = TOOLS.invoke_accounting_read({
            "tool_name": "accounting.documents.search",
            "input": {"companyId": 7, "adversarial": "request_id"},
        })
        self.assertEqual(json.loads(request_id_output), {
            "error": "agentic_disabled", "retryable": False, "status": 503
        })
        self.assertNotIn("requestId", request_id_output)
        self.assertNotIn("secret-agent-token", request_id_output)
        self.assertNotIn("/private/tmp", request_id_output)
        self.assertNotIn("payload={customer-data}", request_id_output)

        reflected = CLIENT.RemanError(CLIENT._normalize_remote_error_code("agentic_secret_agent_token_payload"), 500)
        self.assertEqual(reflected.public()["error"], "reman_http_error")

    def test_only_transport_errors_are_retryable(self):
        self.assertFalse(CLIENT.RemanError("agentic_disabled").public()["retryable"])
        self.assertFalse(CLIENT.RemanError("agentic_direct_disabled").public()["retryable"])
        self.assertTrue(CLIENT.RemanTransportError("reman_transport_timeout_or_unreachable").public()["retryable"])

    def test_redirects_are_denied_without_forwarding_token(self):
        for route in ("redirect-same", "redirect-cross"):
            client = CLIENT.RemanClient(base_url=State.base_url + "/" + route, token="redirect-secret")
            with self.assertRaises(CLIENT.RemanError) as raised:
                client.discover()
            self.assertEqual(raised.exception.code, "reman_redirect_denied")
        self.assertEqual(State.adversary_requests, [])
        self.assertEqual([item[1] for item in State.requests], [
            "/redirect-same/api/v1/agentic/tools", "/redirect-cross/api/v1/agentic/tools"
        ])

    def test_runtime_has_no_create_upload_or_direct_surface(self):
        self.assertFalse(hasattr(CLIENT.RemanClient, "create_upload_session"))
        self.assertFalse(hasattr(CLIENT.RemanClient, "upload_pdf"))
        self.assertFalse(hasattr(TOOLS, "create_invoice"))
        self.assertFalse(hasattr(PLUGIN.schemas, "CREATE_INVOICE"))
        with self.assertRaises(CLIENT.RemanError) as raised:
            CLIENT.RemanClient().invoke("accounting.non_electronic_invoices.create", "direct", {})
        self.assertEqual(raised.exception.code, "reman_read_only_connector")

    def test_remote_plain_http_is_rejected(self):
        with self.assertRaises(CLIENT.RemanError) as raised:
            CLIENT.RemanClient(base_url="http://example.com", token="token")
        self.assertEqual(raised.exception.code, "reman_https_required")

    def test_plugin_registers_declared_tools_and_skill(self):
        registered = []
        skills = []

        class Context:
            def register_tool(self, **definition):
                registered.append(definition["name"])

            def register_skill(self, **definition):
                skills.append(definition)

        PLUGIN.register(Context())
        self.assertEqual(set(registered), set(PLUGIN.schemas.__dict__[name]["name"] for name in (
            "AVAILABLE_TOOLS", "INVOKE_ACCOUNTING_READ", "LIST_COMPANIES", "SEARCH_PARTNERS", "SEARCH_INVOICES"
        )))
        self.assertEqual([item["name"] for item in skills], ["reman-accounting"])
        self.assertTrue(skills[0]["path"].is_file())


if __name__ == "__main__":
    unittest.main()
