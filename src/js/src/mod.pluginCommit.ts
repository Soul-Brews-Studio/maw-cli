import { spawnSync } from "node:child_process";

// The short commit of a plugin directory that is its own Git checkout, for
// `maw <plugin> version` (#52); "" for anything else. `--show-prefix` prints an
// empty line only at the top of a work tree, so an enclosing repository never
// answers for a plugin inside it. Inherited GIT_* routing (a hook's GIT_DIR) is
// dropped, GIT_OPTIONAL_LOCKS=0 keeps it from writing, and any failure or the
// two-second timeout reads as "not a Git checkout".
export function pluginCommit(dir: string): string {
  const env: NodeJS.ProcessEnv = { GIT_OPTIONAL_LOCKS: "0" };
  for (const [key, value] of Object.entries(process.env)) if (!key.startsWith("GIT_")) env[key] = value;
  const result = spawnSync("git", ["-C", dir, "rev-parse", "--show-prefix", "--short", "HEAD"], {
    env, encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"],
  });
  const match = result.status === 0 ? /^\n([0-9a-f]{4,64})\n?$/.exec(result.stdout) : null;
  return match ? match[1] : "";
}
