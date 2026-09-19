import { fail } from "./mod.fail";

declare const MAW_VERSION: string;
const version = typeof MAW_VERSION === "undefined" ? "dev" : MAW_VERSION;

export function showVersion(args: string[]): number {
  if (args.length) return fail("usage: maw version");
  console.log(`maw ${version}`);
  return 0;
}
