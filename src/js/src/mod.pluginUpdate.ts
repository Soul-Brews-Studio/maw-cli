import { pluginDirectory } from "./mod.pluginDirectory";
import { pluginMetadata } from "./mod.pluginMetadata";
import { pluginEntryPath } from "./mod.pluginEntryPath";
import { pluginGit } from "./mod.pluginGit";
import { pluginRef } from "./mod.pluginRef";

export function pluginUpdate(name: string, ref?: string): number {
  const dir = pluginDirectory(name);
  if (pluginGit(dir, ["status", "--porcelain", "--untracked-files=all"])) throw new Error("plugin has local changes; update refused");
  const current = pluginMetadata(dir);
  if (current.name !== name) throw new Error("plugin name differs from installation");
  pluginEntryPath(dir, "plugin.json");
  pluginEntryPath(dir, current.entry);
  const branch = pluginGit(dir, ["symbolic-ref", "--quiet", "--short", "HEAD"], true);
  if (!branch && !ref) { console.log(`${name} pinned to ${pluginGit(dir, ["rev-parse", "HEAD"])}; use --ref to change it`); return 0; }
  let candidate: string;
  if (ref) candidate = pluginRef(dir, ref);
  else {
    pluginGit(dir, ["fetch", "--no-tags", "origin"]);
    candidate = pluginGit(dir, ["rev-parse", "--verify", "@{upstream}^{commit}"]);
    pluginGit(dir, ["merge-base", "--is-ancestor", "HEAD", candidate]);
  }
  const m = pluginMetadata(dir, candidate);
  if (m.name !== name) throw new Error("candidate plugin name changed");
  if (ref) {
    pluginGit(dir, ["checkout", "--detach", candidate]);
  } else pluginGit(dir, ["merge", "--ff-only", candidate]);
  console.log(`updated ${name} ${candidate}`);
  return 0;
}
