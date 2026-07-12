import assert from "node:assert/strict";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, beforeEach, test } from "node:test";
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, symlink, writeFile } from "node:fs/promises";
import plugin from "../src/index.js";
import { CREATE_TOOL, createInvoice } from "../src/accounting.js";
import { invokeAccountingRead, RemanClient, RemanError, RemanTransportError } from "../src/client.js";
import { readAllowedPdf, resolveAllowedPdfRoots } from "../src/file-access.js";
import type { InvoiceInput } from "../src/types.js";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let server = createServer();
let adversary = createServer();
let baseUrl = "";
let adversaryUrl = "";
const temporaryRoots: string[] = [];

const state = {
  requests: [] as Array<{ path: string; body?: Record<string, unknown>; headers: IncomingMessage["headers"] }>,
  adversaryRequests: [] as Array<{ path: string; headers: IncomingMessage["headers"] }>,
  sessions: 0,
  uploads: 0,
  invokes: 0,
};

async function body(request: IncomingMessage): Promise<Record<string, unknown> | undefined> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(Buffer.from(chunk));
  return chunks.length ? (JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>) : undefined;
}

function send(response: ServerResponse, status: number, payload: Record<string, unknown>): void {
  const encoded = Buffer.from(JSON.stringify(payload));
  response.writeHead(status, { "content-type": "application/json", "content-length": encoded.length });
  response.end(encoded);
}

before(async () => {
  adversary = createServer((request, response) => {
    state.adversaryRequests.push({ path: request.url ?? "", headers: request.headers });
    send(response, 200, { received: true });
  });
  await new Promise<void>((resolveListen) => adversary.listen(0, "127.0.0.1", resolveListen));
  const adversaryAddress = adversary.address();
  if (!adversaryAddress || typeof adversaryAddress === "string") throw new Error("adversary_address_invalid");
  adversaryUrl = `http://127.0.0.1:${adversaryAddress.port}`;

  server = createServer(async (request, response) => {
    const payload = await body(request);
    state.requests.push({ path: request.url ?? "", body: payload, headers: request.headers });
    if (request.url?.startsWith("/redirect-same/")) {
      response.writeHead(302, { location: `${baseUrl}/api/v1/agentic/tools` });
      response.end();
      return;
    }
    if (request.url?.startsWith("/redirect-cross/")) {
      response.writeHead(302, { location: `${adversaryUrl}/collect` });
      response.end();
      return;
    }
    if (request.method === "GET" && request.url === "/api/v1/agentic/tools") {
      send(response, 200, {
        grantVersion: 3,
        items: [
          { name: "accounting.companies.list", supportedModes: ["read"] },
          { name: "accounting.partners.search", supportedModes: ["read"] },
          { name: "accounting.payments.search", supportedModes: ["read"] },
          { name: "accounting.non_electronic_invoices.search", supportedModes: ["read"] },
          {
            name: CREATE_TOOL,
            supportedModes: ["draft_with_confirmation", "direct"],
            filePolicy: {
              maxFiles: 5,
              maxFileBytes: 20 * 1024 * 1024,
              maxTotalBytes: 100 * 1024 * 1024,
            },
          },
        ],
      });
      return;
    }
    if (request.method === "POST" && request.url === "/api/v1/agentic/uploads/sessions") {
      state.sessions += 1;
      send(response, 201, { sessionId: "e5452286-1651-4add-9373-b97c6f935237" });
      return;
    }
    if (request.method === "POST" && request.url?.endsWith("/items")) {
      state.uploads += 1;
      send(response, 201, { itemId: "item-1", status: "ready" });
      return;
    }
    if (request.method === "POST" && request.url?.endsWith("/accounting.payments.search/invoke")) {
      send(response, 200, { result: { items: [{ id: 41, amount: 120 }], nextCursor: null } });
      return;
    }
    if (request.method === "POST" && request.url?.endsWith("/invoke")) {
      state.invokes += 1;
      if (state.invokes === 1) {
        request.socket.destroy();
        return;
      }
      send(response, 200, {
        result: {
          status: "pending_confirmation",
          draftId: "93df00bb-9f49-4f31-bc6e-b7c525643170",
          companyId: 7,
          attachmentCount: 1,
          confirmationUrl: "/amministrazione?agenticDraftId=93df00bb-9f49-4f31-bc6e-b7c525643170",
        },
        idempotentReplay: true,
      });
      return;
    }
    send(response, 404, { error: "not_found" });
  });
  await new Promise<void>((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("test_server_address_invalid");
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  await new Promise<void>((resolveClose, reject) => server.close((error) => (error ? reject(error) : resolveClose())));
  await new Promise<void>((resolveClose, reject) => adversary.close((error) => (error ? reject(error) : resolveClose())));
  await Promise.all(temporaryRoots.map((root) => rm(root, { recursive: true, force: true })));
});

beforeEach(() => {
  state.requests = [];
  state.adversaryRequests = [];
  state.sessions = 0;
  state.uploads = 0;
  state.invokes = 0;
  delete process.env.REMAN_AGENT_ALLOWED_PDF_DIRS;
});

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "reman-openclaw-test-"));
  temporaryRoots.push(root);
  const allowed = join(root, "allowed");
  await mkdir(allowed);
  const pdf = join(allowed, "invoice.pdf");
  await writeFile(pdf, "%PDF-1.4\n%%EOF\n");
  return { root, allowed, pdf };
}

