import { sorted } from "./mod.sorted";
import { readDefaultPlugin } from "./mod.defaultPlugin";
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
  if (fallback) console.log(`Default: ${fallback} — unmatched verbs route to it (maw default unset to stop).`);
  return 0;
}
