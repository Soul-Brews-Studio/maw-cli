import { spawnSync } from "node:child_process";

// The short commit of the Git work tree a plugin directory lies in, for
// `maw <plugin> version` (#52); "" when it lies in none. git runs inside the
// directory, so a symlinked plugin reports the repository its target lives in,
// even from a subfolder of a larger one. `rev-parse --short HEAD`, never
// `describe`: plugin checkouts never fetch new tags, so describe goes stale.
// Inherited GIT_* routing (a hook's GIT_DIR) is dropped, GIT_OPTIONAL_LOCKS=0
// keeps it from writing, and any failure or the two-second timeout reads as
// "not a Git checkout".
export function pluginCommit(dir: string): string {
  const env: NodeJS.ProcessEnv = { GIT_OPTIONAL_LOCKS: "0" };
  for (const [key, value] of Object.entries(process.env)) if (!key.startsWith("GIT_")) env[key] = value;
  const result = spawnSync("git", ["-C", dir, "rev-parse", "--is-inside-work-tree", "--short", "HEAD"], {
    env, encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"],
  });
  const match = result.status === 0 ? /^true\n([0-9a-f]{4,64})\n?$/.exec(result.stdout) : null;
  return match ? match[1] : "";
}
