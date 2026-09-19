import { readdirSync } from "node:fs";
import { join } from "node:path";
import { readPluginJson } from "./mod.readPluginJson";
import { safePath } from "./mod.safePath";

export function disabledPlugins(config: string): Set<string> {
  let files: string[];
  try { files = readdirSync(config); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return new Set();
    throw new Error(`cannot read config directory: ${safePath(config)}`);
  }
  const weighted = files.map(name => ({ name, match: /^maw\.config\.(\d+)(\.local)?\.json$/.exec(name) })).filter(item => item.match);
  weighted.sort((a, b) => {
    const aw = BigInt(a.match![1]), bw = BigInt(b.match![1]);
    return aw < bw ? -1 : aw > bw ? 1 : Number(!!a.match![2]) - Number(!!b.match![2]) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
  });
  files = weighted.length ? weighted.map(item => item.name) : ["maw.config.json"];
  let disabled = new Set<string>();
  for (const file of files) {
    const value = readPluginJson(join(config, file));
    if (Array.isArray(value?.disabledPlugins)) disabled = new Set(value.disabledPlugins.filter((name): name is string => typeof name === "string"));
  }
  return disabled;
}
