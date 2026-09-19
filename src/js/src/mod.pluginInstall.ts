import { existsSync, lstatSync, mkdirSync, mkdtempSync, realpathSync, renameSync, rmSync } from "node:fs";
import { join } from "node:path";
import { inventoryPaths } from "./mod.inventoryPaths";
import { pluginGit } from "./mod.pluginGit";
import { pluginMetadata } from "./mod.pluginMetadata";
import { pluginEntryPath } from "./mod.pluginEntryPath";
import { pluginRef } from "./mod.pluginRef";

export function pluginInstall(source: string, ref?: string): number {
  if (existsSync(source)) {
    if (!lstatSync(source).isDirectory()) throw new Error("source must be a Git directory");
    source = realpathSync(source);
  } else {
    if (source === "herdr") source = "Soul-Brews-Studio/maw-herdr-plugin";
    const shorthand = /^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)(?:@(.+))?$/.exec(source);
    if (shorthand) {
      if (ref && shorthand[2]) throw new Error("ref provided twice");
      ref ||= shorthand[2];
      source = `https://github.com/${shorthand[1]}`;
    } else if (!/^https:\/\/[^\s]+$/.test(source)) throw new Error("source must be herdr, owner/repo, HTTPS URL, or local Git directory");
  }
  const root = inventoryPaths().plugins;
  mkdirSync(root, { recursive: true });
  const stage = mkdtempSync(join(root, ".install-"));
  const dir = join(stage, "plugin");
  try {
    pluginGit(stage, ["clone", "--no-local", "--", source, dir]);
    if (ref) pluginGit(dir, ["checkout", "--detach", pluginRef(dir, ref)]);
    const m = pluginMetadata(dir);
    pluginEntryPath(dir, "plugin.json");
    pluginEntryPath(dir, m.entry);
    const target = join(root, m.name);
    try { lstatSync(target); throw new Error("plugin destination already exists"); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
    renameSync(dir, target);
    console.log(`installed ${m.name} ${pluginGit(target, ["rev-parse", "HEAD"])}`);
    return 0;
  } finally { rmSync(stage, { recursive: true, force: true }); }
}
