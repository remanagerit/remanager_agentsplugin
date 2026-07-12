import { createHash, randomUUID } from "node:crypto";
import { chmod, mkdir, open, readFile, rename, rmdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { homedir } from "node:os";
import type { JsonObject } from "./types.js";
import { RemanError } from "./client.js";

const STATE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type OperationState = {
  idempotencyKey: string;
  uploadSessionId?: string;
  uploadedItems?: string[];
  status?: "succeeded";
  response?: JsonObject;
  updatedAt: number;
};

export function resolveStateRoot(configured?: string): string {
  return configured?.trim() || join(process.env.OPENCLAW_STATE_DIR || join(homedir(), ".openclaw"), "reman-agentic-state");
}

export async function prepareStateRoot(root: string): Promise<void> {
  await mkdir(root, { recursive: true, mode: 0o700 });
  await chmod(root, 0o700).catch(() => undefined);
}

export function operationFingerprint(value: JsonObject): string {
  return createHash("sha256").update(stableJson(value)).digest("hex");
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as JsonObject)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function statePaths(root: string, fingerprint: string): { state: string; lock: string } {
  return {
    state: join(root, `${fingerprint}.json`),
    lock: join(root, `${fingerprint}.lock`),
  };
}

export async function acquireLock(path: string): Promise<void> {
  try {
    await mkdir(path, { mode: 0o700 });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "EEXIST") {
      throw new RemanError("reman_operation_already_in_progress");
    }
    throw error;
  }
}

export async function releaseLock(path: string): Promise<void> {
  await rmdir(path).catch(() => undefined);
}

export async function loadState(path: string): Promise<OperationState | undefined> {
  try {
    const parsed = JSON.parse(await readFile(path, "utf8")) as OperationState;
    if (Date.now() - parsed.updatedAt <= STATE_TTL_MS && typeof parsed.idempotencyKey === "string") {
      return parsed;
    }
  } catch {
    // Missing, expired, or malformed state starts a new idempotent operation.
  }
  return undefined;
}

export async function saveState(path: string, value: OperationState): Promise<void> {
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  const temporary = `${path}.${randomUUID()}.tmp`;
  const handle = await open(temporary, "wx", 0o600);
  try {
    await handle.writeFile(JSON.stringify(value));
    await handle.sync();
  } finally {
    await handle.close();
  }
  await rename(temporary, path);
  await chmod(path, 0o600).catch(() => undefined);
}

export function createInitialState(fingerprint: string): OperationState {
  return {
    idempotencyKey: `openclaw-reman-${fingerprint}`,
    uploadedItems: [],
    updatedAt: Date.now(),
  };
}

export function safePersistentResponse(response: JsonObject): JsonObject {
  const source = response.result && typeof response.result === "object" && !Array.isArray(response.result)
    ? (response.result as JsonObject)
    : {};
  const result = Object.fromEntries(
    [
      "status",
      "entryId",
      "draftId",
      "companyId",
      "attachmentIds",
      "attachmentCount",
      "documentNumber",
      "documentDate",
      "warnings",
      "createdVia",
      "expiresAt",
      "confirmationUrl",
    ]
      .filter((key) => source[key] !== undefined)
      .map((key) => [key, source[key]]),
  );
  return Object.fromEntries(
    Object.entries({
      result,
      idempotentReplay: response.idempotentReplay,
      requestId: response.requestId,
    }).filter(([, value]) => value !== undefined),
  );
}
