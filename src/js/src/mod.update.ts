import { selectRelease } from "./mod.selectRelease";
import { releaseMetadata } from "./mod.releaseMetadata";
import { updateStatus } from "./mod.updateStatus";
import { installRelease } from "./mod.installRelease";
import { sourceCheckout } from "./mod.sourceCheckout";
import { releasePlatform } from "./mod.releasePlatform";
import { releaseAssetUrl } from "./mod.releaseAssetUrl";
import { apiOrigin, repository } from "./mod.validReleaseUrl";
import { tagPattern } from "./mod.compareTags";
import { updateError } from "./mod.updateError";
import { shellQuote } from "./mod.shellQuote";
import { version } from "./mod.showVersion";
import type { UpdateError } from "./types";

export const updateUsage = "maw update [--check] [--version vYY.M.D-alpha.HMM]";
export const updateSummary = "Update maw-js from verified alpha release assets (not plugins)";
const reinstall = "bun add --global 'git+https://github.com/Soul-Brews-Studio/maw-cli.git#alpha'";

// Port of the Go updater: select a published alpha, verify its assets, prove
// the candidate, then replace this standalone maw-js. A source run never
// replaces anything; from a git checkout it prints the git commands instead.
export async function update(args: string[]): Promise<number> {
  let check = false, tag = "";
  const rest = [...args];
  while (rest.length && rest[0] !== "-" && rest[0].startsWith("-")) {
    const argument = rest.shift()!;
    if (argument === "--") break;
    const flag = /^--?([^-=][^=]*)(?:=(.*))?$/.exec(argument);
    if (flag?.[1] === "check" && [undefined, "true", "false"].includes(flag[2])) check = flag[2] !== "false";
    else if (flag?.[1] === "version" && (flag[2] ?? rest[0]) !== undefined) tag = flag[2] ?? rest.shift()!;
    else if (flag?.[1] === "h" || flag?.[1] === "help") { console.log(`Usage: ${updateUsage}\n\n${updateSummary}`); return 0; }
    else return refuse(`usage: ${updateUsage}`, "maw update --check");
  }
  if (rest.length || (tag && !tagPattern.test(tag))) return refuse(`usage: ${updateUsage}`, "maw update --check");
  // A compiled maw-js runs from Bun's embedded filesystem; anything else is a
  // script whose process.execPath is the bun runtime, which must never be replaced.
  const standalone = Bun.main.startsWith("/$bunfs/");
  if (!check && (version === "dev" || !standalone)) return refuseSource(standalone);
  const platform = releasePlatform();
  if (!platform) return refuse("update: self-update supports Linux/macOS amd64/arm64 only", reinstall);

  const rerun = ["maw", "update", ...args].map(shellQuote).join(" ");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(updateError("timed out after 3 minutes; original executable unchanged", rerun)), 180_000);
  let fallback = `curl -sSIL ${shellQuote(`${apiOrigin}/repos/${repository}/releases${tag ? `/tags/${tag}` : "?per_page=30"}`)}`;
  try {
    const release = await selectRelease(tag, controller.signal);
    fallback = `curl -fsSL ${shellQuote(releaseAssetUrl(release.tag, "release.json"))}`;
    const asset = `maw-js-${platform.os}-${platform.arch}.tar.gz`;
    const { plan, sums } = await releaseMetadata(release, asset, controller.signal);
    process.stdout.write(`current\t${version}\ntarget\t${plan.tag}\ncommit\t${plan.commit}\n`);
    const { install, status } = updateStatus(version, plan, tag !== "");
    process.stdout.write(`status\t${status}\n`);
    if (check || !install) return 0;
    const path = await installRelease(release, plan, sums.get(asset)!, asset, platform, controller.signal);
    process.stdout.write(`updated\t${path}\n`);
    return 0;
  } catch (error) {
    const { message, fix } = error as UpdateError;
    console.error(`maw: update: ${message}`);
    for (const line of fix?.length ? fix : [fallback]) console.error(`  ${line}`);
    return 1;
  } finally {
    clearTimeout(timer);
  }
}

function refuse(message: string, ...fix: string[]): number {
  console.error(`maw: ${message}`);
  for (const line of fix) console.error(`  ${line}`);
  return 2;
}

function refuseSource(standalone: boolean): number {
  const checkout = standalone ? undefined : sourceCheckout(import.meta.path);
  if (!checkout) {
    return version === "dev"
      ? refuse("update: local dev builds are not self-updated; reinstall maw-js with bun (or use update --check)", reinstall)
      : refuse(`update: this maw runs as a script under ${process.execPath}, not as a standalone maw-js; refusing to replace the runtime`, reinstall);
  }
  const root = shellQuote(checkout.root);
  const fix = [`git -C ${root} pull --ff-only`];
  if (checkout.branch !== "alpha") fix.unshift(`git -C ${root} switch alpha`);
  if (!checkout.dirty) return refuse("update: this maw runs from a source checkout; update it with git", ...fix);
  console.error("maw: update: this maw runs from a source checkout; update it with git");
  return refuse(`update: ${checkout.root} has uncommitted changes; maw leaves them untouched, so commit or stash them first`, ...fix);
}
