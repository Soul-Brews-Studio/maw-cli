import { closeSync, fstatSync, openSync, readSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { safePath } from "./mod.safePath";
import type { Oracle } from "./types";

const MAX_BYTES = 4194304;
const MAX_ENTRIES = 4096;

export function oracleRegistryPath(): string {
  const home = process.env.MAW_HOME;
  return home ? join(home, "oracles.json") : join(homedir(), ".maw", "oracles.json");
}

export function readOracleRegistry(path = oracleRegistryPath()): Oracle[] {
  let data: Buffer;
  try {
    const stat = statSync(path);
    if (!stat.isFile() || stat.size > MAX_BYTES) throw new Error();
    const fd = openSync(path, "r");
    try {
      if (!fstatSync(fd).isFile()) throw new Error();
      const buffer = Buffer.alloc(Math.min(stat.size + 1, MAX_BYTES + 1));
      let size = 0;
      while (size < buffer.length) {
        const count = readSync(fd, buffer, size, buffer.length - size, null);
        if (!count) break;
        size += count;
      }
      if (size > MAX_BYTES) throw new Error();
      data = buffer.subarray(0, size);
    } finally { closeSync(fd); }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw new Error(`cannot read oracle registry: ${safePath(path)}`);
  }
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(data));
  } catch { throw new Error(`cannot read oracle registry: ${safePath(path)}`); }
  const oracles = (value as { oracles?: unknown })?.oracles;
  if (!Array.isArray(oracles)) throw new Error(`cannot read oracle registry: ${safePath(path)}`);
  if (oracles.length > MAX_ENTRIES) throw new Error(`oracle registry exceeds ${MAX_ENTRIES} entries: ${safePath(path)}`);
  const result: Oracle[] = [];
  for (const entry of oracles) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue;
    const { name, org, repo, local_path } = entry as Record<string, unknown>;
    if (typeof name !== "string" || !name) continue;
    result.push({
      name,
      org: typeof org === "string" ? org : "",
      repo: typeof repo === "string" ? repo : "",
      localPath: typeof local_path === "string" ? local_path : "",
    });
  }
  return result;
}
