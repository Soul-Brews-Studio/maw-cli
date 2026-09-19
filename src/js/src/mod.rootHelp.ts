import { sorted } from "./mod.sorted";
import type { Command } from "./types";

export function rootHelp(registry: Map<string, Command>): number {
  console.log("Usage: maw <command> [args]\n\nCommands:");
  for (const command of sorted(registry)) {
    console.log(`  ${command.name.padEnd(12)} ${command.summary}`);
  }
  console.log("\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.");
  return 0;
}
