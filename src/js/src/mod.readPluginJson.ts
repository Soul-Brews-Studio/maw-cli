import { closeSync, fstatSync, openSync, readSync, statSync } from "node:fs";
import { safePath } from "./mod.safePath";

export function readPluginJson(path: string): Record<string, unknown> | null {
  try {
    const stat = statSync(path);
    if (!stat.isFile() || stat.size > 1048576) throw new Error();
    const fd = openSync(path, "r");
    let data: Buffer;
    try {
      if (!fstatSync(fd).isFile()) throw new Error();
      const buffer = Buffer.alloc(Math.min(stat.size + 1, 1048577));
      let size = 0;
      while (size < buffer.length) {
        const count = readSync(fd, buffer, size, buffer.length - size, null);
        if (!count) break;
        size += count;
      }
      if (size > 1048576) throw new Error();
      data = buffer.subarray(0, size);
    } finally { closeSync(fd); }
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(data));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return value;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw new Error(`cannot read JSON metadata: ${safePath(path)}`);
  }
}
