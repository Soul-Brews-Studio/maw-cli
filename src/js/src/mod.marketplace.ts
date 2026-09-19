import { fail } from "./mod.fail";

export function marketplace(args: string[]): number {
  if (args.length > 1 || (args.length === 1 && !["ls", "list"].includes(args[0]))) return fail("usage: maw marketplace [ls|list]");
  console.log("NAME\tSOURCE\nherdr\thttps://github.com/Soul-Brews-Studio/maw-herdr-plugin");
  return 0;
}
