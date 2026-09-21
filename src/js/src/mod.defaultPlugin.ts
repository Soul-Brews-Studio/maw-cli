import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { readPluginJson } from "./mod.readPluginJson";
import { safePath } from "./mod.safePath";

// The unnumbered file is the base layer, so a numbered maw.config.<n>.json can
// still override what `maw default set` writes here.
const FILE = "maw.config.json";

export function readDefaultPlugin(config: string): string {
  const value = readPluginJson(join(config, FILE));
  return typeof value?.defaultPlugin === "string" ? value.defaultPlugin : "";
}

// Writes only defaultPlugin, preserving every other key, and replaces the file
// atomically so a crash cannot leave a half-written config.
export function writeDefaultPlugin(config: string, name: string | null): void {
  const path = join(config, FILE);
  let current: Record<string, unknown> = {};
  try { current = readPluginJson(path) ?? {}; }
  catch { throw new Error(`refusing to overwrite unreadable config: ${safePath(path)}`); }
  if (name === null) delete current.defaultPlugin; else current.defaultPlugin = name;
  mkdirSync(config, { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(current, null, 2)}\n`, { mode: 0o644 });
  renameSync(temporary, path);
}

export function configFilePath(config: string): string {
  return join(config, FILE);
}
