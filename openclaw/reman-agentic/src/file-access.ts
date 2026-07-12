import { constants } from "node:fs";
import { lstat, open, realpath, stat } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep, delimiter } from "node:path";
import { RemanError } from "./client.js";

export type AllowedPdfRoot = { declared: string; canonical: string };

export function configuredPdfDirectoryValues(configured?: string[]): string[] {
  const source = configured?.length
    ? configured
    : (process.env.REMAN_AGENT_ALLOWED_PDF_DIRS ?? "").split(delimiter);
  return [...new Set(source.map((value) => value.trim()).filter(Boolean))];
}

export function hasConfiguredPdfDirectories(configured?: string[]): boolean {
  return configuredPdfDirectoryValues(configured).length > 0;
}

export async function resolveAllowedPdfRoots(configured?: string[]): Promise<AllowedPdfRoot[]> {
  const values = configuredPdfDirectoryValues(configured);
  if (!values.length) throw new RemanError("reman_pdf_roots_not_configured");
  const roots: AllowedPdfRoot[] = [];
  for (const value of values) {
    if (!isAbsolute(value)) throw new RemanError("reman_pdf_root_invalid");
    const declared = resolve(value);
    let canonical: string;
    try {
      canonical = await realpath(declared);
      if (!(await stat(canonical)).isDirectory()) throw new Error("not_directory");
    } catch {
      throw new RemanError("reman_pdf_root_invalid");
    }
    if (!roots.some((root) => root.declared === declared && root.canonical === canonical)) {
      roots.push({ declared, canonical });
    }
  }
  return roots;
}

function locateUnderRoot(rawPath: string, roots: AllowedPdfRoot[]): { path: string; root: string; parts: string[] } {
  if (!isAbsolute(rawPath) || rawPath.split(/[\\/]+/u).includes("..")) {
    throw new RemanError("reman_pdf_path_denied");
  }
  const lexical = resolve(rawPath);
  for (const allowed of roots) {
    for (const base of [allowed.declared, allowed.canonical]) {
      const child = relative(base, lexical);
      if (child && !child.startsWith(`..${sep}`) && child !== ".." && !isAbsolute(child)) {
        return { path: resolve(allowed.canonical, child), root: allowed.canonical, parts: child.split(sep) };
      }
    }
  }
  throw new RemanError("reman_pdf_path_denied");
}

function sameFile(left: Awaited<ReturnType<typeof lstat>>, right: Awaited<ReturnType<typeof lstat>>): boolean {
  return left.dev === right.dev
    && left.ino === right.ino
    && left.size === right.size
    && left.mtimeMs === right.mtimeMs
    && left.ctimeMs === right.ctimeMs;
}

export async function readAllowedPdf(options: {
  rawPath: string;
  roots: AllowedPdfRoot[];
  maxBytes?: number;
  beforeOpen?: (path: string) => Promise<void> | void;
}): Promise<{ path: string; content: Buffer; size: number }> {
  const located = locateUnderRoot(options.rawPath, options.roots);
  let current = located.root;
  let before: Awaited<ReturnType<typeof lstat>> | undefined;
  for (const [index, part] of located.parts.entries()) {
    current = resolve(current, part);
    try {
      before = await lstat(current);
    } catch {
      throw new RemanError("reman_pdf_invalid_or_missing");
    }
    if (before.isSymbolicLink()) throw new RemanError("reman_pdf_symlink_denied");
    if (index < located.parts.length - 1 && !before.isDirectory()) {
      throw new RemanError("reman_pdf_path_denied");
    }
  }
  if (!before?.isFile()) throw new RemanError("reman_pdf_not_regular");
  if (before.size <= 0 || (options.maxBytes !== undefined && before.size > options.maxBytes)) {
    throw new RemanError("reman_pdf_exceeds_grant_limit");
  }
  try {
    if ((await realpath(located.path)) !== located.path) throw new RemanError("reman_pdf_symlink_denied");
  } catch (error) {
    if (error instanceof RemanError) throw error;
    throw new RemanError("reman_pdf_invalid_or_missing");
  }
  await options.beforeOpen?.(located.path);

  const noFollow = "O_NOFOLLOW" in constants ? constants.O_NOFOLLOW : 0;
  let handle;
  try {
    handle = await open(located.path, constants.O_RDONLY | noFollow);
  } catch {
    throw new RemanError("reman_pdf_changed_during_read");
  }
  try {
    const opened = await handle.stat();
    if (!opened.isFile() || !sameFile(before, opened)) throw new RemanError("reman_pdf_changed_during_read");
    const content = await handle.readFile();
    const after = await handle.stat();
    let pathAfter;
    try {
      pathAfter = await lstat(located.path);
    } catch {
      throw new RemanError("reman_pdf_changed_during_read");
    }
    if (!sameFile(opened, after) || !sameFile(after, pathAfter)) {
      throw new RemanError("reman_pdf_changed_during_read");
    }
    return { path: located.path, content, size: opened.size };
  } finally {
    await handle.close();
  }
}
