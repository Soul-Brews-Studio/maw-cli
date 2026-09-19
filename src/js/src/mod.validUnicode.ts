import { object } from "./mod.object";

// JSON.parse permits lone UTF-16 surrogates; other parsers reject them.
export function validUnicode(value: unknown): boolean {
  const pending: unknown[] = [value];
  while (pending.length) {
    const item = pending.pop();
    if (typeof item === "string") {
      for (let i = 0; i < item.length; i++) {
        const code = item.charCodeAt(i);
        if (code >= 0xdc00 && code <= 0xdfff) return false;
        if (code >= 0xd800 && code <= 0xdbff) {
          const low = item.charCodeAt(++i);
          if (!(low >= 0xdc00 && low <= 0xdfff)) return false;
        }
      }
    } else if (Array.isArray(item)) {
      for (const child of item) pending.push(child);
    } else if (object(item)) {
      for (const [key, child] of Object.entries(item)) pending.push(key, child);
    }
  }
  return true;
}
