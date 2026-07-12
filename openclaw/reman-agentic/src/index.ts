import {
  definePluginEntry,
  type OpenClawPluginApi,
  type OpenClawPluginDefinition,
} from "openclaw/plugin-sdk/plugin-entry";
import { resolveConfiguredSecretInputString } from "openclaw/plugin-sdk/secret-input-runtime";
import { compact, invokeAccountingRead, RemanClient, RemanError } from "./client.js";
import {
  accountingReadSchema,
  availableToolsSchema,
  listCompaniesSchema,
  searchInvoicesSchema,
  searchPartnersSchema,
} from "./schemas.js";
import type { AccountingReadInput, JsonObject, RemanPluginConfig } from "./types.js";

function toolResult(value: JsonObject) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(value) }],
    details: value,
  };
}

function safeFailure(error: unknown): JsonObject {
  if (error instanceof RemanError) return error.publicPayload();
  if (error instanceof Error && /^reman_[a-z0-9_]+$/.test(error.message)) {
    return { error: error.message, retryable: false };
  }
  return { error: "reman_connector_internal_error", retryable: false };
}

function handler<T>(action: (params: T) => Promise<JsonObject>) {
  return async (_id: string, params: T) => {
    try {
      return toolResult(await action(params));
    } catch (error) {
      return toolResult(safeFailure(error));
    }
  };
}

async function resolveClient(api: OpenClawPluginApi): Promise<RemanClient> {
  const config = (api.pluginConfig ?? {}) as RemanPluginConfig;
  const baseUrl = config.baseUrl?.trim() || process.env.REMAN_AGENT_BASE_URL?.trim() || "";
  let token = process.env.REMAN_AGENT_TOKEN?.trim() || "";

  if (config.token !== undefined && config.token !== null) {
    const resolved = await resolveConfiguredSecretInputString({
      config: api.config as never,
      env: process.env,
      value: config.token,
      path: "plugins.entries.reman-agentic.config.token",
      unresolvedReasonStyle: "detailed",
    });
    if (resolved.unresolvedRefReason) throw new RemanError("reman_token_secret_unavailable");
    if (typeof resolved.value !== "string" || !resolved.value.trim()) {
      throw new RemanError("reman_connector_not_configured");
    }
    token = resolved.value.trim();
  }

  return new RemanClient({ baseUrl, token, timeoutSeconds: config.timeoutSeconds });
}

const plugin: OpenClawPluginDefinition = definePluginEntry({
  id: "reman-agentic",
  name: "REmanager Agentic",
  description: "Governed REmanager Accounting read tools for a user-delegated OpenClaw agent.",
  register(api) {
    api.registerTool({
      name: "reman_available_tools",
      label: "REmanager available tools",
      description:
        "List only REmanager tools and modes currently granted to this agent. Load the reman-accounting skill before Accounting workflows.",
      parameters: availableToolsSchema,
      execute: handler(async () => (await resolveClient(api)).discover()),
    });

    api.registerTool({
      name: "reman_accounting_read",
      label: "REmanager Accounting read",
      description:
        "Invoke one exact read-only accounting.* tool returned by discovery. Use the camelCase input documented in the reman-accounting skill.",
      parameters: accountingReadSchema,
      execute: handler(async (params: AccountingReadInput) => {
        const client = await resolveClient(api);
        return invokeAccountingRead(client, params.tool_name, params.input);
      }),
    });

    api.registerTool({
      name: "reman_accounting_list_companies",
      label: "REmanager companies",
      description: "List Accounting companies accessible to both the delegated REmanager user and this agent grant.",
      parameters: listCompaniesSchema,
      execute: handler(async (params: { query?: string; limit?: number }) => {
        const client = await resolveClient(api);
        return client.invoke("accounting.companies.list", "read", compact({
          query: params.query,
          limit: params.limit ?? 25,
        }));
      }),
    });

    api.registerTool({
      name: "reman_accounting_search_partners",
      label: "REmanager partner search",
      description: "Search suppliers or Accounting contacts inside one granted REmanager company.",
      parameters: searchPartnersSchema,
      execute: handler(async (params: {
        company_id: number;
        query?: string;
        vat_number?: string;
        tax_code?: string;
        limit?: number;
      }) => {
        const client = await resolveClient(api);
        return client.invoke("accounting.partners.search", "read", compact({
          companyId: params.company_id,
          query: params.query,
          vatNumber: params.vat_number,
          taxCode: params.tax_code,
          limit: params.limit ?? 25,
        }));
      }),
    });

    api.registerTool({
      name: "reman_accounting_search_non_electronic_invoices",
      label: "REmanager invoice search",
      description: "Search existing non-electronic incoming invoices in one granted company, including duplicate checks.",
      parameters: searchInvoicesSchema,
      execute: handler(async (params: {
        company_id: number;
        query?: string;
        document_number?: string;
        partner_name?: string;
        date_from?: string;
        date_to?: string;
        limit?: number;
      }) => {
        const client = await resolveClient(api);
        return client.invoke("accounting.non_electronic_invoices.search", "read", compact({
          companyId: params.company_id,
          query: params.query,
          documentNumber: params.document_number,
          partnerName: params.partner_name,
          dateFrom: params.date_from,
          dateTo: params.date_to,
          limit: params.limit ?? 25,
        }));
      }),
    });

  },
});

export default plugin;
