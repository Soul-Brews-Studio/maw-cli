import { fail } from "./mod.fail";

export function unknown(name: string): number {
  return fail(`unknown command ${JSON.stringify(name)}; run 'maw help'`);
}
