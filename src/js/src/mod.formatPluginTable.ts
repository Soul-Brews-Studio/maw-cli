import { homedir } from "node:os";
import { safePath } from "./mod.safePath";
import type { InstalledPlugin } from "./types";

const TIERS = ["core", "standard", "extra"] as const;
const ICON: Record<string, string> = {
  core: "\u001b[32m●\u001b[0m",
  standard: "\u001b[36m●\u001b[0m",
  extra: "\u001b[33m●\u001b[0m",
};
const DISABLED_ICON = "\u001b[90m○\u001b[0m";
const HEADERS = ["name", "version", "tier", "surfaces", "dir"];

const tilde = (dir: string) => {
  const home = homedir();
  return dir === home || dir.startsWith(`${home}/`) ? `~${dir.slice(home.length)}` : dir;
};

// Mirrors maw-rs: a cli surface falls back to the plugin name when the manifest
// declares no cli.command, api reports its PATH rather than a command, and a
// plugin with neither surface renders as an em dash, not an empty cell.
const surfaces = (plugin: InstalledPlugin) => {
  const parts: string[] = [];
  if (plugin.cli) parts.push(`cli:${plugin.command || plugin.name}`);
  if (plugin.api && plugin.apiPath) parts.push(`api:${plugin.apiPath}`);
  return parts.length ? parts.join(" ") : "\u2014";
};

const icon = (plugin: InstalledPlugin) => plugin.enabled ? (ICON[plugin.tier] ?? "") : DISABLED_ICON;

// Width is the raw char count, escape sequences included, exactly as maw-rs
// measures it: its `tier` column is 15 for "<esc>●<esc> core" (5+1+4+5), not 6.
const chars = (cell: string) => [...cell].length;
const pad = (cell: string, width: number) =>
  chars(cell) >= width ? cell : cell + " ".repeat(width - chars(cell));

export function formatPluginTable(plugins: InstalledPlugin[]): string {
  const rows = [...plugins].sort((a, b) =>
    TIERS.indexOf(a.tier) - TIERS.indexOf(b.tier) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  let output = "";
  for (const tier of TIERS) {
    const tierRows = rows.filter(plugin => plugin.tier === tier);
    if (!tierRows.length) continue;
    // maw-rs measures the tier column with the plain tier name even for a
    // disabled row, whose rendered label is the wider "disabled". Replicated so
    // a disabled row under-pads identically instead of realigning the table.
    const widths = HEADERS.map((header, column) => Math.max(chars(header), ...tierRows.map(plugin => chars([
      plugin.name,
      plugin.version,
      `${icon(plugin)} ${tier}`,
      surfaces(plugin),
      safePath(tilde(plugin.dir)),
    ][column]!))));
    output += `\n\u001b[1m${tier}\u001b[0m (${tierRows.length})\n`;
    output += `${HEADERS.map((header, column) => pad(header, widths[column]!)).join("  ")}\n`;
    output += `${widths.map(width => "─".repeat(width)).join("  ")}\n`;
    for (const plugin of tierRows) {
      const cells = [
        plugin.name,
        plugin.version,
        `${icon(plugin)} ${plugin.enabled ? tier : "disabled"}`,
        surfaces(plugin),
        safePath(tilde(plugin.dir)),
      ];
      output += `${cells.map((cell, column) => pad(cell, widths[column]!)).join("  ")}\n`;
    }
  }
  const active = rows.filter(plugin => plugin.enabled).length;
  const disabled = rows.length - active;
  output += disabled > 0
    ? `\n${active} active. ${disabled} disabled — use 'maw plugin ls --all' to see them.\n`
    : `\n${active} active\n`;
  return output;
}
