import { realpathSync, statSync } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

export function findBun(): string | undefined {
  for (const directory of (process.env.PATH ?? "").split(delimiter)) {
    if (!isAbsolute(directory)) continue;
    try {
      const path = realpathSync(join(directory, process.platform === "win32" ? "bun.exe" : "bun"));
      const info = statSync(path);
      if (info.isFile() && (process.platform === "win32" || (info.mode & 0o111) !== 0)) return path;
    } catch { /* Continue past missing runtimes and broken symlinks. */ }
  }
}
