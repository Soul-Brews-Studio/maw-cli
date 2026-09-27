import { existsSync, realpathSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { checkoutGit } from "./mod.checkoutGit";

// The git checkout of this repository that a source run (bun cli.ts, bun link)
// is executing from, found by walking up from the running module's real path,
// so it is always the tree whose code is running. Reads only the branch name.
export function sourceCheckout(module: string): { root: string; branch: string } | undefined {
  let path: string;
  try { path = realpathSync(module); } catch { return undefined; }
  for (let root = dirname(path); ; root = dirname(root)) {
    if (existsSync(join(root, ".git"))) {
      if (!relative(root, path).startsWith(`src${sep}js${sep}`) || !existsSync(join(root, "src", "js", "src", "cli.ts"))) return undefined;
      let branch = "";
      try { branch = checkoutGit(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], true); } catch { /* git unavailable */ }
      return { root, branch };
    }
    if (dirname(root) === root) return undefined;
  }
}
