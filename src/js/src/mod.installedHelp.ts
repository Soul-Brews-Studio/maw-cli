import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";
import { helpRows } from "./mod.helpRows";
import type { Command, InstalledPlugin } from "./types";

const COMMAND = /^[a-z][a-z0-9-]*$/;
const RESERVED = ["go", "rs", "js", "zig", "index"];

// First non-empty line, with control characters (terminal escapes) blanked.
function oneLine(text: string): string {
  return (text.trim().split(/[\r\n]/)[0] ?? "").replace(/[\u0000-\u001f\u007f-\u009f]/g, " ").trim();
}

// Root help's "Installed plugins" rows (#53), read from manifests only. A row is
// what dispatch reaches: the inventory is already one plugin per manifest name,
// and dispatch takes the first plugin in tier/name order declaring a command, so
// a later plugin declaring the same command never gets a row. Throws when the
// inventory cannot be read, as `plugin ls` fails.
export function installedHelp(registry: Map<string, Command>, columns: number): string[] {
  const paths = inventoryPaths();
  const plugins = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config));
  const claimed = new Map<string, InstalledPlugin>();
  const holders = new Map<string, number>();
  for (const plugin of plugins) {
    const command = plugin.command;
    if (COMMAND.test(command) && !RESERVED.includes(command) && !claimed.has(command)) claimed.set(command, plugin);
    if (plugin.cli && plugin.enabled) for (const alias of new Set(plugin.aliases)) holders.set(alias, (holders.get(alias) ?? 0) + 1);
  }
  // An alias shows only if it reaches this plugin (#55): typeable, not a
  // built-in, PATH executable or plugin command, and no other enabled plugin
  // declares it, since an alias two enabled plugins declare runs neither.
  const reachable = (word: string) => COMMAND.test(word) && !RESERVED.includes(word) && !registry.has(word) && !claimed.has(word) && holders.get(word) === 1;
  const rows: [string, string][] = [];
  let disabled = 0;
  for (const command of [...claimed.keys()].sort()) {
    const plugin = claimed.get(command)!;
    if (!plugin.enabled) { disabled++; continue; }
    const aliases = [...new Set(plugin.aliases.filter(reachable))];
    const shadow = registry.get(command);
    const mark = shadow ? `(shadowed by ${shadow.path ? `PATH maw-${command}` : "built-in"})` : "";
    const summary = oneLine(plugin.description) || oneLine(plugin.help);
    rows.push([aliases.length ? `${command} (${aliases.join(", ")})` : command, [mark, summary].filter(Boolean).join(" ")]);
  }
  const lines = helpRows(rows, columns);
  if (disabled) lines.push(`  ${disabled} disabled — maw plugin ls --all`);
  return lines;
}
