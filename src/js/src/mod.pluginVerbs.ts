import { inventoryPaths } from "./mod.inventoryPaths";
import { disabledPlugins } from "./mod.disabledPlugins";
import { scanInstalledPlugins } from "./mod.scanInstalledPlugins";

// Plugins already state their verbs in the help line they register, e.g.
//   maw herdr <ls|a|wake|hey|peek|federation|serve> [--json]
// Reading that is cheaper and safer than executing a plugin to ask, which help
// must never do. A plugin that does not use the convention simply contributes
// no verbs.
export function pluginVerbs(command: string): string[] {
  let plugins;
  try {
    const paths = inventoryPaths();
    plugins = scanInstalledPlugins(paths.plugins, disabledPlugins(paths.config));
  } catch { return []; }
  const plugin = plugins.find(candidate => candidate.enabled
    && (candidate.command === command || candidate.name === command));
  const group = /<([^>]+)>/.exec(plugin?.help ?? "");
  if (!group) return [];
  return group[1]!
    .split("|")
    .map(verb => verb.trim())
    .filter(verb => /^[a-z][a-z0-9-]*$/.test(verb));
}
