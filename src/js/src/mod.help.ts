import { fail } from "./mod.fail";
import { rootHelp } from "./mod.rootHelp";
import { unknown } from "./mod.unknown";
import type { Command } from "./types";

export function help(registry: Map<string, Command>, args: string[]): number | Promise<number> {
  if (args.length === 0) return rootHelp(registry);
  if (args.length !== 1) return fail("usage: maw help [command]");
  const command = registry.get(args[0]);
  if (!command) return unknown(args[0]);
  if (command.path) return command.run(["--help"]);
  console.log(`Usage: ${command.usage}\n\n${command.summary}`);
  return 0;
}
