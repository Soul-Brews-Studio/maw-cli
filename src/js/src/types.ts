export type Command = {
  name: string;
  summary: string;
  usage?: string;
  path?: string;
  run: (args: string[]) => number | Promise<number>;
};

export type InstalledPlugin = {
  name: string; version: string; tier: "core" | "standard" | "extra";
  dir: string; enabled: boolean; cli: boolean; api: boolean; missing: boolean;
  command: string; entry: string; runtime: string; target: string; interactive: boolean;
};
