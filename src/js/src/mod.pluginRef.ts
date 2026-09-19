import { pluginGit } from "./mod.pluginGit";

export function pluginRef(dir: string, ref: string): string {
  if (!ref || ref.startsWith("-") || /[\x00-\x20\x7f]/.test(ref)) throw new Error("invalid Git ref");
  pluginGit(dir, ["check-ref-format", "--allow-onelevel", ref]);
  pluginGit(dir, ["fetch", "--no-tags", "origin", ref]);
  const commit = pluginGit(dir, ["rev-parse", "--verify", "FETCH_HEAD^{commit}"]);
  if (/^[0-9a-fA-F]{40}$/.test(ref) && commit !== ref.toLowerCase()) throw new Error("resolved commit differs from requested SHA");
  return commit;
}
