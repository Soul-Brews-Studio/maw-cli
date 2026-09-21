import { sorted } from "./mod.sorted";
import { readDefaultPlugin } from "./mod.defaultPlugin";
import { pluginVerbs } from "./mod.pluginVerbs";
import { inventoryPaths } from "./mod.inventoryPaths";
import type { Command } from "./types";

export function rootHelp(registry: Map<string, Command>): number {
  console.log("Usage: maw <command> [args]\n\nCommands:");
  for (const command of sorted(registry)) {
    if (command.name === "plugins") continue;
    console.log(`  ${command.name.padEnd(12)} ${command.summary}`);
  }
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
