import { spawnSync } from "node:child_process";

// Variables that could point git at a repository other than the checkout.
const routing = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"];

// git in the developer's own source checkout, as if they typed the command:
// their config, hooks and credentials apply. It never prompts, is bounded by a
// timeout, and drops inherited routing so it acts on `root` and nothing else.
// With `optional`, a non-zero exit returns "" instead of throwing.
export function checkoutGit(root: string, args: string[], optional = false, timeout = 30_000): string {
  const env: NodeJS.ProcessEnv = { ...process.env, GIT_TERMINAL_PROMPT: "0" };
  for (const key of routing) delete env[key];
  const result = spawnSync("git", ["-C", root, ...args], { env, encoding: "utf8", maxBuffer: 2097152, timeout });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    if (optional) return "";
    throw new Error(`git ${args[0]} failed: ${result.stderr.trim() || (result.signal ? `signal ${result.signal}` : `exit status ${result.status}`)}`);
  }
  return result.stdout.trimEnd();
}
