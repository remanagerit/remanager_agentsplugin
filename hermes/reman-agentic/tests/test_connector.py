import importlib.util
import json
import os
import sys
import tempfile
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
FILES = importlib.import_module("reman_agentic_test_plugin.file_access")
TOOLS = importlib.import_module("reman_agentic_test_plugin.tools")


class State:
    requests = []
    adversary_requests = []
    sessions = 0
    uploads = 0
    invokes = 0
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
            {"name": "accounting.non_electronic_invoices.search", "supportedModes": ["read"]},
            {"name": TOOLS.CREATE_TOOL, "supportedModes": ["draft_with_confirmation", "direct"], "filePolicy": {
                "maxFiles": 5, "maxFileBytes": 20 * 1024 * 1024, "maxTotalBytes": 100 * 1024 * 1024
            }},
        ]})

    def do_POST(self):
        payload = self._json()
        State.requests.append(("POST", self.path, payload, dict(self.headers)))
        if self.path == "/api/v1/agentic/uploads/sessions":
            State.sessions += 1
            self._send(201, {"sessionId": "e5452286-1651-4add-9373-b97c6f935237"})
        elif self.path.endswith("/items"):
            State.uploads += 1
            self._send(201, {"itemId": "item-1", "status": "ready"})
        elif self.path.endswith("/accounting.payments.search/invoke"):
            self._send(200, {"result": {"items": [{"id": 41, "amount": 120}], "nextCursor": None}})
        elif self.path.endswith("/invoke"):
            State.invokes += 1
            if State.invokes == 1:
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", "100")
                self.end_headers()
                self.wfile.write(b'{"result":')
                self.wfile.flush()
                self.close_connection = True
                return
            self._send(200, {"result": {
                "status": "pending_confirmation",
                "draftId": "93df00bb-9f49-4f31-bc6e-b7c525643170",
                "attachmentCount": 1,
                "confirmationUrl": "/amministrazione?agenticDraftId=93df00bb-9f49-4f31-bc6e-b7c525643170",
            }, "idempotentReplay": True})
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
        State.sessions = State.uploads = State.invokes = 0
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.allowed = self.root / "allowed"
        self.allowed.mkdir()
        self.pdf = self.allowed / "invoice.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        os.environ["HERMES_HOME"] = self.temp.name
        os.environ["REMAN_AGENT_BASE_URL"] = State.base_url
        os.environ["REMAN_AGENT_TOKEN"] = "secret-agent-token"
        os.environ["REMAN_AGENT_ALLOWED_PDF_DIRS"] = str(self.allowed)

    def tearDown(self):
        for key in (
            "HERMES_HOME", "REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN", "REMAN_AGENT_ALLOWED_PDF_DIRS"
        ):
            os.environ.pop(key, None)
        self.temp.cleanup()

    def invoice_args(self):
        return {
            "mode": "draft_with_confirmation", "company_id": 7, "document_number": "INV-42",
            "document_date": "2026-07-11", "net_amount": 100, "vat_amount": 22, "gross_amount": 122,
            "notes": "never persist me", "pdf_paths": [str(self.pdf)],
        }

    def assert_file_error(self, path, code, before_open=None):
        with self.assertRaises(CLIENT.RemanError) as raised:
            FILES.read_allowed_pdf(path, FILES.allowed_pdf_roots(), max_bytes=1024 * 1024, before_open=before_open)
        self.assertEqual(raised.exception.code, code)

    def test_timeout_retry_reuses_upload_session_and_key_without_secrets(self):
        first_text = TOOLS.create_invoice(self.invoice_args())
        first = json.loads(first_text)
        self.assertEqual(first["error"], "reman_transport_timeout_or_unreachable")
        second_text = TOOLS.create_invoice(self.invoice_args())
        second = json.loads(second_text)
        self.assertEqual(second["result"]["status"], "pending_confirmation")
        self.assertEqual(State.sessions, 1)
        self.assertEqual(State.uploads, 1)
        invokes = [item for item in State.requests if item[1].endswith("/invoke")]
        self.assertEqual(len(invokes), 2)
        self.assertEqual(invokes[0][2]["input"]["uploadSessionId"], invokes[1][2]["input"]["uploadSessionId"])
        first_headers = {key.lower(): value for key, value in invokes[0][3].items()}
        second_headers = {key.lower(): value for key, value in invokes[1][3].items()}
        self.assertEqual(first_headers["x-reman-idempotency-key"], second_headers["x-reman-idempotency-key"])
        state_text = "".join(path.read_text() for path in Path(self.temp.name, "reman-agentic-state").glob("*.json"))
        combined_output = first_text + second_text + state_text
        self.assertNotIn("secret-agent-token", combined_output)
        self.assertNotIn("never persist me", combined_output)
        self.assertNotIn(str(self.pdf), combined_output)
        self.assertNotIn("%PDF-", combined_output)

    def test_direct_mode_is_disabled_even_if_server_discovery_grants_it(self):
        args = self.invoice_args()
        args["mode"] = "direct"
        result = json.loads(TOOLS.create_invoice(args))
        self.assertEqual(result["error"], "reman_direct_mode_disabled")
        self.assertEqual(State.sessions, 0)
        self.assertEqual(State.uploads, 0)

    def test_discovery_hides_direct_mode(self):
        discovery = CLIENT.RemanClient().discover()
        create = next(item for item in discovery["items"] if item["name"] == TOOLS.CREATE_TOOL)
        self.assertEqual(create["supportedModes"], ["draft_with_confirmation"])

    def test_generic_accounting_read_uses_discovery_and_blocks_context_or_other_namespaces(self):
        result = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search",
            "input": {"companyId": 7, "limit": 25, "cursor": 0},
        }))
        self.assertEqual(result["result"]["items"][0]["id"], 41)
        invoke = next(item for item in State.requests if item[1].endswith("/accounting.payments.search/invoke"))
        self.assertEqual(invoke[2], {
            "mode": "read", "input": {"companyId": 7, "limit": 25, "cursor": 0}
        })

        forbidden = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search", "input": {"companyId": 7, "teamId": 99}
        }))
        self.assertEqual(forbidden["error"], "reman_agent_context_input_forbidden")
        self.assertFalse(forbidden["retryable"])
        outside = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "tasks.search", "input": {}
        }))
        self.assertEqual(outside["error"], "reman_accounting_tool_name_invalid")

    def test_error_payload_marks_only_transport_as_retryable(self):
        self.assertFalse(CLIENT.RemanError("agentic_disabled").public()["retryable"])
        self.assertFalse(CLIENT.RemanError("agentic_upload_session_unavailable").public()["retryable"])
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

    def test_pdf_root_boundary_rejects_outside_traversal_symlink_and_non_regular(self):
        path, content, _ = FILES.read_allowed_pdf(str(self.pdf), FILES.allowed_pdf_roots(), max_bytes=1024 * 1024)
        self.assertEqual(path, self.pdf.resolve())
        self.assertTrue(content.startswith(b"%PDF-"))

        outside = self.root / "outside.pdf"
        outside.write_bytes(b"%PDF-1.4\noutside\n")
        self.assert_file_error(str(outside), "reman_pdf_path_denied")
        self.assert_file_error(str(self.allowed / ".." / "outside.pdf"), "reman_pdf_path_denied")

        direct_link = self.allowed / "direct-link.pdf"
        direct_link.symlink_to(self.pdf)
        self.assert_file_error(str(direct_link), "reman_pdf_symlink_denied")

        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        (outside_dir / "escaped.pdf").write_bytes(b"%PDF-1.4\nescaped\n")
        escape_dir = self.allowed / "escape"
        escape_dir.symlink_to(outside_dir, target_is_directory=True)
        self.assert_file_error(str(escape_dir / "escaped.pdf"), "reman_pdf_symlink_denied")

        non_regular = self.allowed / "folder.pdf"
        non_regular.mkdir()
        self.assert_file_error(str(non_regular), "reman_pdf_not_regular")

    def test_pdf_change_between_validation_and_open_is_rejected(self):
        def replace(path):
            path.unlink()
            path.write_bytes(b"%PDF-1.4\nreplaced\n")

        self.assert_file_error(str(self.pdf), "reman_pdf_changed_during_read", before_open=replace)

    def test_create_tool_is_not_registered_until_quarantine_is_consumable(self):
        registered = []

        class Context:
            def register_tool(self, **definition):
                registered.append(definition)

            def register_skill(self, **definition):
                pass

        PLUGIN.register(Context())
        read = next(item for item in registered if item["name"] == "reman_available_tools")
        self.assertNotIn("reman_accounting_create_non_electronic_invoice", [item["name"] for item in registered])
        self.assertTrue(read["check_fn"]())

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
