import { fail } from "./mod.fail";
import { readOracleRegistry } from "./mod.readOracleRegistry";
import { resolveOracle } from "./mod.resolveOracle";
import { safePath } from "./mod.safePath";
import type { Oracle } from "./types";

const USAGE = "usage: maw locate <oracle> [--path | --json] [--no-remote]";

export function locate(args: string[]): number {
  let target = "";
  let path = false;
  let json = false;
  for (const argument of args) {
    if (argument === "--path") { if (path) return fail(USAGE); path = true; continue; }
    if (argument === "--json") { if (json) return fail(USAGE); json = true; continue; }
    if (argument === "--no-remote") continue;
    if (argument.startsWith("-")) return fail(`unknown option ${argument}\n${USAGE}`);
    if (target) return fail(USAGE);
    target = argument;
  }
  if (!target || (path && json)) return fail(USAGE);

  let oracles: Oracle[];
  try { oracles = readOracleRegistry(); }
  catch (error) { console.error(`maw: ${(error as Error).message}`); return 1; }

  const resolution = resolveOracle(oracles, target);
  if (resolution.kind === "ambiguous") {
    console.error(`maw: '${safePath(target)}' matches ${resolution.candidates.length} oracles:`);
    for (const candidate of resolution.candidates.slice(0, 10)) {
      console.error(`    ${candidate.name}\t${candidate.org}/${candidate.repo}`);
    }
    if (resolution.candidates.length > 10) console.error(`    … ${resolution.candidates.length - 10} more`);
    console.error("  name one exactly, or use <org>/<repo>");
    return 1;
  }
  if (resolution.kind === "none") {
    console.error(`maw: oracle '${safePath(target)}' not found in ${oracles.length} registered`);
    return 1;
  }

  const { oracle } = resolution;
  if (json) { console.log(JSON.stringify({ name: oracle.name, org: oracle.org, repo: oracle.repo, local_path: oracle.localPath })); return 0; }
  if (path) {
    if (!oracle.localPath) { console.error(`maw: oracle '${oracle.name}' has no local_path`); return 1; }
    console.log(oracle.localPath);
    return 0;
  }
  console.log(`${oracle.name}\t${oracle.org}/${oracle.repo}\t${oracle.localPath || "(no local path)"}`);
  return 0;
}
