import { formatPluginTable } from "./mod.formatPluginTable";
import type { InstalledPlugin } from "./types";

export type PluginLsOptions = { verbose: boolean; all: boolean; filters: string[]; json: boolean };

// " matching core+api" — maw-rs appends this wherever a filter narrowed the set.
const filterLabel = (filters: string[]) => filters.length ? ` matching ${filters.join("+")}` : "";

function renderJson(plugins: InstalledPlugin[], filters: string[]): string {
  const active = plugins.filter(plugin => plugin.enabled).length;
  return `${JSON.stringify({
    active,
    disabled: plugins.length - active,
    filters,
    missingExecutables: plugins.filter(plugin => plugin.missing).length,
    plugins: plugins.map(plugin => ({
      api: plugin.api && plugin.apiPath ? plugin.apiPath : null,
      cli: plugin.cli ? (plugin.command || plugin.name) : null,
      dir: plugin.dir,
      disabled: !plugin.enabled,
      missingExecutable: plugin.missing,
      name: plugin.name,
      tier: plugin.tier,
      version: plugin.version,
    })),
    total: plugins.length,
  }, null, 2)}\n`;
}

export function formatPluginInventory(plugins: InstalledPlugin[], options: PluginLsOptions): string {
  const { verbose, filters, json } = options;
  // JSON is decided before the empty early-return: a consumer that asked for
  // --json must get parseable output on every path, including the empty one.
  if (json) return renderJson(plugins, filters);
  if (!plugins.length) return filters.length ? `no plugins${filterLabel(filters)}.\n` : "no plugins installed\n";
  const active = plugins.filter(p => p.enabled).length, disabled = plugins.length - active;
  // -v lists every row, disabled included, as maw-rs does; --all only affects
  // the compact listing.
  if (verbose) return formatPluginTable(plugins);
  const visible = plugins;
  const count = (tier: string) => visible.filter(p => p.tier === tier).length;
  const missing = visible.filter(p => p.missing).length;
  const health = missing ? `${missing} missing executable${missing === 1 ? "" : "s"}` : "ok";
  const names = visible.map(p => p.enabled ? (p.missing ? `${p.name} (no executable)` : p.name) : `${p.name} (disabled)`);
  const lines = [`${plugins.length} plugin${plugins.length === 1 ? "" : "s"} (${active} active, ${disabled} disabled)${filterLabel(filters)}`,
    `  core: ${count("core")} · standard: ${count("standard")} · extra: ${count("extra")}`,
    `  cli: ${visible.filter(p => p.cli).length} · api: ${visible.filter(p => p.api).length} · health: ${health}`];
  if (visible.length) lines.push(`  ${names.join(" · ")}`);
  return lines.join("\n") + "\n";
}