function invoiceArgs(pdf: string): InvoiceInput {
  return {
    mode: "draft_with_confirmation",
    company_id: 7,
    document_number: "INV-42",
    document_date: "2026-07-11",
    net_amount: 100,
    vat_amount: 22,
    gross_amount: 122,
    notes: "never persist me",
    pdf_paths: [pdf],
  };
}

function isRemanCode(code: string) {
  return (error: unknown) => error instanceof RemanError && error.code === code;
}

test("lost response retry reuses upload state without persisting secrets, notes, PDF, or paths", async () => {
  const { root, allowed, pdf } = await fixture();
  const client = new RemanClient({ baseUrl, token: "secret-agent-token", timeoutSeconds: 5 });
  const args = invoiceArgs(pdf);
  await assert.rejects(
    () => createInvoice({ client, args, stateDir: join(root, "state"), allowedPdfDirectories: [allowed] }),
    isRemanCode("reman_transport_timeout_or_unreachable"),
  );
  const result = await createInvoice({
    client,
    args,
    stateDir: join(root, "state"),
    allowedPdfDirectories: [allowed],
  });
  assert.equal((result.result as Record<string, unknown>).status, "pending_confirmation");
  assert.equal(state.sessions, 1);
  assert.equal(state.uploads, 1);
  assert.equal(state.invokes, 2);

  const invokes = state.requests.filter((request) => request.path.endsWith("/invoke"));
  assert.equal(invokes[0]?.headers["x-reman-idempotency-key"], invokes[1]?.headers["x-reman-idempotency-key"]);
  assert.equal(
    (invokes[0]?.body?.input as Record<string, unknown>).uploadSessionId,
    (invokes[1]?.body?.input as Record<string, unknown>).uploadSessionId,
  );
  const files = await readdir(join(root, "state"));
  const persisted = (
    await Promise.all(files.filter((name) => name.endsWith(".json")).map((name) => readFile(join(root, "state", name), "utf8")))
  ).join("");
  const output = JSON.stringify(result) + persisted;
  assert.doesNotMatch(output, /secret-agent-token|never persist me|%PDF-/);
  assert.equal(output.includes(pdf), false);
});

test("direct mode is disabled even when discovery advertises it", async () => {
  const { root, allowed, pdf } = await fixture();
  const client = new RemanClient({ baseUrl, token: "token" });
  const args = { ...invoiceArgs(pdf), mode: "direct" } as unknown as InvoiceInput;
  await assert.rejects(
    () => createInvoice({ client, args, stateDir: join(root, "state"), allowedPdfDirectories: [allowed] }),
    isRemanCode("reman_direct_mode_disabled"),
  );
  assert.equal(state.sessions, 0);
  assert.equal(state.uploads, 0);
});

test("discovery hides direct mode", async () => {
  const discovery = await new RemanClient({ baseUrl, token: "token" }).discover();
  const create = (discovery.items as Array<Record<string, unknown>>).find((item) => item.name === CREATE_TOOL);
  assert.deepEqual(create?.supportedModes, ["draft_with_confirmation"]);
});

test("generic Accounting read uses discovery and blocks context or other namespaces", async () => {
  const client = new RemanClient({ baseUrl, token: "token" });
  const result = await invokeAccountingRead(client, "accounting.payments.search", {
    companyId: 7,
    limit: 25,
    cursor: 0,
  });
  assert.equal((((result.result as Record<string, unknown>).items as Array<Record<string, unknown>>)[0]?.id), 41);
  const invoke = state.requests.find((request) => request.path.endsWith("/accounting.payments.search/invoke"));
  assert.deepEqual(invoke?.body, {
    mode: "read",
    input: { companyId: 7, limit: 25, cursor: 0 },
  });

  await assert.rejects(
    () => invokeAccountingRead(client, "accounting.payments.search", { companyId: 7, teamId: 99 }),
    isRemanCode("reman_agent_context_input_forbidden"),
  );
  await assert.rejects(
    () => invokeAccountingRead(client, "tasks.search", {}),
    isRemanCode("reman_accounting_tool_name_invalid"),
  );
});

test("error payload marks only transport as retryable", () => {
  assert.equal(new RemanError("agentic_disabled").publicPayload().retryable, false);
  assert.equal(new RemanError("agentic_upload_session_unavailable").publicPayload().retryable, false);
  assert.equal(new RemanTransportError("reman_transport_timeout_or_unreachable").publicPayload().retryable, true);
});

