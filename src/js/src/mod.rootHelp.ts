import { sorted } from "./mod.sorted";
import { readDefaultPlugin } from "./mod.defaultPlugin";
import { pluginVerbs } from "./mod.pluginVerbs";
import { inventoryPaths } from "./mod.inventoryPaths";
import { installedHelp } from "./mod.installedHelp";
import { helpRows } from "./mod.helpRows";
import { terminalWidth } from "./mod.terminalWidth";
import type { Command } from "./types";

export function rootHelp(registry: Map<string, Command>): number {
  const columns = terminalWidth();
  console.log("Usage: maw <command> [args]\n\nCommands:");
  for (const command of sorted(registry)) {
    if (command.name === "plugins" || command.path) continue;
    console.log(`  ${command.name.padEnd(12)} ${command.summary}`);
  }
  let installed: string[] = [];
  try { installed = installedHelp(registry, columns); }
  catch (error) { console.error(`maw: installed plugins not listed: ${(error as Error).message}\n  maw plugin ls`); }
  if (installed.length) console.log(`\nInstalled plugins:\n${installed.join("\n")}`);
  const external = sorted(registry).filter(command => command.path).map((command): [string, string] => [command.name, `maw-${command.name}`]);
  if (external.length) console.log(`\nExternal (PATH):\n${helpRows(external, columns).join("\n")}`);
  console.log("\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.");
  let fallback = "";
  try { fallback = readDefaultPlugin(inventoryPaths().config); } catch { /* no config, no default */ }
  if (fallback) {
    const verbs = pluginVerbs(fallback);
    console.log(`\nDefault: ${fallback} — unmatched verbs route to it (maw default unset to stop).`);
    if (verbs.length) console.log(`  via ${fallback}:  ${verbs.join("  ")}`);
  }
  return 0;
}
