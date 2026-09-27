import { fail } from "./mod.fail";
import { devCalver } from "./mod.devCalver";

declare const MAW_VERSION: string;
export const version = typeof MAW_VERSION === "undefined" ? "dev" : MAW_VERSION;

export function showVersion(args: string[]): number {
  if (args.length) return fail("usage: maw version");
  // "dev" stays first so neither a person nor `maw update` mistakes a source
  // build for a published release; the internal version stays "dev".
  const detail = version === "dev" ? devCalver() : "";
  console.log(detail ? `maw ${version} ${detail}` : `maw ${version}`);
  return 0;
}