test("same-origin and cross-origin redirects are denied without forwarding the token", async () => {
  for (const route of ["redirect-same", "redirect-cross"]) {
    const client = new RemanClient({ baseUrl: `${baseUrl}/${route}`, token: "redirect-secret" });
    await assert.rejects(() => client.discover(), isRemanCode("reman_redirect_denied"));
  }
  assert.deepEqual(state.adversaryRequests, []);
  assert.deepEqual(state.requests.map((request) => request.path), [
    "/redirect-same/api/v1/agentic/tools",
    "/redirect-cross/api/v1/agentic/tools",
  ]);
});

test("PDF roots reject outside paths, traversal, symlinks, and non-regular files", async () => {
  const { root, allowed, pdf } = await fixture();
  const roots = await resolveAllowedPdfRoots([allowed]);
  const valid = await readAllowedPdf({ rawPath: pdf, roots, maxBytes: 1024 * 1024 });
  assert.equal(valid.path, await realpath(pdf));
  assert.equal(valid.content.subarray(0, 5).toString("ascii"), "%PDF-");

  const outside = join(root, "outside.pdf");
  await writeFile(outside, "%PDF-1.4\noutside\n");
  await assert.rejects(() => readAllowedPdf({ rawPath: outside, roots }), isRemanCode("reman_pdf_path_denied"));
  await assert.rejects(
    () => readAllowedPdf({ rawPath: `${allowed}/../outside.pdf`, roots }),
    isRemanCode("reman_pdf_path_denied"),
  );

  const directLink = join(allowed, "direct-link.pdf");
  await symlink(pdf, directLink);
  await assert.rejects(() => readAllowedPdf({ rawPath: directLink, roots }), isRemanCode("reman_pdf_symlink_denied"));

  const outsideDir = join(root, "outside-dir");
  await mkdir(outsideDir);
  await writeFile(join(outsideDir, "escaped.pdf"), "%PDF-1.4\nescaped\n");
  const escapeDir = join(allowed, "escape");
  await symlink(outsideDir, escapeDir, "dir");
  await assert.rejects(
    () => readAllowedPdf({ rawPath: join(escapeDir, "escaped.pdf"), roots }),
    isRemanCode("reman_pdf_symlink_denied"),
  );

  const nonRegular = join(allowed, "folder.pdf");
  await mkdir(nonRegular);
  await assert.rejects(() => readAllowedPdf({ rawPath: nonRegular, roots }), isRemanCode("reman_pdf_not_regular"));
});

test("PDF replacement between validation and open is rejected", async () => {
  const { allowed, pdf } = await fixture();
  const roots = await resolveAllowedPdfRoots([allowed]);
  await assert.rejects(
    () => readAllowedPdf({
      rawPath: pdf,
      roots,
      beforeOpen: async (path) => {
        await rm(path);
        await writeFile(path, "%PDF-1.4\nreplaced\n");
      },
    }),
    isRemanCode("reman_pdf_changed_during_read"),
  );
});

test("create tool is not registered until quarantine is consumable", () => {
  const registrations: Array<{
    tool: { name: string } | (() => { name: string } | null);
    options?: { name?: string; optional?: boolean };
  }> = [];
  plugin.register({
    registerTool(tool: { name: string } | (() => { name: string } | null), options?: { name?: string; optional?: boolean }) {
      registrations.push({ tool, options });
    },
    pluginConfig: {},
    config: {},
  } as never);
  const names = registrations.map((item) => typeof item.tool === "function" ? item.options?.name : item.tool.name);
  assert.equal(names.includes("reman_accounting_create_non_electronic_invoice"), false);
});

test("plugin registers exactly manifest tools and keeps create absent with PDF roots", async () => {
  const { allowed } = await fixture();
  const registrations: Array<{
    tool: { name: string } | (() => { name: string } | null);
    options?: { name?: string; optional?: boolean };
  }> = [];
  plugin.register({
    registerTool(tool: { name: string } | (() => { name: string } | null), options?: { name?: string; optional?: boolean }) {
      registrations.push({ tool, options });
    },
    pluginConfig: { allowedPdfDirectories: [allowed] },
    config: {},
  } as never);
  const names = registrations.map((item) => typeof item.tool === "function" ? item.options?.name : item.tool.name);
  const manifest = JSON.parse(await readFile(join(packageRoot, "openclaw.plugin.json"), "utf8")) as {
    contracts: { tools: string[] };
  };
  assert.deepEqual(names.sort(), [...manifest.contracts.tools].sort());
  assert.equal(names.includes("reman_accounting_create_non_electronic_invoice"), false);
});

test("remote plain HTTP is rejected", () => {
  assert.throws(() => new RemanClient({ baseUrl: "http://example.com", token: "token" }), isRemanCode("reman_https_required"));
});

test("Hermes and OpenClaw ship the same Accounting skill", async () => {
  const openClawSkill = await readFile(join(packageRoot, "skills", "reman-accounting", "SKILL.md"), "utf8");
  const hermesSkill = await readFile(
    resolve(packageRoot, "..", "..", "hermes", "reman-agentic", "skills", "reman-accounting", "SKILL.md"),
    "utf8",
  );
  assert.equal(openClawSkill, hermesSkill);
});
