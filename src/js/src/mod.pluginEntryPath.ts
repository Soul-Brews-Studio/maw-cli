import { lstatSync } from "node:fs";
import { join } from "node:path";

export function pluginEntryPath(dir: string, entry: string): string {
  let path = dir;
  for (const part of entry.split("/")) {
    path = join(path, part);
    if (lstatSync(path).isSymbolicLink()) throw new Error("plugin entry traverses a symlink");
  }
  if (!lstatSync(path).isFile()) throw new Error("plugin entry is not a regular file");
  return path;
}
