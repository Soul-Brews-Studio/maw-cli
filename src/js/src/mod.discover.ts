import { readdirSync, realpathSync, statSync } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

export function discover(): Map<string, string> {
  const plugins = new Map<string, string>();
  for (const directory of (process.env.PATH ?? "").split(delimiter)) {
    if (!isAbsolute(directory)) continue;
    let entries: string[];
    try {
      entries = readdirSync(directory);
    } catch {
      continue;
    }
    for (const entry of entries) {
      let filename = entry;
      if (process.platform === "win32") {
        if (!filename.endsWith(".exe")) continue;
        filename = filename.slice(0, -4);
      }
      if (!/^maw-[a-z][a-z0-9-]*$/.test(filename)) continue;
      const name = filename.slice(4);
      if (["go", "rs", "js", "zig"].includes(name) || plugins.has(name)) continue;
      try {
        const path = realpathSync(join(directory, entry));
        const info = statSync(path);
        if (!info.isFile()) continue;
        if (process.platform !== "win32" && (info.mode & 0o111) === 0) continue;
        plugins.set(name, path);
      } catch {
        // Unreadable files and broken symlinks are not eligible plugins.
      }
    }
  }
  return plugins;
}
