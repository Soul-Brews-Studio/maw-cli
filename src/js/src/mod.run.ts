import { discover } from "./mod.discover";
import { execute } from "./mod.execute";
import { executeInstalled } from "./mod.executeInstalled";
import { fail } from "./mod.fail";
import { unknown } from "./mod.unknown";
import { rootHelp } from "./mod.rootHelp";
import { help } from "./mod.help";
import { showVersion } from "./mod.showVersion";
import { pluginLifecycle } from "./mod.pluginLifecycle";
import { marketplace } from "./mod.marketplace";
import { locate } from "./mod.locate";
import { defaultCommand } from "./mod.defaultCommand";
import { readDefaultPlugin } from "./mod.defaultPlugin";
import { inventoryPaths } from "./mod.inventoryPaths";
import type { Command } from "./types";

export async function run(args: string[]): Promise<number> {
  const registry = new Map<string, Command>();
  registry.set("help", { name: "help", summary: "Show command help", usage: "maw help [command]", run: (args) => help(registry, args) });
  registry.set("version", {
    name: "version", summary: "Show maw version", usage: "maw version",
    run: showVersion,
  });
  registry.set("plugin", {
    name: "plugin", summary: "Manage installed plugins", usage: "maw plugin ls [-v|--verbose] [--all]|list|install SOURCE [--ref REF]|update NAME [--ref REF]|info NAME|check NAME",
    run: (args) => pluginLifecycle(args),
  });
  registry.set("plugins", {
    name: "plugins", summary: "Alias for plugin; bare invocation lists", usage: "maw plugins [ls|list] [-v|--verbose] [--all]|install SOURCE [--ref REF]|update NAME [--ref REF]|info NAME|check NAME",
    run: (args) => pluginLifecycle(args, true),
  });
  registry.set("marketplace", { name: "marketplace", summary: "List known plugin sources", usage: "maw marketplace [ls|list]", run: marketplace });
  registry.set("default", {
    name: "default", summary: "Route unmatched verbs to a default plugin",
    usage: "maw default [set <plugin>|unset]",
    run: defaultCommand,
  });
  registry.set("locate", {
    name: "locate", summary: "Resolve a registered oracle to its local checkout",
    usage: "maw locate <oracle> [--path | --json] [--no-remote]",
    run: locate,
  });
  for (const [name, path] of discover()) {
    if (registry.has(name)) continue;
    registry.set(name, { name, path, summary: "External plugin", run: (args) => execute(path, args) });
  }
  if (args.length === 0) return rootHelp(registry);
  let name = args[0];
  if (["-h", "--help", "-v", "--version"].includes(name) && args.length !== 1) {
    return fail("global help/version flags do not accept arguments");
  }
  if (name === "-h" || name === "--help") name = "help";
  if (name === "-v" || name === "--version") name = "version";
  const command = registry.get(name);
  if (!command) {
    const installed = await executeInstalled(name, args.slice(1));
    if (installed !== undefined) return installed;
    const fallback = defaultPluginFor(name);
    if (fallback) {
      const routed = await executeInstalled(fallback, args);
      if (routed !== undefined) return routed;
    }
    return unknown(args[0]);
  }
  if (!command.path && args.length === 2 && ["-h", "--help"].includes(args[1])) return help(registry, [name]);
  return command.run(args.slice(1));
}

// Reading config must never break dispatch: an unreadable or absent config
// simply means no default.
function defaultPluginFor(name: string): string {
  try {
    const fallback = readDefaultPlugin(inventoryPaths().config);
    return fallback && fallback !== name ? fallback : "";
  } catch { return ""; }
}
