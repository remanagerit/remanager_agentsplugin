import type { JsonObject, ToolDescriptor } from "./types.js";

export class RemanError extends Error {
  constructor(
    public readonly code: string,
    public readonly status?: number,
    public readonly requestId?: string,
    public readonly retryable = false,
  ) {
    super(code);
    this.name = "RemanError";
  }

  publicPayload(): JsonObject {
    return compact({ error: this.code, status: this.status, requestId: this.requestId, retryable: this.retryable });
  }
}

export class RemanTransportError extends RemanError {
  constructor(code: string) {
    super(code, undefined, undefined, true);
  }
}

export function compact<T extends JsonObject>(value: T): T {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ""),
  ) as T;
}

export class RemanClient {
  readonly baseUrl: string;
  readonly token: string;
  readonly timeoutMs: number;

  constructor(options: { baseUrl: string; token: string; timeoutSeconds?: number }) {
    this.baseUrl = options.baseUrl.trim().replace(/\/+$/, "");
    this.token = options.token.trim();
    this.timeoutMs = Math.max(5, Math.min(120, options.timeoutSeconds ?? 30)) * 1000;
    this.validateConfiguration();
  }

  private validateConfiguration(): void {
    if (!this.baseUrl || !this.token) throw new RemanError("reman_connector_not_configured");
    let parsed: URL;
    try {
      parsed = new URL(this.baseUrl);
    } catch {
      throw new RemanError("reman_base_url_invalid");
    }
    if (parsed.username || parsed.password || parsed.search || parsed.hash || !parsed.hostname) {
      throw new RemanError("reman_base_url_invalid");
    }
    const local = new Set(["localhost", "127.0.0.1", "::1"]).has(parsed.hostname);
    if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && local)) {
      throw new RemanError("reman_https_required");
    }
  }

  private async request(
    method: string,
    path: string,
    payload?: JsonObject,
    idempotencyKey?: string,
  ): Promise<JsonObject> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "User-Agent": "OpenClaw-REmanager-Agentic/1.0",
      "X-REman-Agent-Token": this.token,
    };
    let body: string | undefined;
    if (payload !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(payload);
    }
    if (idempotencyKey) headers["X-REman-Idempotency-Key"] = idempotencyKey;

    let response: Response;
    try {
      response = await fetch(this.baseUrl + path, {
        method,
        headers,
        body,
        redirect: "manual",
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch {
      throw new RemanTransportError("reman_transport_timeout_or_unreachable");
    }

    if (response.status >= 300 && response.status < 400) {
      throw new RemanError("reman_redirect_denied", response.status);
    }

    let parsed: JsonObject = {};
    const text = await response.text();
    if (text) {
      try {
        parsed = JSON.parse(text) as JsonObject;
      } catch {
        throw new RemanError("reman_response_invalid", response.status);
      }
    }
    if (!response.ok) {
      throw new RemanError(
        typeof parsed.error === "string" ? parsed.error : "reman_http_error",
        response.status,
        typeof parsed.requestId === "string" ? parsed.requestId : undefined,
      );
    }
    return parsed;
  }

  async discover(): Promise<JsonObject> {
    const discovery = await this.request("GET", "/api/v1/agentic/tools");
    const items = Array.isArray(discovery.items) ? discovery.items : [];
    return {
      ...discovery,
      items: items
        .filter((item): item is JsonObject => Boolean(item) && typeof item === "object" && !Array.isArray(item))
        .map((item) => ({
          ...item,
          supportedModes: Array.isArray(item.supportedModes)
            ? item.supportedModes.filter((mode) => mode !== "direct")
            : [],
        })),
    };
  }

  async requireTool(toolName: string, mode: string): Promise<ToolDescriptor> {
    const discovery = await this.discover();
    const items = Array.isArray(discovery.items) ? (discovery.items as ToolDescriptor[]) : [];
    const tool = items.find((item) => item.name === toolName);
    if (!tool) throw new RemanError("reman_tool_not_granted_or_unavailable");
    if (!Array.isArray(tool.supportedModes) || !tool.supportedModes.includes(mode)) {
      throw new RemanError("reman_tool_mode_not_granted");
    }
    return tool;
  }

  async invoke(
    toolName: string,
    mode: string,
    input: JsonObject,
    idempotencyKey?: string,
  ): Promise<JsonObject> {
    await this.requireTool(toolName, mode);
    return this.request(
      "POST",
      `/api/v1/agentic/tools/${encodeURIComponent(toolName)}/invoke`,
      { mode, input },
      idempotencyKey,
    );
  }

  createUploadSession(toolName: string): Promise<JsonObject> {
    return this.request("POST", "/api/v1/agentic/uploads/sessions", { toolName });
  }

  uploadPdf(sessionId: string, fileName: string, content: Buffer): Promise<JsonObject> {
    return this.request(
      "POST",
      `/api/v1/agentic/uploads/sessions/${encodeURIComponent(sessionId)}/items`,
      {
        fileName,
        mimeType: "application/pdf",
        contentBase64: content.toString("base64"),
      },
    );
  }
}

const ACCOUNTING_READ_TOOL = /^accounting\.[a-z0-9_.]+$/;
const RESERVED_AGENT_INPUT_KEYS = new Set([
  "agentId", "delegatingUserId", "executionMode", "grantVersion", "isExternalAgent",
  "isSystemAdmin", "mode", "scopes", "teamId", "userId",
]);

export async function invokeAccountingRead(
  client: RemanClient,
  toolName: string,
  input: JsonObject,
): Promise<JsonObject> {
  if (!ACCOUNTING_READ_TOOL.test(toolName)) throw new RemanError("reman_accounting_tool_name_invalid");
  if (!input || typeof input !== "object" || Array.isArray(input) || Object.keys(input).length > 32) {
    throw new RemanError("reman_accounting_input_invalid");
  }
  if (Object.keys(input).some((key) => RESERVED_AGENT_INPUT_KEYS.has(key))) {
    throw new RemanError("reman_agent_context_input_forbidden");
  }
  if (Buffer.byteLength(JSON.stringify(input), "utf8") > 32 * 1024) {
    throw new RemanError("reman_accounting_input_too_large");
  }
  return client.invoke(toolName, "read", input);
}
