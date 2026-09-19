import { fail } from "./mod.fail";
import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { formatPluginInventory } from "./mod.formatPluginInventory";

export function listPlugins(args: string[], legacy = false): number {
  let flags = args;
  if (args[0] === "ls") flags = args.slice(1);
  else if (!legacy) return fail("usage: maw plugin ls [-v|--verbose] [--all]");
  let verbose = false, all = false;
  for (const arg of flags) {
    if ((arg === "-v" || arg === "--verbose") && !verbose) verbose = true;
    else if (arg === "--all" && !all) all = true;
    else return fail(`usage: maw ${legacy ? "plugins [ls]" : "plugin ls"} [-v|--verbose] [--all]`);
  }
  try {
    const paths = inventoryPaths();
    const plugins = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config));
    process.stdout.write(formatPluginInventory(plugins, verbose, all));
    return 0;
  } catch (error) {
    console.error(`maw: ${(error as Error).message}`);
    return 1;
  }
}
