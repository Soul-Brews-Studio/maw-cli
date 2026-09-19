import { existsSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { readPluginJson } from "./mod.readPluginJson";
import { safePath } from "./mod.safePath";
import type { InstalledPlugin } from "./types";

export function scanInstalledPlugins(root: string, disabled: Set<string>): InstalledPlugin[] {
  const overrides = readPluginJson(join(root, ".overrides.json")) || {};
  let names: string[];
  try { names = readdirSync(root).sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b))); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw new Error(`cannot read plugin directory: ${safePath(root)}`);
  }
  const found = new Map<string, InstalledPlugin>();
  for (const folder of names) {
    const dir = join(root, folder);
    try { if (!statSync(dir).isDirectory()) continue; } catch { continue; }
    try {
      const m = readPluginJson(join(dir, "plugin.json"));
      if (!m) {
        if (existsSync(join(dir, "plugin.ts"))) console.error(`maw: skipped TypeScript-only manifest: ${safePath(dir)}`);
        continue;
      }
      if (typeof m.name !== "string" || !/^[A-Za-z0-9._-]+$/.test(m.name) ||
          typeof m.version !== "string" || !m.version || /[\u0000-\u001f\u007f-\u009f]/.test(m.version)) throw new Error();
      if (m.tier !== undefined && !["core", "standard", "extra"].includes(m.tier as string)) throw new Error();
      if (m.weight !== undefined && (typeof m.weight !== "number" || !Number.isFinite(m.weight) || m.weight < 0 || m.weight > 99)) throw new Error();
      if (found.has(m.name)) continue;
      let weight = (m.weight as number | undefined) ?? 50;
      const override = overrides[m.name];
      if (typeof override === "number" && Number.isFinite(override) && override >= 0 && override <= 99) weight = override;
      const tier = (m.tier as InstalledPlugin["tier"] | undefined) || (weight < 10 ? "core" : weight < 50 ? "standard" : "extra");
      const artifact = m.artifact && typeof m.artifact === "object" && !Array.isArray(m.artifact) ? m.artifact as Record<string, unknown> : {};
      const entry = typeof m.entry === "string" ? m.entry : "";
      const wasm = typeof m.wasm === "string" ? m.wasm : "";
      const bundle = m.target !== "wasm" && typeof artifact.path === "string" ? artifact.path : "";
      const path = entry || bundle || wasm;
      const cli = (!!m.cli && typeof m.cli === "object" && !Array.isArray(m.cli)) || !!path;
      const api = !!m.api && typeof m.api === "object" && !Array.isArray(m.api);
      let missing = cli && !path;
      if (path) { try { missing = !statSync(resolve(dir, path)).isFile(); } catch { missing = true; } }
      const cliConfig = m.cli && typeof m.cli === "object" && !Array.isArray(m.cli) ? m.cli as Record<string, unknown> : null;
      found.set(m.name, {
        name: m.name, version: m.version, tier, dir, enabled: !disabled.has(m.name), cli, api, missing,
        command: cliConfig ? (typeof cliConfig.command === "string" && cliConfig.command ? cliConfig.command : m.name) : "",
        entry: path ? resolve(dir, path) : "", runtime: typeof m.runtime === "string" ? m.runtime : "",
        target: typeof m.target === "string" ? m.target : "", interactive: cliConfig?.interactive === true,
      });
    } catch { console.error(`maw: skipped invalid plugin.json: ${safePath(dir)}`); }
  }
  return [...found.values()].sort((a, b) => ["core", "standard", "extra"].indexOf(a.tier) - ["core", "standard", "extra"].indexOf(b.tier) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
}
