import { fail } from "./mod.fail";
import { sorted } from "./mod.sorted";
import type { Command } from "./types";

export function listPlugins(registry: Map<string, Command>, args: string[]): number {
  if (args.length) return fail("usage: maw plugins");
  console.log("NAME\tTYPE\tPATH");
  for (const command of sorted(registry)) {
    console.log(`${command.name}\t${command.path ? "external" : "builtin"}\t${command.path ?? "-"}`);
  }
  return 0;
}
