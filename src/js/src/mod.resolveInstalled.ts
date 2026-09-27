import type { InstalledPlugin } from "./types";

// The plugin a verb names (#55): one whose command (cli.command, else its
// manifest name) it is, first in inventory order, and only then one declaring it
// in cli.aliases, so an alias never shadows a command. Built-ins and PATH
// executables were already tried by the caller. An alias that more than one
// enabled plugin declares resolves to none of them: `ambiguous` holds every
// holder. A disabled holder answers only when no enabled one does.
export function resolveInstalled(plugins: InstalledPlugin[], name: string): { plugin?: InstalledPlugin; ambiguous: InstalledPlugin[] } {
  const named = plugins.find(candidate => candidate.cli && candidate.command === name);
  if (named) return { plugin: named, ambiguous: [] };
  const holders = plugins.filter(candidate => candidate.cli && candidate.aliases.includes(name));
  const enabled = holders.filter(candidate => candidate.enabled);
  if (enabled.length > 1) return { ambiguous: enabled };
  return { plugin: enabled[0] ?? holders[0], ambiguous: [] };
}
