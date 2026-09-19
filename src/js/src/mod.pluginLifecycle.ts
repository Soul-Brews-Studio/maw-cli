import { fail } from "./mod.fail";
import { listPlugins } from "./mod.listPlugins";
import { pluginInstall } from "./mod.pluginInstall";
import { pluginUpdate } from "./mod.pluginUpdate";
import { pluginInfo } from "./mod.pluginInfo";

export function pluginLifecycle(args: string[], legacy = false): number {
  if (["ls", "list"].includes(args[0]) || (legacy && (!args.length || args[0].startsWith("-")))) return listPlugins(args[0] === "list" ? ["ls", ...args.slice(1)] : args, legacy);
  const [verb, name, ...rest] = args;
  if (!["install", "update", "info", "check"].includes(verb) || !name || name.startsWith("-") || (rest.length && (rest.length !== 2 || rest[0] !== "--ref" || !rest[1] || !["install", "update"].includes(verb)))) return fail("usage: maw plugin ls|install SOURCE [--ref REF]|update NAME [--ref REF]|info NAME|check NAME");
  try {
    if (verb === "install") return pluginInstall(name, rest[1]);
    if (verb === "update") return pluginUpdate(name, rest[1]);
    return pluginInfo(name, verb === "check");
  } catch (error) { console.error(`maw: ${(error as Error).message}`); return 1; }
}
