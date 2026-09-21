import { fail } from "./mod.fail";
import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { configFilePath, readDefaultPlugin, writeDefaultPlugin } from "./mod.defaultPlugin";

const USAGE = "usage: maw default [set <plugin>|unset]";

export function defaultCommand(args: string[]): number {
  const [subcommand = "", ...rest] = args;
  const paths = inventoryPaths();
  if (subcommand === "") {
    const current = readDefaultPlugin(paths.config);
    console.log(current || "none");
    return 0;
  }
  if (subcommand === "unset" || subcommand === "reset") {
    if (rest.length) return fail(USAGE);
    if (!readDefaultPlugin(paths.config)) { console.log("none"); return 0; }
    writeDefaultPlugin(paths.config, null);
    console.log(`default unset (${configFilePath(paths.config)})`);
    return 0;
  }
  if (subcommand !== "set") return fail(`maw default: unsupported subcommand "${subcommand}"\n${USAGE}`);
  const [name, ...extra] = rest;
  if (!name || extra.length) return fail(USAGE);
  // Refuse a name that resolves to nothing rather than storing it and failing
  // later at every unmatched verb.
  const plugins = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config));
  const plugin = plugins.find(candidate => candidate.command === name || candidate.name === name);
  if (!plugin || !plugin.cli) {
    console.error(`maw default: no installed plugin provides "${name}"`);
    for (const candidate of plugins.filter(p => p.cli).slice(0, 10)) {
      console.error(`  maw default set ${candidate.command || candidate.name}`);
    }
    return 1;
  }
  if (!plugin.enabled) {
    console.error(`maw default: plugin ${plugin.name} is disabled`);
    return 1;
  }
  writeDefaultPlugin(paths.config, plugin.command || plugin.name);
  console.log(`default: ${plugin.command || plugin.name} (${configFilePath(paths.config)})`);
  return 0;
}
