import { discover } from "./mod.discover";
import { execute } from "./mod.execute";
import { executeInstalled } from "./mod.executeInstalled";
import { fail } from "./mod.fail";
import { unknown } from "./mod.unknown";
import { rootHelp } from "./mod.rootHelp";
import { help } from "./mod.help";
import { showVersion } from "./mod.showVersion";
import { listPlugins } from "./mod.listPlugins";
import type { Command } from "./types";

export async function run(args: string[]): Promise<number> {
  const registry = new Map<string, Command>();
  registry.set("help", { name: "help", summary: "Show command help", usage: "maw help [command]", run: (args) => help(registry, args) });
  registry.set("version", {
    name: "version", summary: "Show maw version", usage: "maw version",
    run: showVersion,
  });
  registry.set("plugin", {
    name: "plugin", summary: "List installed plugin metadata", usage: "maw plugin ls [-v|--verbose] [--all]",
    run: (args) => listPlugins(args),
  });
  registry.set("plugins", {
    name: "plugins", summary: "Alias for plugin ls", usage: "maw plugins [ls] [-v|--verbose] [--all]",
    run: (args) => listPlugins(args, true),
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
  if (!command) return (await executeInstalled(name, args.slice(1))) ?? unknown(args[0]);
  if (!command.path && args.length === 2 && ["-h", "--help"].includes(args[1])) return help(registry, [name]);
  return command.run(args.slice(1));
}
