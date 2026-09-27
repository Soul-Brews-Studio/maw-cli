import { execFileSync } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// A source build has no MAW_VERSION, so describe the code actually running:
// the CalVer of the checkout's HEAD commit and its short hash (#47). Same scheme
// as release tags, v{yy}.{m}.{d}-alpha.{H*100+M} in Asia/Bangkok, so a dev build
// and the release cut from the same commit read alike. The commit's time, not
// the wall clock: it names the code, and it does not change between calls.
// Any failure (no git, not a checkout, timeout) returns "" and the caller
// prints plain "dev". GIT_OPTIONAL_LOCKS=0 keeps `version` from writing.
export function devCalver(): string {
  try {
    const here = dirname(fileURLToPath(import.meta.url));
    const out = execFileSync("git", ["-C", here, "log", "-1", "--format=%ct %h"], {
      encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"],
      env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" },
    }).trim();
    const match = /^(\d+) ([0-9a-f]{4,40})$/.exec(out);
    if (!match) return "";
    return `${calver(Number(match[1]) * 1000)} (${match[2]})`;
  } catch {
    return "";
  }
}

export function calver(epochMs: number): string {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Bangkok", year: "2-digit", month: "numeric", day: "numeric",
    hour: "numeric", minute: "numeric", hourCycle: "h23",
  }).formatToParts(new Date(epochMs)).map(p => [p.type, p.value]));
  const hmm = Number(parts.hour) * 100 + Number(parts.minute);
  return `v${Number(parts.year)}.${Number(parts.month)}.${Number(parts.day)}-alpha.${hmm}`;
}
