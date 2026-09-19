import { spawnSync } from "node:child_process";

export function pluginGit(dir: string, args: string[], optional = false): string {
  const env: NodeJS.ProcessEnv = {};
  for (const [key, value] of Object.entries(process.env)) if (!key.startsWith("GIT_")) env[key] = value;
  Object.assign(env, { GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_SYSTEM: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", GIT_TERMINAL_PROMPT: "0", GIT_LFS_SKIP_SMUDGE: "1" });
  const result = spawnSync("git", ["--literal-pathspecs", "-c", "user.name=maw", "-c", "user.email=maw@localhost", "-c", "protocol.ext.allow=never", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-C", dir, ...args], { env, encoding: "utf8", maxBuffer: 2097152, timeout: 120000 });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    if (optional && result.status === 1) return "";
    throw new Error(`git ${args[0]} failed: ${result.stderr.trim()}`);
  }
  return result.stdout.trimEnd();
}
