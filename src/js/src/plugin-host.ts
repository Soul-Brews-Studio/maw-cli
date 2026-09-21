// Invokes an SDK-style plugin: one that exports a handler expecting an
// InvokeContext rather than running its work at import time.
//
// Running such a plugin as a plain script imports the module, fires whatever
// top-level side effects it has, and exits without ever calling the handler.
// On a machine with the full plugin set that looks like `maw ls` printing a
// stray "loaded config: ..." line and nothing else.
//
// argv: <entry> [args...]
const [entry, ...args] = Bun.argv.slice(2);

const module = await import(entry);
const handler = typeof module.default === "function"
  ? module.default
  : typeof module.handler === "function"
    ? module.handler
    : undefined;

if (!handler) {
  console.error(`maw: plugin entry ${entry} exports no handler`);
  console.error(`  bun ${entry} ${args.join(" ")}`);
  process.exit(126);
}

// source "cli" means the plugin streams straight to the terminal, which keeps
// interactive and long-running verbs live instead of buffering to the end.
//
// The writer must reach stdout directly. Plugins funnel their console.log into
// ctx.writer, so a writer that calls console.log recurses until the stack dies.
const result = await handler({
  source: "cli",
  args,
  matchedName: process.env.MAW_MATCHED_NAME || undefined,
  writer: (...parts: unknown[]) => {
    process.stdout.write(`${parts.map(part => typeof part === "string" ? part : Bun.inspect(part)).join(" ")}\n`);
  },
});

if (result && typeof result === "object") {
  if (result.output) process.stdout.write(result.output.endsWith("\n") ? result.output : `${result.output}\n`);
  if (result.error) console.error(result.error);
  process.exit(result.ok ? 0 : (result.exitCode ?? 1));
}
process.exit(0);
