import { pluginDirectory } from "./mod.pluginDirectory";
import { pluginMetadata } from "./mod.pluginMetadata";
import { pluginEntryPath } from "./mod.pluginEntryPath";
import { pluginGit } from "./mod.pluginGit";

export function pluginInfo(name: string, check: boolean): number {
  const dir = pluginDirectory(name), m = pluginMetadata(dir);
  if (m.name !== name) throw new Error("plugin name differs from installation");
  pluginEntryPath(dir, "plugin.json");
  const actual = pluginGit(dir, ["hash-object", "--no-filters", "--", pluginEntryPath(dir, m.entry)]);
  const modified = actual !== m.hash || pluginGit(dir, ["status", "--porcelain", "--untracked-files=all"]) !== "";
  const source = pluginGit(dir, ["remote", "get-url", "origin"]);
  console.log(`source\t${source}\ncommit\t${pluginGit(dir, ["rev-parse", "HEAD"])}\nentry\t${m.entry}\nhash\t${actual}\nstatus\t${modified ? "modified" : "clean"}`);
  return check && modified ? 1 : 0;
}
