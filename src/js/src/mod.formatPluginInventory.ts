import { safePath } from "./mod.safePath";
import { formatPluginTable } from "./mod.formatPluginTable";
import type { InstalledPlugin } from "./types";

export function formatPluginInventory(plugins: InstalledPlugin[], verbose: boolean, all: boolean): string {
  if (!plugins.length) return "no plugins installed\n";
  const active = plugins.filter(p => p.enabled).length, disabled = plugins.length - active;
  const visible = plugins.filter(p => all || p.enabled);
  if (verbose) return visible.length ? formatPluginTable(visible) : "";
  const count = (tier: string) => visible.filter(p => p.tier === tier).length;
  const missing = visible.filter(p => p.missing).length;
  const health = missing ? `${missing} missing executable${missing === 1 ? "" : "s"}` : "ok";
  const lines = [`${plugins.length} plugin${plugins.length === 1 ? "" : "s"} (${active} active, ${disabled} disabled)`,
    `  core: ${count("core")} · standard: ${count("standard")} · extra: ${count("extra")}`,
    `  cli: ${visible.filter(p => p.cli).length} · api: ${visible.filter(p => p.api).length} · health: ${health}`];
  if (visible.length) lines.push(`  ${visible.map(p => p.name).join(" · ")}`);
  if (!all && disabled) lines.push("  disabled hidden by default — use --all to include");
  return lines.join("\n") + "\n";
}
