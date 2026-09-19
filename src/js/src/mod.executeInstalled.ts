import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { findBun } from "./mod.findBun";
import { execute } from "./mod.execute";

export async function executeInstalled(name: string, args: string[]): Promise<number | undefined> {
  if (!/^[a-z][a-z0-9-]*$/.test(name) || ["go", "rs", "js", "zig", "index"].includes(name)) return;
  try {
    const paths = inventoryPaths();
    const plugin = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config)).find(p => p.command === name);
    if (!plugin) return;
    if (!plugin.enabled) {
      console.error(`maw: plugin ${plugin.name} is disabled`);
      return 1;
    }
    if (plugin.runtime !== "bun-dev" || plugin.target !== "js" || !plugin.interactive) {
      console.error(`maw: plugin ${plugin.name} is not a standalone Bun CLI (requires runtime=bun-dev, target=js, cli.interactive=true)`);
      return 126;
    }
    if (!plugin.entry || plugin.missing) {
      console.error(`maw: plugin ${plugin.name} entry is missing or not a regular file`);
      return 126;
    }
    const bun = findBun();
    if (!bun) {
      console.error(`maw: plugin ${plugin.name} requires bun on PATH`);
      return 126;
    }
    return await execute(bun, [plugin.entry, ...args]);
  } catch (error) {
    console.error(`maw: ${(error as Error).message}`);
    return 1;
  }
}
