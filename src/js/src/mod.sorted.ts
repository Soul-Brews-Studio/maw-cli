import type { Command } from "./types";

export function sorted(registry: Map<string, Command>): Command[] {
  return [...registry.values()].sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
}
