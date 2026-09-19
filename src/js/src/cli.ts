import { discover, execute } from "./plugins";
import { indexTrace } from "./index";

type Command = {
  name: string;
  summary: string;
  usage?: string;
  path?: string;
  run: (args: string[]) => number | Promise<number>;
};

export async function run(args: string[]): Promise<number> {
  const registry = new Map<string, Command>();
  const sorted = () => [...registry.values()].sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
  const fail = (message: string) => {
    console.error(`maw: ${message}`);
    return 2;
  };
  const unknown = (name: string) => fail(`unknown command ${JSON.stringify(name)}; run 'maw help'`);
  const rootHelp = () => {
    console.log("Usage: maw <command> [args]\n\nCommands:");
    for (const command of sorted()) {
      console.log(`  ${command.name.padEnd(12)} ${command.summary}`);
    }
    console.log("\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.");
    return 0;
  };
  const help = (args: string[]): number | Promise<number> => {
    if (args.length === 0) return rootHelp();
    if (args.length !== 1) return fail("usage: maw help [command]");
    const command = registry.get(args[0]);
    if (!command) return unknown(args[0]);
    if (command.path) return command.run(["--help"]);
    console.log(`Usage: ${command.usage}\n\n${command.summary}`);
    return 0;
  };
  registry.set("help", { name: "help", summary: "Show command help", usage: "maw help [command]", run: help });
  registry.set("index", {
    name: "index", summary: "Index MCP-shaped JSONL context records", usage: "maw index FILE|-", run: indexTrace,
  });
  registry.set("version", {
    name: "version", summary: "Show maw version", usage: "maw version",
    run: (args) => {
      if (args.length) return fail("usage: maw version");
      console.log("maw dev");
      return 0;
    },
  });
  registry.set("plugins", {
    name: "plugins", summary: "List commands and executable plugin paths", usage: "maw plugins",
    run: (args) => {
      if (args.length) return fail("usage: maw plugins");
      console.log("NAME\tTYPE\tPATH");
      for (const command of sorted()) {
        console.log(`${command.name}\t${command.path ? "external" : "builtin"}\t${command.path ?? "-"}`);
      }
      return 0;
    },
  });
  for (const [name, path] of discover()) {
    if (registry.has(name)) continue;
    registry.set(name, { name, path, summary: "External plugin", run: (args) => execute(path, args) });
  }
  if (args.length === 0) return rootHelp();
  let name = args[0];
  if (["-h", "--help", "-v", "--version"].includes(name) && args.length !== 1) {
    return fail("global help/version flags do not accept arguments");
  }
  if (name === "-h" || name === "--help") name = "help";
  if (name === "-v" || name === "--version") name = "version";
  const command = registry.get(name);
  if (!command) return unknown(args[0]);
  if (!command.path && args.length === 2 && ["-h", "--help"].includes(args[1])) return help([name]);
  return command.run(args.slice(1));
}

if (import.meta.main) process.exitCode = await run(Bun.argv.slice(2));
