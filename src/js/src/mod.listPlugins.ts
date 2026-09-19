import { fail } from "./mod.fail";
import { sorted } from "./mod.sorted";
import type { Command } from "./types";

export function listPlugins(registry: Map<string, Command>, args: string[], legacy = false): number {
  if (!(args.length === 1 && args[0] === "ls") && !(legacy && args.length === 0)) {
    return fail(legacy ? "usage: maw plugins [ls]" : "usage: maw plugin ls");
  }
  console.log("NAME\tTYPE\tPATH");
  for (const command of sorted(registry)) {
    console.log(`${command.name}\t${command.path ? "external" : "builtin"}\t${command.path ?? "-"}`);
  }
  return 0;
}
