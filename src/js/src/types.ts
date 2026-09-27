export type Command = {
  name: string;
  summary: string;
  usage?: string;
  path?: string;
  run: (args: string[]) => number | Promise<number>;
};

export type Oracle = { name: string; org: string; repo: string; localPath: string };

export type InstalledPlugin = {
  name: string; version: string; tier: "core" | "standard" | "extra";
  dir: string; enabled: boolean; cli: boolean; api: boolean; missing: boolean;
  command: string; entry: string; runtime: string; target: string; interactive: boolean; apiPath: string; aliases: string[]; help: string; description: string;
};

export type PublishedRelease = { tag: string; draft: boolean; published: string; assets: { name: string; size: number }[] };
export type ReleasePlan = { schema: string; skip: boolean; tag: string; commit: string; archives: string[] };
export type ReleasePlatform = { os: "linux" | "darwin"; arch: "amd64" | "arm64" };
// An update failure plus the copy-pasteable command lines that fix or narrow it.
export type UpdateError = Error & { fix?: string[] };
