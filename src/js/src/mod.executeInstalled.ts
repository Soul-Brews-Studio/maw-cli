import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { findBun } from "./mod.findBun";
import { execute } from "./mod.execute";

// Two plugin shapes exist in the wild. Script-style plugins do their work at
// import time; SDK-style ones export a handler and do nothing until it is
// called. Running the latter as a script silently produces no output, so the
// shape has to be decided before anything executes — inspecting by importing
// would fire the script-style side effects twice.
export function isSdkStylePlugin(source: string): boolean {
  return /^\s*export\s+default\s+(async\s+)?function/m.test(source)
    || /^\s*export\s+default\s+[A-Za-z_$][\w$]*\s*;?\s*$/m.test(source)
    || /^\s*export\s+(async\s+)?function\s+handler\b/m.test(source)
    || /^\s*export\s+const\s+handler\s*[:=]/m.test(source);
}

// maw-rs dispatches any enabled plugin whose cli command (or alias) matches and
// that has an entry path, running it under Bun. There is no runtime/target/
// interactive gate: `today` declares no cli.interactive and `dropbox` no target,
// and both run there, so requiring them here made maw refuse real plugins.
export async function executeInstalled(name: string, args: string[]): Promise<number | undefined> {
  if (!/^[a-z][a-z0-9-]*$/.test(name) || ["go", "rs", "js", "zig", "index"].includes(name)) return;
  try {
    const paths = inventoryPaths();
    const plugins = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config));
    const plugin = plugins.find(candidate => candidate.cli
      && (candidate.command === name || candidate.aliases.includes(name)));
    if (!plugin) return;
    if (!plugin.enabled) {
      console.error(`maw: plugin ${plugin.name} is disabled`);
      return 1;
    }
    if (!plugin.entry || plugin.missing) {
      console.error(`maw: plugin ${plugin.name} entry is missing or not a regular file`);
      return 126;
    }
    const bun = findBun();
    if (!bun) {
      console.error("TS/JS plugin requires prebuilt WASM artifact; no maw-js/Bun fallback");
      return 2;
    }
    let sdkStyle = false;
    try { sdkStyle = isSdkStylePlugin(readFileSync(plugin.entry, "utf8")); } catch { /* unreadable: run as a script */ }
    if (!sdkStyle) return await execute(bun, [plugin.entry, ...args]);

    const host = join(dirname(fileURLToPath(import.meta.url)), "plugin-host.ts");
    return await execute(bun, [host, plugin.entry, ...args], { MAW_MATCHED_NAME: name });
  } catch (error) {
    console.error(`maw: ${(error as Error).message}`);
    return 1;
  }
}
