import { spawnSync } from "node:child_process";

const result = spawnSync("npm", ["ls", "--all", "--json"], { encoding: "utf8" });
let parsed;
try {
  parsed = JSON.parse(result.stdout || "{}");
} catch {
  process.stderr.write(result.stderr || "Unable to parse npm dependency tree.\n");
  process.exit(1);
}

const problems = Array.isArray(parsed.problems) ? parsed.problems : [];
if (!problems.length && result.status === 0) {
  process.stdout.write("OpenClaw dependency tree is clean.\n");
  process.exit(0);
}

const expected = [
  /^invalid: tar@7\.5\.16 .*\/openclaw\/node_modules\/tar$/u,
  /^invalid: @types\/retry@0\.12\.5 .*\/openclaw\/node_modules\/@types\/retry$/u,
];
const onlyDocumentedUpstreamProblems = problems.length === expected.length
  && expected.every((pattern) => problems.some((problem) => pattern.test(String(problem))));

if (!onlyDocumentedUpstreamProblems) {
  process.stderr.write(`Unexpected npm dependency problems:\n${problems.join("\n")}\n`);
  process.exit(1);
}

const sourceCiException = process.env.REMAN_SOURCE_CI_ALLOW_DOCUMENTED_OPENCLAW_P2 === "1";
const message = "KNOWN UPSTREAM P2: openclaw@2026.6.11 publishes incompatible transitive ranges for tar and @types/retry. See DEPENDENCY_NOTES.md.";
if (sourceCiException) {
  process.stdout.write(`${message} Accepted only for source CI; release remains blocked.\n`);
  process.exit(0);
}

process.stderr.write(`${message} Release verification is fail-closed until this P2 is resolved.\n`);
process.exit(1);
