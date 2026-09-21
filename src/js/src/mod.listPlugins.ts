import { fail } from "./mod.fail";
import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { formatPluginInventory } from "./mod.formatPluginInventory";

const TIER_FLAGS: Record<string, string> = { "--core": "core", "--standard": "standard", "--extra": "extra" };
const USAGE = "[-v|--verbose] [--json] [--all] [--core] [--standard] [--extra] [--api] [--disabled <name>]...";

export function listPlugins(args: string[], legacy = false): number {
  let flags = args;
  if (args[0] === "ls") flags = args.slice(1);
  else if (!legacy) return fail(`usage: maw plugin ls ${USAGE}`);
  const usage = () => fail(`usage: maw ${legacy ? "plugins [ls]" : "plugin ls"} ${USAGE}`);
  let verbose = false, all = false, apiOnly = false, json = false;
  const tiers: string[] = [];
  // Names disabled on the command line, as maw-rs does: listing-only, it never
  // writes config.
  const disabledArgs: string[] = [];
  for (let index = 0; index < flags.length; index++) {
    const arg = flags[index]!;
    if ((arg === "-v" || arg === "--verbose") && !verbose) verbose = true;
    else if (arg === "--all" && !all) all = true;
    else if (arg === "--json" && !json) json = true;
    else if (arg === "--api" && !apiOnly) apiOnly = true;
    else if (TIER_FLAGS[arg]) tiers.push(TIER_FLAGS[arg]!);
    else if (arg === "--disabled") {
      const value = flags[++index];
      if (!value || value.startsWith("-")) return usage();
      disabledArgs.push(value);
    } else return usage();
  }
  try {
    const paths = inventoryPaths();
    const disabled = disabledPlugins(paths.config);
    for (const name of disabledArgs) disabled.add(name);
    let plugins = scanInstalledPlugins(paths.plugins, disabled);
    if (tiers.length) plugins = plugins.filter(plugin => tiers.includes(plugin.tier));
    if (apiOnly) plugins = plugins.filter(plugin => plugin.api);
    const filters = [...tiers, ...(apiOnly ? ["api"] : [])];
    process.stdout.write(formatPluginInventory(plugins, { verbose, all, filters, json }));
    return 0;
  } catch (error) {
    console.error(`maw: ${(error as Error).message}`);
    return 1;
  }
}
