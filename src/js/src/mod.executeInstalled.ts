import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { findBun } from "./mod.findBun";
import { execute } from "./mod.execute";

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
    return await execute(bun, [plugin.entry, ...args]);
  } catch (error) {
    console.error(`maw: ${(error as Error).message}`);
    return 1;
  }
}
