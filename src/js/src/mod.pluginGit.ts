import { spawnSync } from "node:child_process";

// GIT_CONFIG_GLOBAL=/dev/null below is deliberate: a plugin clone must not inherit
// the user's aliases, hooks, url rewrites or filters. It also discards the one piece
// of global config a clone legitimately needs — the credential helper — so a private
// repo failed with `could not read Username for 'https://github.com'` even though a
// plain `git clone` of the same URL worked. Read the helpers out of the real config
// before nulling it, and re-inject only those.
function credentialArgs(): string[] {
  const read = spawnSync("git", ["config", "--get-regexp", "^credential\\."], { encoding: "utf8", maxBuffer: 262144, timeout: 10000 });
  if (read.status !== 0 || !read.stdout) return [];
  const args: string[] = [];
  for (const line of read.stdout.split("\n")) {
    const sep = line.indexOf(" ");
    if (sep < 1) continue;
    const key = line.slice(0, sep);
    const value = line.slice(sep + 1);
    // helper only. username/useHttpPath/etc. are not needed to authenticate and an
    // empty helper value is the documented "reset the list" entry — keep it, or a
    // later helper in the list would be applied in the wrong order.
    if (!/\.helper$/.test(key)) continue;
    args.push("-c", `${key}=${value}`);
  }
  return args;
}

export function pluginGit(dir: string, args: string[], optional = false): string {
  const env: NodeJS.ProcessEnv = {};
  for (const [key, value] of Object.entries(process.env)) if (!key.startsWith("GIT_")) env[key] = value;
  Object.assign(env, { GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_SYSTEM: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", GIT_TERMINAL_PROMPT: "0", GIT_LFS_SKIP_SMUDGE: "1" });
  const result = spawnSync("git", ["--literal-pathspecs", "-c", "user.name=maw", "-c", "user.email=maw@localhost", "-c", "protocol.ext.allow=never", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", ...credentialArgs(), "-C", dir, ...args], { env, encoding: "utf8", maxBuffer: 2097152, timeout: 120000 });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    if (optional && result.status === 1) return "";
    throw new Error(`git ${args[0]} failed: ${result.stderr.trim()}`);
  }
  return result.stdout.trimEnd();
}
