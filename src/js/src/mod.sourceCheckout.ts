import { existsSync, realpathSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { pluginGit } from "./mod.pluginGit";

// The git checkout of this repository that a source run (bun cli.ts, bun link)
// is executing from, found by walking up from the running module's real path.
// Read-only: it asks git for the branch and porcelain status, nothing else.
export function sourceCheckout(module: string): { root: string; branch: string; dirty: boolean } | undefined {
  let path: string;
  try { path = realpathSync(module); } catch { return undefined; }
  for (let root = dirname(path); ; root = dirname(root)) {
    if (existsSync(join(root, ".git"))) {
      if (!relative(root, path).startsWith(`src${sep}js${sep}`) || !existsSync(join(root, "src", "js", "src", "cli.ts"))) return undefined;
      let branch = "", dirty = false;
      try { branch = pluginGit(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], true); } catch { /* detached or unreadable */ }
      try { dirty = pluginGit(root, ["status", "--porcelain"]) !== ""; } catch { /* unknown; say nothing */ }
      return { root, branch, dirty };
    }
    if (dirname(root) === root) return undefined;
  }
}
