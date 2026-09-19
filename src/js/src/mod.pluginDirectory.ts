import { lstatSync, realpathSync } from "node:fs";
import { join, resolve } from "node:path";
import { inventoryPaths } from "./mod.inventoryPaths";
import { pluginGit } from "./mod.pluginGit";

export function pluginDirectory(name: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name)) throw new Error("invalid plugin name");
  const dir = join(inventoryPaths().plugins, name);
  if (!lstatSync(dir).isDirectory() || lstatSync(dir).isSymbolicLink()) throw new Error("plugin must be a real directory");
  if (!lstatSync(join(dir, ".git")).isDirectory()) throw new Error("plugin must own its Git checkout");
  if (realpathSync(pluginGit(dir, ["rev-parse", "--show-toplevel"])) !== realpathSync(dir)) throw new Error("plugin must own its Git checkout");
  return resolve(dir);
}
