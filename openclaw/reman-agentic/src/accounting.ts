import { createHash } from "node:crypto";
import { basename, extname } from "node:path";
import { compact, RemanClient, RemanError } from "./client.js";
import { readAllowedPdf, resolveAllowedPdfRoots } from "./file-access.js";
import {
  acquireLock,
  createInitialState,
  loadState,
  operationFingerprint,
  prepareStateRoot,
  releaseLock,
  resolveStateRoot,
  safePersistentResponse,
  saveState,
  statePaths,
} from "./state.js";
import type { InvoiceInput, JsonObject, ToolDescriptor } from "./types.js";

export const CREATE_TOOL = "accounting.non_electronic_invoices.create";
const DEFAULT_MAX_FILES = 5;
const DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024;
const DEFAULT_MAX_TOTAL_BYTES = 100 * 1024 * 1024;

type PdfFile = { path: string; name: string; content: Buffer; sha256: string };

function positiveLimit(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : fallback;
}

async function readPdfs(
  paths: unknown,
  tool: ToolDescriptor,
  allowedPdfDirectories?: string[],
  beforeOpen?: (path: string) => Promise<void> | void,
): Promise<PdfFile[]> {
  if (!Array.isArray(paths) || paths.length === 0) throw new RemanError("reman_pdf_count_invalid");
  const policy = tool.filePolicy ?? {};
  const maxFiles = Math.min(DEFAULT_MAX_FILES, positiveLimit(policy.maxFiles, DEFAULT_MAX_FILES));
  const maxFileBytes = Math.min(DEFAULT_MAX_FILE_BYTES, positiveLimit(policy.maxFileBytes, DEFAULT_MAX_FILE_BYTES));
  const maxTotalBytes = Math.min(DEFAULT_MAX_TOTAL_BYTES, positiveLimit(policy.maxTotalBytes, DEFAULT_MAX_TOTAL_BYTES));
  if (paths.length > maxFiles) throw new RemanError("reman_pdf_count_exceeds_grant");
  const roots = await resolveAllowedPdfRoots(allowedPdfDirectories);

  const files: PdfFile[] = [];
  let total = 0;
  for (const rawPath of paths) {
    if (typeof rawPath !== "string" || !rawPath.trim()) throw new RemanError("reman_pdf_invalid_or_missing");
    if (extname(rawPath).toLowerCase() !== ".pdf") {
      throw new RemanError("reman_pdf_invalid_or_missing");
    }
    const item = await readAllowedPdf({ rawPath, roots, maxBytes: maxFileBytes, beforeOpen });
    total += item.size;
    if (total > maxTotalBytes) throw new RemanError("reman_pdf_total_exceeds_grant_limit");
    if (item.content.length !== item.size || item.content.subarray(0, 5).toString("ascii") !== "%PDF-") {
      throw new RemanError("reman_pdf_invalid_or_missing");
    }
    files.push({
      path: item.path,
      name: basename(item.path),
      content: item.content,
      sha256: createHash("sha256").update(item.content).digest("hex"),
    });
  }
  return files;
}

function invoiceBusinessInput(args: InvoiceInput): JsonObject {
  return compact({
    companyId: args.company_id,
    accountingContactId: args.accounting_contact_id,
    partnerName: args.partner_name,
    partnerTaxCode: args.partner_tax_code,
    partnerVatNumber: args.partner_vat_number,
    documentNumber: args.document_number,
    documentDate: args.document_date,
    dueDate: args.due_date,
    netAmount: args.net_amount,
    vatAmount: args.vat_amount,
    grossAmount: args.gross_amount,
    withholdingAmount: args.withholding_amount,
    description: args.description,
    notes: args.notes,
  });
}

export async function createInvoice(options: {
  client: RemanClient;
  args: InvoiceInput;
  stateDir?: string;
  allowedPdfDirectories?: string[];
  beforePdfOpen?: (path: string) => Promise<void> | void;
}): Promise<JsonObject> {
  const mode = options.args.mode ?? "draft_with_confirmation";
  if ((mode as string) === "direct") throw new RemanError("reman_direct_mode_disabled");
  if (mode !== "draft_with_confirmation") {
    throw new RemanError("reman_execution_mode_invalid");
  }

  const grantedTool = await options.client.requireTool(CREATE_TOOL, mode);
  const files = await readPdfs(
    options.args.pdf_paths,
    grantedTool,
    options.allowedPdfDirectories,
    options.beforePdfOpen,
  );
  const input = invoiceBusinessInput(options.args);
  const fingerprint = operationFingerprint({
    mode,
    input,
    files: files.map((file) => ({ name: file.name, sha256: file.sha256, size: file.content.length })),
    operationId: options.args.operation_id || null,
  });
  const root = resolveStateRoot(options.stateDir);
  await prepareStateRoot(root);
  const paths = statePaths(root, fingerprint);
  await acquireLock(paths.lock);

  try {
    const state = (await loadState(paths.state)) ?? createInitialState(fingerprint);
    if (state.status === "succeeded" && state.response) return state.response;

    if (!state.uploadSessionId) {
      const session = await options.client.createUploadSession(CREATE_TOOL);
      if (typeof session.sessionId !== "string" || !session.sessionId) {
        throw new RemanError("reman_upload_session_invalid");
      }
      state.uploadSessionId = session.sessionId;
      state.updatedAt = Date.now();
      await saveState(paths.state, state);
    }

    const uploaded = new Set(state.uploadedItems ?? []);
    for (const [index, file] of files.entries()) {
      const itemKey = `${index}:${file.sha256}`;
      if (uploaded.has(itemKey)) continue;
      await options.client.uploadPdf(state.uploadSessionId, file.name, file.content);
      uploaded.add(itemKey);
      state.uploadedItems = [...uploaded].sort();
      state.updatedAt = Date.now();
      await saveState(paths.state, state);
    }

    const response = await options.client.invoke(
      CREATE_TOOL,
      mode,
      { ...input, uploadSessionId: state.uploadSessionId },
      state.idempotencyKey,
    );
    state.status = "succeeded";
    state.response = safePersistentResponse(response);
    state.updatedAt = Date.now();
    await saveState(paths.state, state);
    return response;
  } finally {
    await releaseLock(paths.lock);
  }
}
