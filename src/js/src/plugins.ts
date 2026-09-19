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
      if (plugins.has(name)) continue;
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

export async function execute(path: string, args: string[]): Promise<number> {
  try {
    const child = Bun.spawn([path, ...args], {
      stdin: "inherit",
      stdout: "inherit",
      stderr: "inherit",
      env: process.env,
    });
    let interrupted = false;
    const interrupt = () => {
      interrupted = true;
      child.kill("SIGKILL");
    };
    process.on("SIGINT", interrupt);
    try {
      const code = await child.exited;
      return interrupted ? 1 : child.signalCode ? 126 : code;
    } finally {
      process.off("SIGINT", interrupt);
    }
  } catch (error) {
    console.error(`maw: cannot execute ${path}: ${error instanceof Error ? error.message : error}`);
    return 126;
  }
}
